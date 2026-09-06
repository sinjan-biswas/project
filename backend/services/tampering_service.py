import os
import cv2
import numpy as np
from PIL import Image


class TamperingDetector:
    def __init__(self):
        self.threshold = 0.12

    def analyze(self, image_path: str):
        if not os.path.exists(image_path):
            return self._result(0.0, False, "Image not found")

        try:
            score = self._simple_ela(image_path)
            is_tampered = score > self.threshold
            return self._result(score, is_tampered)
        except Exception as e:
            return self._result(0.0, False, str(e))

    def _simple_ela(self, image_path: str) -> float:
        original = Image.open(image_path).convert("RGB")
        temp_path = "/tmp/ela_temp.jpg"
        original.save(temp_path, "JPEG", quality=90)
        compressed = Image.open(temp_path)

        orig_array = np.array(original).astype(np.float32)
        comp_array = np.array(compressed).astype(np.float32)
        diff = np.abs(orig_array - comp_array)
        avg_diff = float(np.mean(diff) / 255.0)

        if os.path.exists(temp_path):
            os.remove(temp_path)
        return avg_diff

    def _result(self, score: float, is_tampered: bool, note: str = ""):
        return {
            "tampering_score": round(score * 100, 2),
            "ela_score": round(score * 100, 2),
            "copy_move_score": 0.0,
            "edge_score": 0.0,
            "heatmap_path": None,
            "is_tampered": is_tampered,
            "note": note or ("Tampering detected" if is_tampered else "No tampering detected"),
        }
