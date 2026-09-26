from contextlib import asynccontextmanager
import asyncio
import subprocess
import time as _t
import urllib.error
import urllib.request
from pathlib import Path

from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from services.image_quality_service import ImageQualityGate
from services.enhancement_service import EnhancementService, _CACHE_DIR as ENHANCER_CACHE_DIR
from services.ocr_service import OCRService
from services.validation_service import ValidationService
from services.face_service import FaceVerificationService
from services.tampering_service import TamperingDetector
from risk_engine.scorer import RiskScorer
from blockchain.client import FabricClient
from app.routers.screening_finalize import router as screening_router

from app.core.redis import redis_client
from app.routers import liveness
from services.pipeline import DocumentPipeline
from app.routers.documents import router as documents_router
from app.routers.screening_history import router as history_router



# ---------------------------------------------------------------------------
# Warm-server paths
# ---------------------------------------------------------------------------
_ROOT = Path(__file__).resolve().parent.parent

_DEWARP_DIR    = _ROOT / "enhancers" / "Document-Image-Dewarping"
_DEWARP_PY     = _DEWARP_DIR / "venv" / "bin" / "python"
_DEWARP_SCRIPT = _DEWARP_DIR / "dewarp_server.py"
_DEWARP_HEALTH = "http://127.0.0.1:8765/health"

_ESRGAN_DIR    = _ROOT / "enhancers" / "Real-ESRGAN"
_ESRGAN_PY     = _ESRGAN_DIR / "venv" / "bin" / "python"
_ESRGAN_SCRIPT = _ESRGAN_DIR / "esrgan_server.py"
_ESRGAN_HEALTH = "http://127.0.0.1:8766/health"

_dewarp_proc: subprocess.Popen | None = None
_esrgan_proc: subprocess.Popen | None = None


def _service_up(health_url: str) -> bool:
    try:
        with urllib.request.urlopen(health_url, timeout=0.5) as r:
            return r.status == 200
    except Exception:
        return False


async def _wait_for_service(health_url: str, timeout_s: float = 60.0) -> bool:
    deadline = asyncio.get_event_loop().time() + timeout_s
    while asyncio.get_event_loop().time() < deadline:
        if await asyncio.to_thread(_service_up, health_url):
            return True
        await asyncio.sleep(0.5)
    return False


def _spawn_service(py, script, cwd, name, health_url):
    if _service_up(health_url):
        print(f"[lifespan] {name} already running — reusing")
        return None
    if not py.exists() or not script.exists():
        print(f"[lifespan] {name} files missing at {cwd} — skipping")
        return None
    print(f"[lifespan] starting {name} ...")
    return subprocess.Popen(
        [str(py), str(script)], cwd=str(cwd),
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1,
    )


def _drain_logs(proc, prefix):
    def _reader():
        try:
            for line in proc.stdout:
                print(f"{prefix} {line.rstrip()}")
        except Exception:
            pass
    import threading
    threading.Thread(target=_reader, daemon=True).start()


def _stop(proc, name):
    if proc is None:
        return
    print(f"[lifespan] stopping {name} ...")
    try:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Module-level singletons
# ---------------------------------------------------------------------------
MAX_UPLOAD_BYTES = 10 * 1024 * 1024
ALLOWED_MIME = {"image/jpeg", "image/png", "image/webp"}
GLOBAL_BROADCAST_THRESHOLD = 70

ocr = OCRService()
validator = ValidationService()
tampering = TamperingDetector()
face_verify = FaceVerificationService()
scorer = RiskScorer()
quality_gate = ImageQualityGate(ocr_probe=ocr.probe_confidence)
enhancer = EnhancementService(enabled=True)

_fabric_client = None

def get_fabric():
    global _fabric_client
    if _fabric_client is None:
        _fabric_client = FabricClient()
    return _fabric_client


# ---------------------------------------------------------------------------
# Lifespan
# ---------------------------------------------------------------------------
@asynccontextmanager
async def lifespan(_app: FastAPI):
    global _dewarp_proc, _esrgan_proc

    _dewarp_proc = _spawn_service(_DEWARP_PY, _DEWARP_SCRIPT, _DEWARP_DIR,
                                  "dewarp-svc", _DEWARP_HEALTH)
    if _dewarp_proc is not None:
        _drain_logs(_dewarp_proc, "[dewarp-svc]")

    _esrgan_proc = _spawn_service(_ESRGAN_PY, _ESRGAN_SCRIPT, _ESRGAN_DIR,
                                  "esrgan-svc", _ESRGAN_HEALTH)
    if _esrgan_proc is not None:
        _drain_logs(_esrgan_proc, "[esrgan-svc]")

    ok_d = await _wait_for_service(_DEWARP_HEALTH, timeout_s=90.0)
    ok_e = await _wait_for_service(_ESRGAN_HEALTH, timeout_s=60.0)
    print(f"[lifespan] dewarp-svc healthy={ok_d}  esrgan-svc healthy={ok_e}")

    _app.state.qg_cache = {}

    # ---- Step 4 — reusable pipeline -----------------------------------
    _app.state.pipeline = DocumentPipeline(
        quality_gate=quality_gate,
        enhancer=enhancer,
        ocr=ocr,
        validator=validator,
        tampering=tampering,
        face_verify=face_verify,
        scorer=scorer,
        get_fabric=get_fabric,
        qg_cache=_app.state.qg_cache,
        enhancer_cache_dir=ENHANCER_CACHE_DIR,
        global_broadcast_threshold=GLOBAL_BROADCAST_THRESHOLD,
    )

    try:
        await redis_client.connect()
        print("[lifespan] Redis connected")
    except Exception as e:
        print(f"[lifespan] Redis unavailable: {e}. /liveness/* will fail until it's up.")

    yield

    _stop(_dewarp_proc, "dewarp-svc")
    _stop(_esrgan_proc, "esrgan-svc")
    try:
        await redis_client.disconnect()
    except Exception:
        pass


app = FastAPI(title="AI Border Screening API", version="3.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], allow_credentials=False,
    allow_methods=["*"], allow_headers=["*"],
)

app.include_router(liveness.router)
app.include_router(documents_router) 
app.include_router(screening_router)
app.include_router(history_router)


# ---------------------------------------------------------------------------
# Shared upload validator
# ---------------------------------------------------------------------------
async def _read_upload(upload: UploadFile, label: str) -> bytes:
    if upload.content_type not in ALLOWED_MIME:
        raise HTTPException(status_code=415,
            detail=f"{label}: unsupported content type {upload.content_type!r}")
    data = await upload.read()
    if not data:
        raise HTTPException(status_code=400, detail=f"{label}: empty file")
    if len(data) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413,
            detail=f"{label}: exceeds {MAX_UPLOAD_BYTES} bytes")
    return data


# ---------------------------------------------------------------------------
# Legacy endpoint
# ---------------------------------------------------------------------------
@app.post("/api/v2/screen", deprecated=True)
async def screen_traveler(
    document: UploadFile = File(...),
    live_photo: UploadFile = File(...),
):
    doc_bytes  = await _read_upload(document, "document")
    live_bytes = await _read_upload(live_photo, "live_photo")

    pipeline: DocumentPipeline = app.state.pipeline
    return await pipeline.run_document(
        doc_bytes=doc_bytes,
        filename=document.filename or "document.jpg",
        live_bytes=live_bytes,
    )


@app.get("/health")
def health():
    return {"status": "operational", "version": "3.0.0"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)