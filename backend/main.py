from contextlib import asynccontextmanager
import asyncio
import subprocess
import sys
import time as _t
import urllib.error
import urllib.request
from pathlib import Path

from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from datetime import datetime, timezone
import uuid
import tempfile
import os
import hashlib

from services.image_quality_service import ImageQualityGate
from services.enhancement_service import EnhancementService, _CACHE_DIR as ENHANCER_CACHE_DIR
from services.ocr_service import OCRService
from services.validation_service import ValidationService
from services.face_service import FaceVerificationService
from services.tampering_service import TamperingDetector
from risk_engine.scorer import RiskScorer
from blockchain.client import FabricClient

from app.core.redis import redis_client
from app.routers import liveness


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


def _spawn_service(py: Path, script: Path, cwd: Path, name: str,
                   health_url: str) -> subprocess.Popen | None:
    if _service_up(health_url):
        print(f"[lifespan] {name} already running — reusing")
        return None
    if not py.exists() or not script.exists():
        print(f"[lifespan] {name} files missing at {cwd} — skipping")
        return None
    print(f"[lifespan] starting {name} ...")
    return subprocess.Popen(
        [str(py), str(script)],
        cwd=str(cwd),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
    )


def _drain_logs(proc: subprocess.Popen, prefix: str) -> None:
    def _reader():
        try:
            assert proc.stdout is not None
            for line in proc.stdout:
                print(f"{prefix} {line.rstrip()}")
        except Exception:
            pass
    import threading
    threading.Thread(target=_reader, daemon=True).start()


def _stop(proc: subprocess.Popen | None, name: str) -> None:
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


app = FastAPI(
    title="AI Border Screening API",
    version="3.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(liveness.router)


# ---------------- SCREENING ENDPOINT ---------------------

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


@app.post("/api/v2/screen")
async def screen_traveler(
    document: UploadFile = File(...),
    live_photo: UploadFile = File(...),
):
    _timings = {"start": _t.time()}
    def _mark(label):
        _timings[label] = _t.time()
        keys = list(_timings.keys())
        prev = keys[-2]
        print(f"[timing] {prev} → {label}: {_timings[label] - _timings[prev]:.2f}s")

    doc_bytes = await _read_upload(document, "document")
    live_bytes = await _read_upload(live_photo, "live_photo")
    _mark("upload")

    # ---- Layer 1 – Quality Gate (cached) ----------------------------
    qg_key = hashlib.sha256(doc_bytes).hexdigest()
    if qg_key in app.state.qg_cache:
        quality = app.state.qg_cache[qg_key]
        print("[timing] quality_gate: cache HIT")
    else:
        quality = quality_gate.assess(doc_bytes)
        app.state.qg_cache[qg_key] = quality
        _mark("quality_gate")

    if quality["decision"] == "reject":
        raise HTTPException(status_code=422, detail={
            "error": "image_quality_rejected",
            "quality_score": quality["score"],
            "metrics": quality["metrics"],
            "fix_instructions": quality["reasons"],
        })

    # ---- Layer 2 – Enhancement Retry --------------------------------
    was_enhanced = False
    if quality["decision"] == "enhance":
        pre_hash = hashlib.sha256(doc_bytes).hexdigest()
        enhancer_cache_hit = os.path.exists(
            os.path.join(ENHANCER_CACHE_DIR, pre_hash + ".pkl"))

        try:
            doc_bytes, was_enhanced = await enhancer.enhance(doc_bytes, quality)
            _mark("enhance")
        except Exception:
            raise HTTPException(status_code=422, detail={
                "error": "enhancement_failed",
                "fix_instructions": quality["reasons"],
            })

        new_hash = hashlib.sha256(doc_bytes).hexdigest()
        if enhancer_cache_hit and new_hash in app.state.qg_cache:
            quality = app.state.qg_cache[new_hash]
            print("[timing] quality_recheck: cache HIT")
        else:
            quality = quality_gate.assess(doc_bytes)
            app.state.qg_cache[new_hash] = quality
            _mark("quality_recheck")

        if quality["decision"] == "reject":
            raise HTTPException(status_code=422, detail={
                "error": "still_unreadable_after_enhancement",
                "fix_instructions": quality["reasons"],
            })

    # ---- 1. OCR ------------------------------------------------------
    try:
        ocr_data = ocr.extract(doc_bytes)
    except Exception as e:
        ocr_data = {"success": False, "error": f"OCR exception: {e}"}
    _mark("ocr")

    ocr_failed = not ocr_data.get("success", False)
    ocr_data["image_quality"] = quality["score"]
    ocr_data["image_enhanced"] = was_enhanced

    # ---- 2. Validation -----------------------------------------------
    if ocr_failed:
        validation = {
            "valid": False,
            "errors": [f"OCR failed: {ocr_data.get('error', 'unknown')}"],
            "document_type": ocr_data.get("document_type"),
            "expiry_date": None,
        }
    else:
        validation = validator.validate(ocr_data)
    _mark("validation")

    # ---- 3. Tampering ------------------------------------------------
    tampering_result = {"tampering_score": 0.0, "is_tampered": False, "risk_factors": []}
    with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as tmp_file:
        tmp_file.write(doc_bytes)
        temp_path = tmp_file.name
    try:
        tampering_result = tampering.analyze(
            temp_path, ocr_lines=ocr_data.get("ocr_lines", []))
    finally:
        try:
            os.unlink(temp_path)
        except OSError:
            pass
    _mark("tampering")

    # ---- 4. Face verification ----------------------------------------
    face_result = face_verify.verify(doc_bytes, live_bytes)
    _mark("face_verify")

    # ---- 5. Risk scoring ---------------------------------------------
    is_expired = any("expired" in e.lower() for e in validation.get("errors", []))
    risk = scorer.calculate(
        tampering_score=tampering_result.get("tampering_score", 0),
        face_distance=face_result.get("distance", 0),
        validation_errors=validation.get("errors", []),
        is_expired=is_expired,
        ocr_failed=ocr_failed,
        image_enhanced=was_enhanced,
        image_quality=quality["score"],
    )
    _mark("risk")

    if ocr_failed and risk.get("decision") == "APPROVE":
        risk["decision"] = "SECONDARY_INSPECTION"
        risk.setdefault("reasons", []).append("OCR unreadable — manual review required")

    # ---- 6. Blockchain -----------------------------------------------
    screening_id = uuid.uuid4().hex[:16]
    blockchain_ok = False
    blockchain_error = None
    global_broadcast_ok = False

    try:
        fabric = get_fabric()
        ocr_fields = (ocr_data.get("fields") or {})
        passport_number = str(ocr_fields.get("passport_number", "unknown"))
        passport_hash = hashlib.sha256(passport_number.encode()).hexdigest()

        fabric.record_screening(
            screening={
                "screening_id": screening_id,
                "document_hash": hashlib.sha256(doc_bytes).hexdigest(),
                "passport_hash": passport_hash,
                "risk_score": float(risk.get("score", 0)),
                "decision": str(risk.get("decision", "UNKNOWN")),
                "checkpoint_id": "JFK_01",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "agent_signature": "",
            },
            pii={
                "screening_id": screening_id,
                "name": str(ocr_fields.get("name", "")),
                "father_name": str(ocr_fields.get("father_name", "")),
                "passport_number": passport_number,
                "date_of_birth": str(ocr_fields.get("date_of_birth", "")),
            },
        )
        blockchain_ok = True

        if float(risk.get("score", 0)) > GLOBAL_BROADCAST_THRESHOLD:
            try:
                fabric.broadcast_alert({
                    "screening_id": screening_id + "_global",
                    "document_hash": hashlib.sha256(doc_bytes).hexdigest(),
                    "passport_hash": passport_hash,
                    "risk_score": float(risk.get("score", 0)),
                    "decision": str(risk.get("decision", "DENY")),
                    "checkpoint_id": "JFK_01",
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "agent_signature": "",
                })
                global_broadcast_ok = True
            except Exception as e:
                print(f"global broadcast failed: {e}")
    except Exception as e:
        blockchain_error = str(e)
    _mark("blockchain")

    if os.getenv("DEBUG_OCR", "false").lower() != "true":
        ocr_data = {k: v for k, v in ocr_data.items() if k != "ocr_lines"}

    total = _t.time() - _timings["start"]
    print(f"[timing] ===== TOTAL: {total:.2f}s =====")

    return {
        "screening_id": screening_id,
        "document_type": ocr_data.get("document_type"),
        "ocr_data": ocr_data,
        "validation": validation,
        "tampering": tampering_result,
        "biometrics": face_result,
        "risk_assessment": risk,
        "blockchain": {
            "screening_id": screening_id,
            "recorded": blockchain_ok,
            "pii_stored_privately": blockchain_ok,
            "global_broadcast": global_broadcast_ok,
            **({"error": blockchain_error} if blockchain_error else {}),
        },
        "timestamp": datetime.now().isoformat(),
    }


@app.get("/health")
def health():
    return {"status": "operational", "version": "3.0.0"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)