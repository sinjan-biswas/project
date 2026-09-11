from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from datetime import datetime
import uuid
import tempfile
import os

from services.ocr_service import OCRService
from services.validation_service import ValidationService
from services.face_service import FaceVerificationService
from services.tampering_service import TamperingDetector
from services.document_classifier import DocumentClassifier
from services.document_parsers import DocumentParserRouter
from risk_engine.scorer import RiskScorer

app = FastAPI(title="AI Border Screening API", version="2.2.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

ocr = OCRService()
validator = ValidationService()
tampering = TamperingDetector()
face_verify = FaceVerificationService()
doc_classifier = DocumentClassifier()
doc_parsers = DocumentParserRouter()
scorer = RiskScorer()


# Fields whose presence actually counts as identity evidence.
# Used by _has_identity_fields() to distinguish "dict with keys but all
# None" from "dict with at least one real value".
IDENTITY_FIELD_KEYS = {
    "document_number", "aadhaar_number", "pan_number",
    "epic_number", "license_number", "visa_number",
    "surname", "given_names", "name",
    "date_of_birth", "date_of_expiry", "validity",
}


def _is_truthy_mrz(mrz_data: dict) -> bool:
    """A structured MRZ was actually parsed, with a real document number."""
    return (
        bool(mrz_data.get("mrz_parsed"))
        and bool(mrz_data.get("document_number"))
        and mrz_data.get("document_number") != "UNKNOWN"
    )


def _has_identity_fields(fields: dict | None) -> bool:
    """True only if at least one identity-relevant field has a real value.

    A dict like {"aadhaar_number": None, "name": None} is truthy but
    carries no identity information — this distinguishes the two cases.
    """
    if not fields:
        return False
    for key in IDENTITY_FIELD_KEYS:
        v = fields.get(key)
        if isinstance(v, dict):  # e.g. date_of_birth = {"iso": ..., "raw": ...}
            v = v.get("iso") or v.get("raw")
        if v not in (None, "", "UNKNOWN", False):
            return True
    return False


@app.post("/api/v2/screen")
async def screen_traveler(
    document: UploadFile = File(...),
    live_photo: UploadFile = File(...)
):
    doc_bytes = await document.read()
    live_bytes = await live_photo.read()

    # 1) Classify document type (CNN, gated on confidence)
    classification = doc_classifier.classify(doc_bytes)
    doc_type = classification["document_type"]

    # 2) OCR raw text — always run, always keep the raw text
    mrz_data = ocr.extract(doc_bytes)
    raw_text = mrz_data.get("raw_text", "") or ""
    mrz_trustworthy = _is_truthy_mrz(mrz_data)

    # 3) Template-specific parse of the raw text
    parsed = doc_parsers.parse(doc_type, raw_text)

    # 4) Validation:
    #    - If the MRZ parse is trustworthy, validate on it.
    #    - Otherwise validate on the template parser's fields, so Aadhaar/
    #      PAN/Voter/DL and unknown docs don't inherit fabricated MRZ values.
    if mrz_trustworthy:
        validation = validator.validate_mrz(mrz_data)
        validation["source"] = "mrz"
    else:
        validation = _validate_from_parsed(parsed)
        validation["source"] = "template_parser" if parsed.get("fields") else "none"

    # 5) Tampering analysis
    with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as tmp:
        tmp.write(doc_bytes)
        temp_path = tmp.name
    try:
        tampering_result = tampering.analyze(temp_path)
    finally:
        os.unlink(temp_path)

    # 6) Face verification
    face_result = face_verify.verify(doc_bytes, live_bytes)

    # 7) Risk scoring — pass classification + parsing context so the scorer
    #    can apply hard overrides for unidentifiable documents (Bugs G & H).
    is_expired = any("expired" in e.lower() for e in validation["errors"])
    risk = scorer.calculate(
        tampering_score=tampering_result["tampering_score"],
        face_distance=face_result.get("distance", 0),
        validation_errors=validation["errors"],
        is_expired=is_expired,
        document_type=doc_type,
        classification_confidence=classification.get("confidence"),
        validation_source=validation.get("source"),
        has_identity_fields=_has_identity_fields(parsed.get("fields")),
    )

    return {
        "screening_id": uuid.uuid4().hex[:16],
        "document_classification": classification,
        "document": parsed,
        "ocr_data": _sanitize_ocr_for_response(mrz_data, mrz_trustworthy),
        "validation": validation,
        "tampering": tampering_result,
        "biometrics": face_result,
        "risk_assessment": risk,
        "override_reason": risk.get("override_reason"),
        "timestamp": datetime.now().isoformat(),
    }


def _validate_from_parsed(parsed: dict):
    """Minimal validator for non-MRZ / unknown documents.

    Checks the parsed template fields for presence + expiry. No fake
    date_of_expiry → no phantom 'expired' error.
    """
    fields = parsed.get("fields") or {}
    errors = []

    doc_num = (fields.get("document_number") or fields.get("aadhaar_number")
               or fields.get("pan_number") or fields.get("epic_number")
               or fields.get("license_number"))
    if not doc_num:
        errors.append("Missing document number")

    dob = fields.get("date_of_birth")
    if isinstance(dob, dict):
        dob = dob.get("iso")
    if not dob:
        errors.append("Missing date of birth")

    expiry = fields.get("date_of_expiry")
    if isinstance(expiry, dict):
        expiry = expiry.get("iso")
    expiry_str = None
    if expiry:
        expiry_str = str(expiry)
        try:
            for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y"):
                try:
                    dt = datetime.strptime(expiry_str, fmt)
                    if dt < datetime.now():
                        errors.append("Document expired")
                    break
                except ValueError:
                    continue
        except Exception:
            pass

    return {
        "valid": len(errors) == 0,
        "errors": errors,
        "expiry_date": expiry_str,
        "source": "template_parser",
    }


def _sanitize_ocr_for_response(mrz_data: dict, trustworthy: bool):
    """Return the OCR dict as-is if the MRZ parse was real; otherwise
    strip every field so downstream consumers can't trust fabricated values."""
    if trustworthy:
        return mrz_data
    return {
        "success": bool(mrz_data.get("success")),
        "raw_text": mrz_data.get("raw_text", ""),
        "engine": mrz_data.get("engine"),
        "error": mrz_data.get("error"),
        "mrz_parsed": False,
        "mrz_type": None,
        "mrz_line": None,
        "document_type": None,
        "country_code": None,
        "surname": None,
        "given_names": None,
        "document_number": None,
        "nationality": None,
        "date_of_birth": None,
        "sex": None,
        "date_of_expiry": None,
        "trustworthy": False,
    }


@app.get("/health")
def health():
    return {"status": "operational", "version": "2.2.0"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)