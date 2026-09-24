"""Warm ESRGAN HTTP service — loads RealESRGAN_x2plus once, serves requests."""

import time
import numpy as np
import cv2
import torch
import uvicorn
from fastapi import FastAPI, UploadFile, File
from fastapi.responses import Response

from basicsr.archs.rrdbnet_arch import RRDBNet
from realesrgan import RealESRGANer

MODEL_PATH = "weights/RealESRGAN_x2plus.pth"
TILE = 256
PORT = 8766

app = FastAPI()
_upsampler = None


@app.on_event("startup")
def _load():
    global _upsampler
    print(f"[esrgan-svc] loading {MODEL_PATH} ...")
    t0 = time.time()

    device = "cuda" if torch.cuda.is_available() else "cpu"
    print(f"[esrgan-svc] device = {device}")

    model = RRDBNet(
        num_in_ch=3, num_out_ch=3, num_feat=64,
        num_block=23, num_grow_ch=32, scale=2,   # x2
    )
    _upsampler = RealESRGANer(
        scale=2,
        model_path=MODEL_PATH,
        model=model,
        tile=TILE,
        tile_pad=10,
        pre_pad=0,
        half=False,
        device=device,
    )

    # Warm-up: use 512x512 so the TILED code path (padding + stitching)
    # is JIT-compiled too — a 64x64 dummy skips tiling entirely.
    print("[esrgan-svc] warming up CUDA kernels (512x512) ...")
    dummy = np.zeros((512, 512, 3), dtype=np.uint8)
    _upsampler.enhance(dummy, outscale=2)

    # Second warm-up at the true input aspect (roughly) to catch
    # any other shape-specific kernels the first one missed.
    dummy2 = np.zeros((384, 512, 3), dtype=np.uint8)
    _upsampler.enhance(dummy2, outscale=2)

    print(f"[esrgan-svc] ready in {time.time() - t0:.1f}s")


@app.get("/health")
def health():
    return {"ok": _upsampler is not None}


@app.post("/esrgan")
async def esrgan(file: UploadFile = File(...)):
    raw = await file.read()
    img = cv2.imdecode(np.frombuffer(raw, np.uint8), cv2.IMREAD_COLOR)
    if img is None:
        return Response(status_code=400, content=b"bad image")

    output, _ = _upsampler.enhance(img, outscale=2)

    ok, buf = cv2.imencode(".png", output)
    if not ok:
        return Response(status_code=500, content=b"encode failed")
    return Response(content=buf.tobytes(), media_type="image/png")


if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=PORT, log_level="info")