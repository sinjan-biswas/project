import cv2
import numpy as np
import pytesseract
from pytesseract import Output


class TextManipulationDetector:
    """
    Detects text tampering using OCR confidence variance.
    Authentic documents have uniform OCR confidence across text regions.
    Spliced/painted text creates local confidence anomalies.
    """

    def __init__(self, low_conf_threshold: int = 60):
        self.low_conf_threshold = low_conf_threshold

    def detect(self, image_path: str) -> dict:
        img = cv2.imread(str(image_path))
        if img is None:
            return {"text_score": 0.0, "available": False}

        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        data = pytesseract.image_to_data(gray, output_type=Output.DICT)

        confs = np.array([c for c in data["conf"] if c != "-1"], dtype=float)
        if confs.size < 10:
            return {"text_score": 0.0, "available": False, "reason": "too little text"}

        # Global statistics
        mean_conf = confs.mean()
        std_conf = confs.std()
        low_conf_ratio = (confs < self.low_conf_threshold).mean()

        # Local anomaly: bin word confidences into a coarse grid and measure
        # spatial variance — real forgeries create localized confidence drops.
        w, h = img.shape[1], img.shape[0]
        grid = np.zeros((4, 4), dtype=float)
        counts = np.zeros((4, 4), dtype=int)
        for i, c in enumerate(data["conf"]):
            if c == "-1":
                continue
            cx = data["left"][i] + data["width"][i] / 2
            cy = data["top"][i] + data["height"][i] / 2
            gx = min(3, int(cx / w * 4))
            gy = min(3, int(cy / h * 4))
            grid[gy, gx] += c
            counts[gy, gx] += 1

        valid = counts > 0
        if valid.sum() < 2:
            spatial_var = 0.0
        else:
            means = grid[valid] / counts[valid]
            spatial_var = float(means.std())

        # Fusion: high std + high low-conf ratio + high spatial variance → suspicious
        score = min(1.0, (std_conf / 40.0) * 0.4
                         + low_conf_ratio * 0.4
                         + (spatial_var / 30.0) * 0.2)

        return {
            "text_score": round(float(score), 3),
            "available": True,
            "mean_confidence": round(float(mean_conf), 2),
            "confidence_std": round(float(std_conf), 2),
            "low_conf_ratio": round(float(low_conf_ratio), 3),
            "spatial_variance": round(spatial_var, 3),
        }