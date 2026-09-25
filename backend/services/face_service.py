import os
import numpy as np
import cv2
from insightface.app import FaceAnalysis


class FaceVerificationService:
    """
    Face verification using InsightFace with ArcFace embeddings.
    Singleton pattern ensures the model loads only once across all instances.
    """

    _instance = None
    _initialized = False

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(FaceVerificationService, cls).__new__(cls)
        return cls._instance

    def __init__(self):
        if self._initialized:
            return

        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        cache_dir = os.path.join(base_dir, "models", "insightface")
        os.environ['INSIGHTFACE_HOME'] = cache_dir
        os.makedirs(cache_dir, exist_ok=True)

        self.model_name = "buffalo_l"
        self.threshold = 0.55
        self.det_size = (640, 640)

        try:
            import onnxruntime as ort
            available_providers = ort.get_available_providers()
            ctx_id = 0 if 'CUDAExecutionProvider' in available_providers else -1
        except ImportError:
            ctx_id = -1

        self.app = FaceAnalysis(name=self.model_name)
        self.app.prepare(ctx_id=ctx_id, det_size=self.det_size)

        print(f"✅ InsightFace Singleton initialized with model: {self.model_name} (ctx_id={ctx_id})")
        print(f"   Cache directory: {cache_dir}")

        self._initialized = True

    # ------------------------------------------------------------------
    # NEW — used by FileRoleClassifier to decide document vs face
    # ------------------------------------------------------------------
    def detect(self, img_or_bytes):
        """
        Face detection only. Accepts bytes or a numpy BGR array.
        Returns list of InsightFace Face objects (.bbox, .det_score, .normed_embedding).
        Returns [] on failure / no face.
        """
        if isinstance(img_or_bytes, (bytes, bytearray)):
            nparr = np.frombuffer(img_or_bytes, np.uint8)
            img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        else:
            img = img_or_bytes

        if img is None or getattr(img, "size", 0) == 0:
            return []

        try:
            return self.app.get(img) or []
        except Exception as e:
            print(f"[face_service.detect] error: {e}")
            return []

    # ------------------------------------------------------------------
    # Unchanged
    # ------------------------------------------------------------------
    def _get_embedding(self, image_bytes: bytes):
        nparr = np.frombuffer(image_bytes, np.uint8)
        img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        if img is None:
            return None
        faces = self.app.get(img)
        if not faces:
            return None
        return faces[0].normed_embedding

    def verify(self, document_image_bytes: bytes, live_photo_bytes: bytes):
        doc_emb = self._get_embedding(document_image_bytes)
        live_emb = self._get_embedding(live_photo_bytes)

        if doc_emb is None:
            return {
                "verified": False, "distance": 1.0, "similarity": 0.0,
                "threshold": self.threshold, "confidence": 0.0,
                "model": self.model_name,
                "note": "No face detected in document image",
            }
        if live_emb is None:
            return {
                "verified": False, "distance": 1.0, "similarity": 0.0,
                "threshold": self.threshold, "confidence": 0.0,
                "model": self.model_name,
                "note": "No face detected in live photo",
            }

        similarity = float(np.dot(doc_emb, live_emb))
        distance = 1.0 - similarity
        verified = similarity >= self.threshold

        return {
            "verified": verified,
            "distance": round(distance, 4),
            "similarity": round(similarity, 4),
            "threshold": self.threshold,
            "confidence": round(similarity, 4),
            "model": self.model_name,
            "note": "Face verification completed" if verified else "Face mismatch detected",
        }