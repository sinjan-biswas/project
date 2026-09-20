# backend/services/image_quality_service.py
"""
Classical-CV quality gate for document images.

No ML for the quality metrics themselves — pure OpenCV + numpy.
The OCR confidence signal comes from PaddleOCR (via an injected probe
callable), reusing the same engine instance that OCRService uses.

The probe is intentionally PaddleOCR-only (not DualOCREngine) because:
  * The gate runs on every request — it needs to be cheap.
  * TrOCR is ~1s/line on CPU; running it here would dominate latency.
  * TrOCR stays inside OCRService.extract() where it belongs.

The probe also deliberately does NOT deskew — we want the gate to see
the raw (possibly tilted) image so it can flag the tilt.
"""

import cv2
import numpy as np


class ImageQualityGate:
    def __init__(
        self,
        ocr_probe=None,                  # callable(image_bytes) -> float in 0..1
        blur_thresh: float = 100.0,      # Laplacian variance floor
        skew_thresh_deg: float = 8.0,    # max tilt in degrees
        dark_pct_thresh: float = 45.0,   # % of pixels below brightness floor
        min_width: int = 800,            # minimum acceptable width in pixels
    ):
        self.ocr_probe = ocr_probe
        self.blur_thresh = blur_thresh
        self.skew_thresh_deg = skew_thresh_deg
        self.dark_pct_thresh = dark_pct_thresh
        self.min_width = min_width

    def assess(self, image_bytes: bytes) -> dict:
        """
        Returns:
            {
              "decision": "ok" | "enhance" | "reject",
              "score": float 0..100,
              "metrics": {blur_var, skew_deg, dark_pct, bright_pct,
                          width, height, ocr_conf},
              "reasons": [str, ...],
              "was_enhanced": False,
            }
        """
        nparr = np.frombuffer(image_bytes, np.uint8)
        img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        if img is None:
            return {
                "decision": "reject",
                "score": 0.0,
                "metrics": {},
                "reasons": ["unreadable image file"],
                "was_enhanced": False,
            }

        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        h, w = gray.shape

        # 1. Blur — Laplacian variance
        blur_var = float(cv2.Laplacian(gray, cv2.CV_64F).var())

        # 2. Skew — minAreaRect over text-edge contours
        edges = cv2.Canny(gray, 50, 150)
        contours, _ = cv2.findContours(
            edges, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE
        )
        angles = [
            cv2.minAreaRect(c)[-1]
            for c in contours
            if cv2.contourArea(c) > 200
        ]
        skew_deg = 0.0
        if angles:
            med = float(np.median(angles))
            skew_deg = med - 90.0 if med > 45.0 else med

        # 3. Illumination — dark / glare
        dark_pct = float(np.mean(gray < 40)) * 100.0
        bright_pct = float(np.mean(gray > 235)) * 100.0

        # 4. Resolution
        low_res = w < self.min_width

        # 5. PaddleOCR confidence probe (injected; returns 0..1)
        avg_conf = 0.0
        if self.ocr_probe is not None:
            try:
                avg_conf = float(self.ocr_probe(image_bytes)) * 100.0
            except Exception:
                avg_conf = 0.0

        # --- Reasons -------------------------------------------------
        reasons = []
        if blur_var < self.blur_thresh:
            reasons.append("too blurry")
        if abs(skew_deg) > self.skew_thresh_deg:
            reasons.append(f"document tilted {abs(skew_deg):.0f}°")
        if dark_pct > self.dark_pct_thresh:
            reasons.append("too dark")
        if bright_pct > 25.0:
            reasons.append("glare / overexposed")
        if low_res:
            reasons.append("resolution too low")

        metrics = {
            "blur_var": round(blur_var, 1),
            "skew_deg": round(skew_deg, 1),
            "dark_pct": round(dark_pct, 1),
            "bright_pct": round(bright_pct, 1),
            "width": int(w),
            "height": int(h),
            "ocr_conf": round(avg_conf, 1),
        }

        # --- Weighted 0–100 score ------------------------------------
        score = 100.0

        if blur_var < self.blur_thresh * 2:
            deficit = (self.blur_thresh * 2 - blur_var) / (self.blur_thresh * 2)
            score -= min(deficit * 40.0, 40.0)

        score -= min(abs(skew_deg) * 2.0, 25.0)
        score -= min(dark_pct * 0.5, 20.0)

        if low_res:
            score -= 10.0

        score = max(0.0, round(score, 1))

        # --- Decision ------------------------------------------------
        if reasons and (score < 40.0 or avg_conf < 30.0):
            decision = "reject"
        elif reasons:
            decision = "enhance"
        else:
            decision = "ok"

        return {
            "decision": decision,
            "score": score,
            "metrics": metrics,
            "reasons": reasons,
            "was_enhanced": False,
        }