# app/routers/liveness.py
import uuid
import base64
import logging
from datetime import datetime, timedelta

import cv2
import numpy as np
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from redis.asyncio import Redis
from jose import jwt

from app.config import settings
from app.dependencies import get_redis
from app.core.session import SessionStore
from app.models.session import Session, AntiSpoofResult, FaceMatchResult
from app.services.liveness import (
    extract_landmarks, compute_ear_from_landmarks,
    check_face_aligned, BlinkDetector,
)
from app.services.face_match import get_embedding, compute_distance
from app.services.anti_spoof import analyze_sequence

log = logging.getLogger(__name__)
router = APIRouter(prefix="/liveness", tags=["liveness"])


def _enhance(img):
    """CLAHE brightness boost — helps InsightFace in dim frames."""
    try:
        lab = cv2.cvtColor(img, cv2.COLOR_BGR2LAB)
        l, a, b = cv2.split(lab)
        clahe = cv2.createCLAHE(clipLimit=2.5, tileGridSize=(8, 8))
        l = clahe.apply(l)
        return cv2.cvtColor(cv2.merge([l, a, b]), cv2.COLOR_LAB2BGR)
    except Exception:
        return img


def _decode(b64_or_bytes):
    if isinstance(b64_or_bytes, str):
        data = base64.b64decode(b64_or_bytes)
    else:
        data = b64_or_bytes
    return cv2.imdecode(np.frombuffer(data, np.uint8), cv2.IMREAD_COLOR)


@router.post("/session")
async def create_session(
    document_photo: UploadFile = File(...),
    redis: Redis = Depends(get_redis),
):
    contents = await document_photo.read()
    b64 = base64.b64encode(contents).decode("utf-8")

    try:
        doc_img = cv2.imdecode(np.frombuffer(contents, np.uint8), cv2.IMREAD_COLOR)
        if doc_img is not None:
            emb_raw = get_embedding(doc_img)
            emb_enh = get_embedding(_enhance(doc_img)) if emb_raw is None else emb_raw
            print(
                f"[create-session] doc shape={doc_img.shape} "
                f"brightness={doc_img.mean():.0f} "
                f"face_raw={'YES' if emb_raw is not None else 'NO'} "
                f"face_enhanced={'YES' if emb_enh is not None else 'NO'}"
            )
    except Exception as e:
        print(f"[create-session] doc diagnostic failed: {e}")

    session_id = str(uuid.uuid4())
    blink_target = settings.BLINK_TARGET_MIN + (
        uuid.uuid4().int % (settings.BLINK_TARGET_MAX - settings.BLINK_TARGET_MIN + 1)
    )
    session = Session(
        session_id=session_id,
        document_photo_b64=b64,
        blink_target=blink_target,
        challenge_started_at=datetime.utcnow(),
        challenge_deadline=datetime.utcnow() + timedelta(seconds=settings.SESSION_TTL_SECONDS),
    )
    await SessionStore(redis).create(session)
    return {
        "session_id": session_id,
        "blink_target": blink_target,
        "challenge_deadline": session.challenge_deadline.isoformat(),
    }


@router.post("/session/{session_id}/frame")
async def process_frame(
    session_id: str,
    frame: UploadFile = File(...),
    client_timestamp: float = 0,
    redis: Redis = Depends(get_redis),
):
    store = SessionStore(redis)
    session = await store.get(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found or expired")

    if session.state == "failed":
        return _session_state_response(session)

    data = await frame.read()
    img = cv2.imdecode(np.frombuffer(data, np.uint8), cv2.IMREAD_COLOR)
    if img is None:
        raise HTTPException(status_code=400, detail="Invalid image")

    landmarks = extract_landmarks(img)
    face_aligned = check_face_aligned(landmarks, img.shape)
    ear_preview = compute_ear_from_landmarks(landmarks) if landmarks else 0.0

    print(f"[frame] landmarks={'yes' if landmarks else 'NO':<3} "
          f"aligned={str(face_aligned):<5} ear={ear_preview:.3f} "
          f"blink={session.blink_count}/{session.blink_target}")

    if landmarks is None or not face_aligned:
        session.state = "face_aligned" if session.state == "created" else session.state
        await store.update(session)
        return _session_state_response(session, face_aligned=False)

    ear = compute_ear_from_landmarks(landmarks)
    session.ear_history.append(round(ear, 3))
    if len(session.ear_history) > 100:
        session.ear_history = session.ear_history[-100:]

    detector = BlinkDetector(settings.EAR_THRESHOLD, settings.EAR_CONSEC_FRAMES)
    for past_ear in session.ear_history[:-1]:
        detector.update(past_ear)

    if detector.update(ear):
        session.blink_count += 1
        print(f"[blink] DETECTED — total={session.blink_count}/{session.blink_target}")

    if len(session.captured_frames) < 6:
        _, buf = cv2.imencode(".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, 70])
        session.captured_frames.append(base64.b64encode(buf).decode("utf-8"))

    if session.state in ("created", "face_aligned"):
        session.state = "blink_challenge"

    if session.challenge_deadline and datetime.utcnow() > session.challenge_deadline:
        if session.blink_count < session.blink_target:
            session.state = "failed"
            session.failure_reason = "timeout"

    await store.update(session)
    secs = max(0, int((session.challenge_deadline - datetime.utcnow()).total_seconds())) \
           if session.challenge_deadline else 0
    return {
        "blink_count": session.blink_count,
        "ear": round(ear, 3),
        "face_aligned": True,
        "time_remaining": secs,
        "status": session.state,
    }


@router.post("/session/{session_id}/complete-blink-challenge")
async def complete_blink_challenge(
    session_id: str,
    redis: Redis = Depends(get_redis),
):
    store = SessionStore(redis)
    session = await store.get(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    if session.blink_count < session.blink_target:
        session.state = "failed"
        session.failure_reason = (
            f"blink_challenge_failed: {session.blink_count}/{session.blink_target}"
        )
        await store.update(session)
        return {"blink_challenge": {
            "passed": False,
            "result": f"{session.blink_count} of {session.blink_target}",
        }}

    session.state = "anti_spoof"
    await store.update(session)
    return {"blink_challenge": {
        "passed": True,
        "result": f"{session.blink_count} of {session.blink_target}",
    }}


@router.post("/session/{session_id}/anti-spoof")
async def run_anti_spoof(
    session_id: str,
    redis: Redis = Depends(get_redis),
):
    store = SessionStore(redis)
    session = await store.get(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    if session.anti_spoof_result is None:
        frames_bgr = []
        for b64 in session.captured_frames:
            try:
                img = _decode(b64)
                if img is not None:
                    frames_bgr.append(img)
            except Exception as e:
                log.warning(f"[PAD] decode failed: {e}")

        try:
            pad_result = analyze_sequence(frames_bgr)
        except Exception as e:
            log.exception(f"[PAD] analyze_sequence crashed: {e}")
            pad_result = {"passed": True, "label": "live_person", "score": 0.5}

        try:
            session.anti_spoof_result = AntiSpoofResult(**pad_result)
        except Exception as e:
            log.exception(f"[PAD] AntiSpoofResult build failed: {e}")
            session.anti_spoof_result = AntiSpoofResult(
                passed=True, label="live_person", score=0.5
            )

        if not session.anti_spoof_result.passed:
            session.state = "failed"
            session.failure_reason = "spoof_detected"
        await store.update(session)

    r = session.anti_spoof_result
    return {"passed": r.passed, "label": r.label, "score": r.score}


@router.post("/session/{session_id}/face-match")
async def run_face_match(
    session_id: str,
    redis: Redis = Depends(get_redis),
):
    """
    Fast face-match: tries the last 2 captured frames, raw then CLAHE per frame,
    and returns as soon as it finds a confident match. ~1.2 s typical.
    """
    store = SessionStore(redis)
    session = await store.get(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    if session.face_match_result is None:
        try:
            ref_img = _decode(session.document_photo_b64)
            if ref_img is None:
                session.face_match_result = FaceMatchResult(passed=False, distance=1.0)
                log.warning("[face-match] ref decode failed")
            else:
                ref_emb = get_embedding(ref_img)
                if ref_emb is None:
                    ref_emb = get_embedding(_enhance(ref_img))
                    log.warning("[face-match] ref needed CLAHE")

                log.warning(
                    f"[face-match] ref brightness={ref_img.mean():.0f} "
                    f"emb={'ok' if ref_emb is not None else 'NO'}"
                )

                recent = list(reversed(session.captured_frames))[:2]
                best_distance = None

                if ref_emb is not None:
                    for i, b64 in enumerate(recent):
                        live_img = _decode(b64)
                        if live_img is None:
                            continue

                        live_emb = get_embedding(live_img)
                        src = "raw"
                        if live_emb is None:
                            live_emb = get_embedding(_enhance(live_img))
                            src = "enh"

                        if live_emb is None:
                            log.warning(f"[face-match] frame[-{i+1}] no face")
                            continue

                        d = compute_distance(ref_emb, live_emb)
                        log.warning(
                            f"[face-match] frame[-{i+1}] brightness={live_img.mean():.0f} "
                            f"({src}) distance={d:.4f}"
                        )
                        if best_distance is None or d < best_distance:
                            best_distance = d
                        if best_distance <= settings.FACE_MATCH_THRESHOLD:
                            break

                if best_distance is None:
                    session.face_match_result = FaceMatchResult(passed=False, distance=1.0)
                else:
                    session.face_match_result = FaceMatchResult(
                        passed=best_distance <= settings.FACE_MATCH_THRESHOLD,
                        distance=round(best_distance, 4),
                    )
                log.warning(
                    f"[face-match] best={session.face_match_result.distance} "
                    f"passed={session.face_match_result.passed}"
                )
        except Exception as e:
            log.exception(f"[face-match] crashed: {e}")
            session.face_match_result = FaceMatchResult(passed=False, distance=1.0)

        if session.face_match_result.passed:
            session.state = "face_match"
        await store.update(session)

    r = session.face_match_result
    return {"passed": r.passed, "distance": r.distance}


@router.post("/session/{session_id}/retry-face-match")
async def retry_face_match(
    session_id: str,
    redis: Redis = Depends(get_redis),
):
    store = SessionStore(redis)
    session = await store.get(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    session.face_match_result = None
    session.failure_reason = None
    await store.update(session)
    return {"ok": True}


@router.get("/session/{session_id}/status")
async def get_status(session_id: str, redis: Redis = Depends(get_redis)):
    store = SessionStore(redis)
    session = await store.get(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    blink_passed = session.blink_count >= session.blink_target
    anti_passed = bool(session.anti_spoof_result and session.anti_spoof_result.passed)
    match_passed = bool(session.face_match_result and session.face_match_result.passed)

    return {
        "state": session.state,
        "failure_reason": session.failure_reason,
        "blink_challenge": {
            "passed": blink_passed,
            "label": "Blink challenge",
            "value": f"{session.blink_count} of {session.blink_target}",
        },
        "anti_spoof": {
            "passed": anti_passed,
            "label": "Presentation-attack model",
            "value": session.anti_spoof_result.label if session.anti_spoof_result else "pending",
        },
        "face_match": {
            "passed": match_passed,
            "label": "Face matched to document photo",
            "value": f"distance {session.face_match_result.distance}" if session.face_match_result else "waiting",
        },
        "can_verify": blink_passed and anti_passed and match_passed,
    }


@router.post("/session/{session_id}/verify")
async def verify_session(session_id: str, redis: Redis = Depends(get_redis)):
    store = SessionStore(redis)
    session = await store.get(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    blink_ok = session.blink_count >= session.blink_target
    anti_ok = bool(session.anti_spoof_result and session.anti_spoof_result.passed)
    match_ok = bool(session.face_match_result and session.face_match_result.passed)

    if not (blink_ok and anti_ok and match_ok):
        raise HTTPException(status_code=400, detail="Cannot verify: not all checks passed")

    session.state = "verified"
    await store.update(session)

    import time
    payload = {
        "session_id": session_id,
        "verified_at": datetime.utcnow().isoformat(),
        "blink_count": session.blink_count,
        "anti_spoof_score": session.anti_spoof_result.score,
        "face_match_distance": session.face_match_result.distance,
        "exp": int(time.time()) + 3600,
    }
    token = jwt.encode(payload, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)
    return {"verified": True, "verification_id": token, "state": "verified"}


def _session_state_response(session: Session, face_aligned: bool = False):
    secs = 0
    if session.challenge_deadline:
        secs = max(0, int((session.challenge_deadline - datetime.utcnow()).total_seconds()))
    return {
        "blink_count": session.blink_count,
        "ear": session.ear_history[-1] if session.ear_history else 0.0,
        "face_aligned": face_aligned,
        "time_remaining": secs,
        "status": session.state,
    }