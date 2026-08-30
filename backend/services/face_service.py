class FaceVerificationService:
    def __init__(self):
        pass
    
    def verify(self, document_image_bytes: bytes, live_photo_bytes: bytes):
        # TODO: Integrate DeepFace here
        return {
            "verified": True,
            "distance": 0.0,
            "threshold": 0.4,
            "confidence": 1.0,
            "model": "stub",
            "note": "Using stub - replace with DeepFace"
        }
