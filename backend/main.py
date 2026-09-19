from pathlib import Path
import os
import uuid
import tempfile
from datetime import datetime

from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from services.ocr_service import OCRService
from services.validation_service import ValidationService
from services.face_service import FaceVerificationService
from services.tampering_service import TamperingDetector
from risk_engine.scorer import RiskScorer


BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"
HEATMAP_DIR = STATIC_DIR / "heatmaps"
HEATMAP_DIR.mkdir(parents=True, exist_ok=True)   # ensure exists BEFORE mount

# 1. Create the app FIRST
app = FastAPI(title="AI Border Screening API", version="2.1.0")

# 2. Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 3. Mount static AFTER app exists and dir is guaranteed
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

# 4. Instantiate services (heavy models load once)
ocr = OCRService()
validator = ValidationService()
tampering = TamperingDetector()
face_verify = FaceVerificationService()
scorer = RiskScorer()


@app.post("/api/v2/screen")
async def screen_traveler(
    document: UploadFile = File(...),
    live_photo: UploadFile = File(...),
):
    doc_bytes = await document.read()
    live_bytes = await live_photo.read()

    # ---------------------------------------------------------------- #
    # 1. OCR — unified service (new pipeline with legacy fallback)
    # ---------------------------------------------------------------- #
    ocr_data = ocr.extract(doc_bytes)
    if not ocr_data.get("success"):
        raise HTTPException(
            status_code=400,
            detail=f"OCR failed: {ocr_data.get('error', 'unknown')}",
        )

    # ---------------------------------------------------------------- #
    # 2. Validation — new dispatcher (handles both old/new OCR output)
    # ---------------------------------------------------------------- #
    validation = validator.validate(ocr_data)

    # ---------------------------------------------------------------- #
    # 3. Tampering analysis on temp file
    # ---------------------------------------------------------------- #
    with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as tmp:
        tmp.write(doc_bytes)
        temp_path = tmp.name
    try:
        tampering_result = tampering.analyze(temp_path)
    finally:
        os.unlink(temp_path)

    # ---------------------------------------------------------------- #
    # 4. Face verification
    # ---------------------------------------------------------------- #
    face_result = face_verify.verify(doc_bytes, live_bytes)

    # ---------------------------------------------------------------- #
    # 5. Risk scoring (unchanged interface)
    # ---------------------------------------------------------------- #
    is_expired = any("expired" in e.lower() for e in validation["errors"])
    risk = scorer.calculate(
        tampering_score=tampering_result["tampering_score"],
        face_distance=face_result.get("distance", 0),
        validation_errors=validation["errors"],
        is_expired=is_expired,
    )

    # ---------------------------------------------------------------- #
    # 6. Response — strip heavy OCR lines unless DEBUG_OCR=true
    # ---------------------------------------------------------------- #
    include_ocr_lines = os.getenv("DEBUG_OCR", "false").lower() == "true"
    if not include_ocr_lines:
        ocr_data = {k: v for k, v in ocr_data.items() if k != "ocr_lines"}

    return {
        "screening_id": uuid.uuid4().hex[:16],
        "document_type": ocr_data.get("document_type"),
        "ocr_data": ocr_data,
        "validation": validation,
        "tampering": tampering_result,
        "biometrics": face_result,
        "risk_assessment": risk,
        "timestamp": datetime.now().isoformat(),
    }


@app.get("/health")
def health():
    return {"status": "operational", "version": "2.1.0"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)