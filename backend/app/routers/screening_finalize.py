"""
Stage 3 — final consolidation.

Reads the screening session (Stage 1 + 2 outputs) and the liveness session
(blink + PAD + face-match, already computed by app/routers/liveness.py),
runs tampering + risk scoring + blockchain, and returns one unified response.
"""
import hashlib
import tempfile
import os
import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Body, HTTPException, UploadFile, File, Depends
from redis.asyncio import Redis

from app.core.session_store import screening_session_store
from app.core.session import SessionStore as LivenessSessionStore
from app.dependencies import get_redis

router = APIRouter(prefix="/api/v2/screening", tags=["screening"])


def _get_pipeline():
    from main import app as _app
    return _app.state.pipeline


def _pick_primary_doc(session):
    """Return the first non-blocked file; else the first file."""
    for f in session.files:
        if not f.blocked:
            return f
    return session.files[0] if session.files else None


# ---------------------------------------------------------------------------
# Start a liveness session using a doc already stored in the screening session
# ---------------------------------------------------------------------------
@router.post("/start-liveness")
async def start_liveness(
    payload: dict = Body(...),
    redis: Redis = Depends(get_redis),
):
    """
    Input:  {"session_id": "sess_...", "doc_index": 0 (optional)}
    Output: {"liveness_session_id": "...", "blink_target": N, "doc_index": 0}

    Reads the enhanced (or original) doc bytes from the screening session
    and creates a liveness session on the caller's behalf, so the frontend
    doesn't have to round-trip the image bytes.
    """
    sid = payload.get("session_id")
    if not sid:
        raise HTTPException(422, "session_id is required")

    session = await screening_session_store.get(sid)
    if not session:
        raise HTTPException(404, "screening session not found or expired")
    if session.stage not in ("validated", "ocr_done"):
        raise HTTPException(409, f"invalid stage: {session.stage}")

    # choose doc
    wanted = payload.get("doc_index")
    if wanted is not None:
        f = next((x for x in session.files if x.index == wanted), None)
        if not f:
            raise HTTPException(404, f"doc_index {wanted} not in session")
    else:
        f = _pick_primary_doc(session)
    if not f:
        raise HTTPException(422, "no documents in session")

    # read bytes, call the liveness router's create_session logic directly
    path = f.enhanced_path or f.disk_path
    try:
        with open(path, "rb") as fh:
            doc_bytes = fh.read()
    except OSError as e:
        raise HTTPException(500, f"cannot read doc bytes: {e}")

    # reuse the same logic the /liveness/session endpoint uses:
    # create a Session, store it, return id + blink target.
    from app.models.session import Session
    from app.config import settings
    from datetime import timedelta
    import base64

    b64 = base64.b64encode(doc_bytes).decode("utf-8")
    liveness_sid = str(uuid.uuid4())
    blink_target = settings.BLINK_TARGET_MIN + (
        uuid.uuid4().int % (settings.BLINK_TARGET_MAX - settings.BLINK_TARGET_MIN + 1)
    )
    live_session = Session(
        session_id=liveness_sid,
        document_photo_b64=b64,
        blink_target=blink_target,
        challenge_started_at=datetime.utcnow(),
        challenge_deadline=datetime.utcnow() + timedelta(seconds=settings.SESSION_TTL_SECONDS),
    )
    await LivenessSessionStore(redis).create(live_session)

    return {
        "liveness_session_id": liveness_sid,
        "blink_target": blink_target,
        "doc_index": f.index,
        "screening_session_id": sid,
    }


# ---------------------------------------------------------------------------
# Final consolidation
# ---------------------------------------------------------------------------
@router.post("/finalize")
async def finalize(
    payload: dict = Body(...),
    redis: Redis = Depends(get_redis),
):
    """
    Input:  {"screening_session_id": "sess_...", "liveness_session_id": "uuid"}
    Output: consolidated result — liveness + face + tampering + risk + blockchain.

    Prereqs: screening session must be at stage 'ocr_done' (Stage 2 done),
             liveness session must be 'verified' (all three checks passed).
    """
    scr_sid = payload.get("screening_session_id")
    live_sid = payload.get("liveness_session_id")
    if not scr_sid or not live_sid:
        raise HTTPException(422, "both screening_session_id and liveness_session_id required")

    screening = await screening_session_store.get(scr_sid)
    if not screening:
        raise HTTPException(404, "screening session not found or expired")
    if screening.stage != "ocr_done":
        raise HTTPException(409, f"screening stage must be 'ocr_done' (got '{screening.stage}')")

    liveness = None
    last_err = None
    for attempt in range(3):
        try:
            liveness = await LivenessSessionStore(redis).get(live_sid)
            break
        except Exception as e:
            last_err = e
            print(f"[finalize] liveness read attempt {attempt + 1}/3 failed: {e}")
            await asyncio.sleep(0.25 * (attempt + 1))  # 250ms, 500ms, 750ms

    if liveness is None and last_err is not None:
        raise HTTPException(
            503,
            f"liveness session read timed out after 3 attempts: {last_err}",
        )
    if not liveness:
        raise HTTPException(404, "liveness session not found or expired")

    # liveness must be verified (or at least have all three checks passing)
    blink_ok = liveness.blink_count >= liveness.blink_target
    anti_ok = bool(liveness.anti_spoof_result and liveness.anti_spoof_result.passed)
    match_ok = bool(liveness.face_match_result and liveness.face_match_result.passed)
    verified = blink_ok and anti_ok and match_ok

    pipeline = _get_pipeline()

    # ---------- tampering across all non-blocked docs ----------
    tampering_results = []
    worst_tampering = 0.0
    for f in screening.files:
        if f.blocked:
            continue
        path = f.enhanced_path or f.disk_path
        try:
            with open(path, "rb") as fh:
                doc_bytes = fh.read()
        except OSError:
            continue
        with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as tmp:
            tmp.write(doc_bytes)
            tmp_path = tmp.name
        try:
            tr = pipeline.tampering.analyze(tmp_path, ocr_lines=[])
        finally:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass
        tampering_results.append({"index": f.index, **tr})
        worst_tampering = max(worst_tampering, tr.get("tampering_score", 0.0))

    # ---------- pull validation signals from Stage 2 ----------
    val_errors = []
    expired = False
    for d in (screening.ocr_results or {}).get("documents", []):
        errs = (d.get("validation") or {}).get("errors") or []
        val_errors.extend(errs)
        if any("expired" in e.lower() for e in errs):
            expired = True

    ocr_failed = any(
        d.get("ocr_failed") for d in (screening.ocr_results or {}).get("documents", [])
    )
    image_quality = min(
        (f.quality.get("score", 100.0) for f in screening.files if not f.blocked),
        default=100.0,
    )
    was_enhanced = any(f.enhanced_path for f in screening.files)

    # ---------- risk scoring ----------
    face_distance = 1.0
    if liveness.face_match_result:
        face_distance = float(liveness.face_match_result.distance)

    risk = pipeline.scorer.calculate(
        tampering_score=worst_tampering,
        face_distance=face_distance,
        validation_errors=val_errors,
        is_expired=expired,
        ocr_failed=ocr_failed,
        image_enhanced=was_enhanced,
        image_quality=image_quality,
    )

    # If liveness didn't fully pass, cap the decision at SECONDARY (never APPROVE).
    stopped_early = not verified
    if stopped_early and risk.get("decision") == "APPROVE":
        risk["decision"] = "SECONDARY_INSPECTION"
        risk.setdefault("reasons", []).append(
            "Liveness / face match incomplete — manual review required"
        )

    # ---------- blockchain ----------
    screening_id = uuid.uuid4().hex[:16]
    blockchain_ok = False
    blockchain_error = None
    try:
        fabric = pipeline.get_fabric()
        primary = _pick_primary_doc(screening)
        doc_hash = ""
        if primary:
            with open(primary.disk_path, "rb") as fh:
                doc_hash = hashlib.sha256(fh.read()).hexdigest()

        fabric.record_screening(
            screening={
                "screening_id": screening_id,
                "document_hash": doc_hash,
                "passport_hash": hashlib.sha256(b"").hexdigest(),
                "risk_score": float(risk.get("score", 0)),
                "decision": str(risk.get("decision", "UNKNOWN")),
                "checkpoint_id": "JFK_01",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "agent_signature": "",
            },
            pii={"screening_id": screening_id, "name": "", "father_name": "",
                 "passport_number": "", "date_of_birth": ""},
        )
        blockchain_ok = True
    except Exception as e:
        blockchain_error = str(e)
        print(f"[finalize] blockchain error: {e}")

    # ---------- consolidated response ----------
    final = {
        "screening_session_id": scr_sid,
        "liveness_session_id": live_sid,
        "stopped_early": stopped_early,
        "liveness": {
            "blink_count": liveness.blink_count,
            "blink_target": liveness.blink_target,
            "ear_history": liveness.ear_history[-20:],
            "anti_spoof": (
                {"passed": liveness.anti_spoof_result.passed,
                 "label": liveness.anti_spoof_result.label,
                 "score": liveness.anti_spoof_result.score}
                if liveness.anti_spoof_result else None
            ),
            "face_match": (
                {"passed": liveness.face_match_result.passed,
                 "distance": liveness.face_match_result.distance}
                if liveness.face_match_result else None
            ),
            "state": liveness.state,
            "failure_reason": liveness.failure_reason,
        },
        "tampering": tampering_results,
        "validation_summary": {
            "expired": expired,
            "ocr_failed": ocr_failed,
            "errors": val_errors,
            "image_quality": image_quality,
        },
        "risk_assessment": risk,
        "blockchain": {
            "screening_id": screening_id,
            "recorded": blockchain_ok,
            **({"error": blockchain_error} if blockchain_error else {}),
        },
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }

    screening.final_result = final
    screening.stage = "final"
    await screening_session_store.save(screening)

    return final


# ---------------------------------------------------------------------------
# Session state reader (for resume)
# ---------------------------------------------------------------------------
@router.get("/{sid}/state")
async def session_state(sid: str):
    """Return the full state of a screening session — used by the frontend
    to resume a wizard after tab close / refresh."""
    session = await screening_session_store.get(sid)
    if not session:
        raise HTTPException(404, "session not found or expired")
    return {
        "session_id": session.session_id,
        "stage": session.stage,
        "expires_at": session.expires_at,
        "files": [f.model_dump() for f in session.files],
        "ocr_results": session.ocr_results,
        "final_result": session.final_result,
    }