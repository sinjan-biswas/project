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
        # Skip re-initialization if already done
        if self._initialized:
            return

        # --- 1. Set persistent cache directory ---
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        cache_dir = os.path.join(base_dir, "models", "insightface")
        os.environ['INSIGHTFACE_HOME'] = cache_dir
        os.makedirs(cache_dir, exist_ok=True)

        # --- 2. Model configuration ---
        self.model_name = "buffalo_l"
        self.threshold = 0.55
        self.det_size = (640, 640)

        # --- 3. Auto-detect GPU (CUDA) ---
        try:
            import onnxruntime as ort
            available_providers = ort.get_available_providers()
            ctx_id = 0 if 'CUDAExecutionProvider' in available_providers else -1
        except ImportError:
            ctx_id = -1   # fallback to CPU

        # --- 4. Load the model (this happens only ONCE) ---
        self.app = FaceAnalysis(name=self.model_name)
        self.app.prepare(ctx_id=ctx_id, det_size=self.det_size)

        print(f"✅ InsightFace Singleton initialized with model: {self.model_name} (ctx_id={ctx_id})")
        print(f"   Cache directory: {cache_dir}")

        # Mark as initialized so subsequent calls skip the heavy load
        self._initialized = True

    def _get_embedding(self, image_bytes: bytes):
        """Extract 512-D face embedding from image bytes."""
        nparr = np.frombuffer(image_bytes, np.uint8)
        img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

        if img is None:
            return None

        faces = self.app.get(img)
        if not faces:
            return None

        return faces[0].normed_embedding

    def verify(self, document_image_bytes: bytes, live_photo_bytes: bytes):
        """Compare document face with live photo face."""
        doc_emb = self._get_embedding(document_image_bytes)
        live_emb = self._get_embedding(live_photo_bytes)

        if doc_emb is None:
            return {
                "verified": False,
                "distance": 1.0,
                "similarity": 0.0,
                "threshold": self.threshold,
                "confidence": 0.0,
                "model": self.model_name,
                "note": "No face detected in document image"
            }

        if live_emb is None:
            return {
                "verified": False,
                "distance": 1.0,
                "similarity": 0.0,
                "threshold": self.threshold,
                "confidence": 0.0,
                "model": self.model_name,
                "note": "No face detected in live photo"
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
            "note": "Face verification completed" if verified else "Face mismatch detected"
        }