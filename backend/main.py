from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from datetime import datetime, timezone
from services.image_quality_service import ImageQualityGate
from services.enhancement_service import EnhancementService
import uuid
import tempfile
import os
import hashlib


from services.ocr_service import OCRService
from services.validation_service import ValidationService
from services.face_service import FaceVerificationService
from services.tampering_service import TamperingDetector
from risk_engine.scorer import RiskScorer
from blockchain.client import FabricClient

app = FastAPI(title="AI Border Screening API", version="2.2.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

MAX_UPLOAD_BYTES = 10 * 1024 * 1024
ALLOWED_MIME = {"image/jpeg", "image/png", "image/webp"}

# Set to 50 for testing the global broadcast, restore to 70 for production
GLOBAL_BROADCAST_THRESHOLD = 70

ocr = OCRService()
validator = ValidationService()
tampering = TamperingDetector()
face_verify = FaceVerificationService()
scorer = RiskScorer()
quality_gate = ImageQualityGate(ocr_probe=ocr.probe_confidence)
enhancer = EnhancementService(enabled=True)

# Lazy Fabric client (won't crash on import if network is down)
_fabric_client = None

def get_fabric():
    global _fabric_client
    if _fabric_client is None:
        _fabric_client = FabricClient()
    return _fabric_client


async def _read_upload(upload: UploadFile, label: str) -> bytes:
    if upload.content_type not in ALLOWED_MIME:
        raise HTTPException(
            status_code=415,
            detail=f"{label}: unsupported content type {upload.content_type!r}",
        )
    data = await upload.read()
    if not data:
        raise HTTPException(status_code=400, detail=f"{label}: empty file")
    if len(data) > MAX_UPLOAD_BYTES:
        raise HTTPException(
            status_code=413,
            detail=f"{label}: exceeds {MAX_UPLOAD_BYTES} bytes",
        )
    return data


@app.post("/api/v2/screen")
async def screen_traveler(
    document: UploadFile = File(...),
    live_photo: UploadFile = File(...),
):
    doc_bytes = await _read_upload(document, "document")
    live_bytes = await _read_upload(live_photo, "live_photo")

    # ---- Layer 1 – Quality Gate -------------------------------------
    quality = quality_gate.assess(doc_bytes)
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
        try:
            doc_bytes, was_enhanced = await enhancer.enhance(doc_bytes, quality)
        except Exception:
            raise HTTPException(status_code=422, detail={
                "error": "enhancement_failed",
                "fix_instructions": quality["reasons"],
            })
        quality = quality_gate.assess(doc_bytes)
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

    # ---- 3. Tampering ------------------------------------------------
    tampering_result = {
        "tampering_score": 0.0,
        "is_tampered": False,
        "risk_factors": [],
    }
    with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as tmp_file:
        tmp_file.write(doc_bytes)
        temp_path = tmp_file.name
    try:
        tampering_result = tampering.analyze(
            temp_path,
            ocr_lines=ocr_data.get("ocr_lines", []),
        )
    finally:
        try:
            os.unlink(temp_path)
        except OSError:
            pass

    # ---- 4. Face verification ----------------------------------------
    face_result = face_verify.verify(doc_bytes, live_bytes)

    # ---- 5. Risk scoring ---------------------------------------------
    is_expired = any("expired" in e.lower()
                     for e in validation.get("errors", []))
    risk = scorer.calculate(
        tampering_score=tampering_result.get("tampering_score", 0),
        face_distance=face_result.get("distance", 0),
        validation_errors=validation.get("errors", []),
        is_expired=is_expired,
        ocr_failed=ocr_failed,
        image_enhanced=was_enhanced,
        image_quality=quality["score"],
    )

    if ocr_failed and risk.get("decision") == "APPROVE":
        risk["decision"] = "SECONDARY_INSPECTION"
        risk.setdefault("reasons", []).append(
            "OCR unreadable — manual review required"
        )

    # ---- 6. Blockchain write (public + private PII) ------------------
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

        # Mirror high-risk screenings to global channel for cross-border alerting
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

    # ---- 7. Response -------------------------------------------------
    if os.getenv("DEBUG_OCR", "false").lower() != "true":
        ocr_data = {k: v for k, v in ocr_data.items() if k != "ocr_lines"}

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
    return {"status": "operational", "version": "2.2.0"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)