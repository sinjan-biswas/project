import os
from pathlib import Path
from typing import List

from fastapi import APIRouter, File, UploadFile, HTTPException, Body
from fastapi.responses import FileResponse

from app.core.session_store import screening_session_store
from app.schemas.session import SessionFileMeta

router = APIRouter(prefix="/api/v2/documents", tags=["documents"])

ALLOWED_MIME = {"image/jpeg", "image/png", "image/webp"}
MAX_FILE_BYTES = 15 * 1024 * 1024
MAX_FILES = 10
DOC_CONFIDENCE_FLOOR = 0.60


def _get_pipeline():
    """Lazy import to avoid circular import at module load."""
    from main import app as _app
    return _app.state.pipeline


def _unpack_classifier_output(out):
    """
    DocumentClassifier.classify returns:
        {"document_type": str, "confidence": float, "top_k": [...]}
    Handle that shape, plus a couple of fallbacks.
    """
    if out is None:
        return None, 0.0
    if isinstance(out, dict):
        dt = out.get("document_type") or out.get("label") or out.get("class")
        conf = out.get("confidence")
        if conf is None:
            conf = out.get("prob", 0.0)
        return dt, float(conf or 0.0)
    if isinstance(out, (tuple, list)) and len(out) >= 2:
        return out[0], float(out[1])
    return str(out), 0.0


def _extract_mrz(ocr_data: dict):
    """
    Best-effort MRZ extraction.
    Prefers ocr_data['mrz'] if the OCR service provides it.
    Otherwise scans ocr_lines for '<'-heavy rows (typical MRZ filler).
    """
    mrz = ocr_data.get("mrz")
    if mrz:
        return mrz
    lines = ocr_data.get("ocr_lines") or []
    candidates = [
        ln for ln in lines
        if isinstance(ln, str) and ln.count("<") >= 4 and len(ln) >= 30
    ]
    if candidates:
        return {"raw": candidates}
    return None


# ---------------------------------------------------------------------------
# Stage 1 — upload + quality + enhancement + classification
# ---------------------------------------------------------------------------
@router.post("/validate")
async def validate_documents(files: List[UploadFile] = File(...)):
    """
    Stage 1 — enhancement + classification on N uploaded files.

    Returns a session_id used by Stage 2 (/documents/details)
    and Stage 3 (/liveness/verify).
    """
    if not (1 <= len(files) <= MAX_FILES):
        raise HTTPException(422, f"Upload 1–{MAX_FILES} files")

    pipeline = _get_pipeline()
    session = await screening_session_store.create()

    file_metas: List[SessionFileMeta] = []
    any_blocked = False

    for i, upload in enumerate(files):
        # ---- validate MIME + size ----
        if upload.content_type not in ALLOWED_MIME:
            raise HTTPException(415, f"{upload.filename}: unsupported type {upload.content_type!r}")
        data = await upload.read()
        if not data:
            raise HTTPException(400, f"{upload.filename}: empty file")
        if len(data) > MAX_FILE_BYTES:
            raise HTTPException(413, f"{upload.filename}: exceeds 15MB")

        suffix = Path(upload.filename or f"file_{i}.jpg").suffix or ".jpg"
        disk_path = screening_session_store.write_file(session.session_id, i, suffix, data)

        # ---- Layer 1: quality gate ----
        quality = pipeline.quality_gate.assess(data)

        # ---- Layer 2: enhancement (only if needed) ----
        enhanced_path = None
        was_enhanced = False
        enhanced_bytes = data
        if quality["decision"] == "enhance":
            try:
                enhanced_bytes, was_enhanced = await pipeline.enhancer.enhance(data, quality)
                if was_enhanced:
                    enhanced_path = screening_session_store.write_enhanced(
                        session.session_id, i, enhanced_bytes)
                    # reassess on enhanced image
                    quality = pipeline.quality_gate.assess(enhanced_bytes)
            except Exception as e:
                print(f"[stage1] enhancement failed for {upload.filename}: {e}")
                enhanced_bytes = data
                was_enhanced = False

        # ---- Layer 2b: classification ----
        doc_type, doc_conf = None, 0.0
        if pipeline.doc_classifier is not None:
            try:
                import cv2
                import numpy as np
                img = cv2.imdecode(
                    np.frombuffer(enhanced_bytes, np.uint8),
                    cv2.IMREAD_COLOR,
                )
                out = pipeline.doc_classifier.classify(img)
                doc_type, doc_conf = _unpack_classifier_output(out)
            except Exception as e:
                print(f"[stage1] classify failed for {upload.filename}: {e}")

        # ---- blocking rules ----
        blocked = False
        block_reason = None
        if quality.get("decision") == "reject":
            blocked = True
            block_reason = "quality_rejected: " + "; ".join(quality.get("reasons", []))
        elif doc_conf < DOC_CONFIDENCE_FLOOR:
            blocked = True
            block_reason = f"low_confidence: {doc_conf:.2f} < {DOC_CONFIDENCE_FLOOR}"

        file_metas.append(SessionFileMeta(
            index=i,
            filename=upload.filename or f"file_{i}.jpg",
            disk_path=disk_path,
            enhanced_path=enhanced_path,
            quality=quality,
            doc_type=doc_type,
            doc_confidence=doc_conf,
            blocked=blocked,
            block_reason=block_reason,
        ))
        any_blocked = any_blocked or blocked

    session.files = file_metas
    session.stage = "validated"
    await screening_session_store.save(session)

    return {
        "session_id": session.session_id,
        "expires_at": session.expires_at,
        "blocked": any_blocked,
        "files": [
            {
                "index": f.index,
                "filename": f.filename,
                "quality": f.quality,
                "classification": {
                    "doc_type": f.doc_type,
                    "confidence": f.doc_confidence,
                },
                "enhanced": f.enhanced_path is not None,
                "preview_url": f"/api/v2/documents/preview/{session.session_id}/{f.index}",
                "blocked": f.blocked,
                "block_reason": f.block_reason,
            }
            for f in file_metas
        ],
    }


# ---------------------------------------------------------------------------
# Stage 1 helper — image preview
# ---------------------------------------------------------------------------
@router.get("/preview/{session_id}/{index}")
async def preview(session_id: str, index: int, enhanced: bool = True):
    """
    Return the original or enhanced image for a validated session file.
    Used by the frontend to render previews without re-uploading.
    """
    session = await screening_session_store.get(session_id)
    if not session:
        raise HTTPException(404, "session not found or expired")

    f = next((x for x in session.files if x.index == index), None)
    if not f:
        raise HTTPException(404, "file not in session")

    path = f.enhanced_path if (enhanced and f.enhanced_path) else f.disk_path
    if not os.path.exists(path):
        raise HTTPException(410, "backing file gone (session likely swept)")

    return FileResponse(path)


# ---------------------------------------------------------------------------
# Stage 2 — OCR + field extraction + MRZ + validation
# ---------------------------------------------------------------------------
@router.post("/details")
async def get_details(payload: dict = Body(...)):
    """
    Stage 2 — runs OCR + validation on the documents captured in Stage 1.

    Input:  {"session_id": "sess_..."}
    Output: per-document fields, MRZ, validation warnings.

    Persists results on the session so Stage 3 (/liveness/verify) can
    reuse them without a second OCR pass.
    """
    sid = payload.get("session_id")
    if not sid:
        raise HTTPException(422, "session_id is required")

    session = await screening_session_store.get(sid)
    if not session:
        raise HTTPException(404, "session not found or expired")

    if session.stage not in ("validated", "ocr_done"):
        raise HTTPException(409, f"invalid stage for details: {session.stage}")

    pipeline = _get_pipeline()
    documents = []

    for f in session.files:
        # ---- blocked at Stage 1: return the reason, skip OCR ----
        if f.blocked:
            documents.append({
                "index": f.index,
                "filename": f.filename,
                "doc_type": f.doc_type,
                "fields": None,
                "mrz": None,
                "validation": {
                    "valid": False,
                    "errors": [f.block_reason or "blocked at Stage 1"],
                    "warnings": [],
                },
                "ocr_failed": True,
            })
            continue

        # ---- read enhanced-or-original bytes ----
        path = f.enhanced_path or f.disk_path
        try:
            with open(path, "rb") as fh:
                data = fh.read()
        except OSError as e:
            documents.append({
                "index": f.index,
                "filename": f.filename,
                "doc_type": f.doc_type,
                "fields": None,
                "mrz": None,
                "validation": {
                    "valid": False,
                    "errors": [f"backing file unreadable: {e}"],
                    "warnings": [],
                },
                "ocr_failed": True,
            })
            continue

        # ---- OCR ----
        try:
            ocr_data = pipeline.ocr.extract(data)
        except Exception as e:
            ocr_data = {"success": False, "error": f"OCR exception: {e}"}

        ocr_failed = not ocr_data.get("success", False)

        # ---- Validation ----
        if ocr_failed:
            validation = {
                "valid": False,
                "errors": [f"OCR failed: {ocr_data.get('error', 'unknown')}"],
                "warnings": [],
            }
        else:
            try:
                validation = pipeline.validator.validate(ocr_data)
            except Exception as e:
                validation = {
                    "valid": False,
                    "errors": [f"validation exception: {e}"],
                    "warnings": [],
                }

        # ---- MRZ ----
        mrz = _extract_mrz(ocr_data) if not ocr_failed else None

        documents.append({
            "index": f.index,
            "filename": f.filename,
            "doc_type": ocr_data.get("document_type") or f.doc_type,
            "fields": ocr_data.get("fields") or {},
            "mrz": mrz,
            "validation": validation,
            "ocr_failed": ocr_failed,
        })

    # ---- persist on session, advance stage ----
    session.ocr_results = {"documents": documents}
    session.stage = "ocr_done"
    await screening_session_store.save(session)

    return {
        "session_id": sid,
        "documents": documents,
        "warnings": [
            w
            for d in documents
            for w in (d.get("validation") or {}).get("warnings", [])
        ],
    }