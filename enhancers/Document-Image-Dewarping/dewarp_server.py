"""Warm dewarp HTTP service — loads the model once, serves rectification requests."""
import time
import numpy as np
import cv2
import torch
import torch.nn.functional as F
import uvicorn
from fastapi import FastAPI, UploadFile, File
from fastapi.responses import Response

from model import DewarpTextlineMaskGuide

INPUT_SIZE = 224
MODEL_PATH = "pretrained_models/30.pt"
DEVICE = "cuda" if torch.cuda.is_available() else "cpu"
PORT = 8765

app = FastAPI()
_model = None


@app.on_event("startup")
def _load():
    global _model
    print(f"[dewarp-svc] loading {MODEL_PATH} on {DEVICE} ...")
    t0 = time.time()
    m = DewarpTextlineMaskGuide(image_size=INPUT_SIZE)
    state = torch.load(MODEL_PATH, map_location="cpu")
    state = {k.replace("module.", "", 1) if k.startswith("module.") else k: v
             for k, v in state.items()}
    m.load_state_dict(state)
    m.to(DEVICE).eval()
    _model = m

    # Warm-up — force CUDA JIT compile with a real-size dummy.
    # Without this, the FIRST request eats ~15-20s of kernel compilation.
    print(f"[dewarp-svc] warming up CUDA kernels ({INPUT_SIZE}x{INPUT_SIZE}) ...")
    dummy = np.zeros((INPUT_SIZE, INPUT_SIZE, 3), dtype=np.float32)
    dummy_t = (torch.from_numpy(dummy)
               .permute(2, 0, 1)
               .unsqueeze(0)
               .to(DEVICE)
               .float())
    with torch.no_grad():
        _ = m(dummy_t)

    print(f"[dewarp-svc] ready in {time.time() - t0:.1f}s")


@app.get("/health")
def health():
    return {"ok": _model is not None, "device": DEVICE}


@app.post("/dewarp")
async def dewarp(file: UploadFile = File(...)):
    raw = await file.read()
    img = cv2.imdecode(np.frombuffer(raw, np.uint8), cv2.IMREAD_COLOR)
    if img is None:
        return Response(status_code=400, content=b"bad image")

    img_h, img_w = img.shape[:2]
    rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB).astype(np.float32) / 255.0
    inp = cv2.resize(rgb, (INPUT_SIZE, INPUT_SIZE))
    inp_t = torch.from_numpy(inp).permute(2, 0, 1).unsqueeze(0).to(DEVICE).float()

    with torch.no_grad():
        bm = _model(inp_t)
        bm = (2 * (bm / 223.) - 1) * 0.99

    bm = bm.detach().cpu()
    bm0 = cv2.resize(bm[0, 0].numpy(), (img_w, img_h))
    bm1 = cv2.resize(bm[0, 1].numpy(), (img_w, img_h))
    bm0 = cv2.blur(bm0, (3, 3))
    bm1 = cv2.blur(bm1, (3, 3))

    lbl = torch.from_numpy(np.stack([bm0, bm1], axis=2)).unsqueeze(0).float()
    src = torch.from_numpy(rgb).permute(2, 0, 1).unsqueeze(0).float()
    with torch.no_grad():
        out = F.grid_sample(src, lbl, align_corners=True)

    img_geo = ((out[0] * 255.).permute(1, 2, 0).numpy()).astype(np.uint8)
    img_bgr = img_geo[:, :, ::-1]

    ok, buf = cv2.imencode(".png", img_bgr)
    return Response(content=buf.tobytes(), media_type="image/png")


if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=PORT, log_level="info")