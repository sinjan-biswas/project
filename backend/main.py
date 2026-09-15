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
app = FastAPI(title="AI Border Screening API", version="2.0.0")

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

    mrz_data = ocr.extract(doc_bytes)
    if not mrz_data.get("success"):
        raise HTTPException(status_code=400, detail=f"OCR failed: {mrz_data.get('error')}")

    validation = validator.validate_mrz(mrz_data)

    # Tampering analysis on temp file
    with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as tmp:
        tmp.write(doc_bytes)
        temp_path = tmp.name
    try:
        tampering_result = tampering.analyze(temp_path)
    finally:
        os.unlink(temp_path)

    face_result = face_verify.verify(doc_bytes, live_bytes)

    is_expired = any("expired" in e.lower() for e in validation["errors"])
    risk = scorer.calculate(
        tampering_score=tampering_result["tampering_score"],
        face_distance=face_result.get("distance", 0),
        validation_errors=validation["errors"],
        is_expired=is_expired,
    )

    return {
        "screening_id": uuid.uuid4().hex[:16],
        "ocr_data": mrz_data,
        "validation": validation,
        "tampering": tampering_result,
        "biometrics": face_result,
        "risk_assessment": risk,
        "timestamp": datetime.now().isoformat(),
    }


@app.get("/health")
def health():
    return {"status": "operational", "version": "2.0.0"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)