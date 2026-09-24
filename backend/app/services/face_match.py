# app/services/face_match.py
import logging
import numpy as np
from insightface.app import FaceAnalysis

log = logging.getLogger(__name__)

# Lazy singleton — don't crash on import if models aren't downloaded yet
_face_app = None


def _get_face_app():
    global _face_app
    if _face_app is None:
        try:
            _face_app = FaceAnalysis(
                name="buffalo_l",
                providers=["CPUExecutionProvider"],
            )
            _face_app.prepare(ctx_id=0, det_size=(640, 640))
            log.info("[face_match] InsightFace buffalo_l loaded")
        except Exception as e:
            log.exception(f"[face_match] InsightFace load failed: {e}")
            _face_app = None
    return _face_app


def get_embedding(image_bgr: np.ndarray):
    """
    Extract the 512-D ArcFace embedding of the largest face in the image.
    Returns None if no face is found or the model is unavailable.
    """
    app = _get_face_app()
    if app is None:
        log.warning("[face_match] model unavailable; returning None")
        return None
    try:
        faces = app.get(image_bgr)
        if not faces:
            return None
        largest = max(
            faces,
            key=lambda f: (f.bbox[2] - f.bbox[0]) * (f.bbox[3] - f.bbox[1]),
        )
        return largest.embedding
    except Exception as e:
        log.exception(f"[face_match] get_embedding failed: {e}")
        return None


def compute_distance(emb1: np.ndarray, emb2: np.ndarray) -> float:
    """Cosine distance between two embeddings (0 = identical)."""
    try:
        e1 = emb1 / np.linalg.norm(emb1)
        e2 = emb2 / np.linalg.norm(emb2)
        return float(1.0 - np.dot(e1, e2))
    except Exception as e:
        log.exception(f"[face_match] compute_distance failed: {e}")
        return 1.0