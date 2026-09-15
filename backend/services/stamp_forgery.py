import cv2
import numpy as np


class StampForgeryDetector:
    """
    Detects forged stamps by analyzing:
      1. Color saturation consistency (real stamps have uniform ink density)
      2. Edge sharpness (digital stamps have unnaturally sharp edges)
      3. Circularity of detected stamp regions
    """

    def __init__(self):
        pass

    def detect(self, image_path: str) -> dict:
        img = cv2.imread(str(image_path))
        if img is None:
            return {"stamp_score": 0.0, "available": False}

        hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
        h, w = img.shape[:2]

        # Red + blue ink masks
        red1 = cv2.inRange(hsv, (0, 80, 60), (10, 255, 255))
        red2 = cv2.inRange(hsv, (170, 80, 60), (180, 255, 255))
        blue = cv2.inRange(hsv, (100, 80, 60), (130, 255, 255))
        mask = cv2.bitwise_or(cv2.bitwise_or(red1, red2), blue)

        # Morphological cleanup — kill isolated text-like pixels
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (7, 7))
        mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel, iterations=2)

        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        # Filter: keep only large, roughly circular contours
        min_area = (h * w) * 0.005               # ≥ 0.5% of image
        candidates = []
        for c in contours:
            area = cv2.contourArea(c)
            if area < min_area:
                continue
            perimeter = cv2.arcLength(c, True)
            circularity = 4 * np.pi * area / (perimeter ** 2 + 1e-6)
            if circularity > 0.6:                # actually circular
                candidates.append((c, area, circularity))

        if not candidates:
            return {"stamp_score": 0.0, "available": True, "stamps_found": 0}

        # Analyze the largest candidate
        c, area, circularity = max(candidates, key=lambda x: x[1])
        x, y, bw, bh = cv2.boundingRect(c)
        roi = cv2.cvtColor(img[y:y+bh, x:x+bw], cv2.COLOR_BGR2GRAY)
        lap_var = cv2.Laplacian(roi, cv2.CV_64F).var()

        roi_mask = mask[y:y+bh, x:x+bw]
        ink_pixels = roi[roi_mask > 0]
        density_std = float(ink_pixels.std()) if ink_pixels.size > 10 else 0.0

        # Scoring
        score = 0.0
        if circularity > 0.80 and lap_var > 1200:
            score += 0.5                         # suspiciously perfect + sharp
        if density_std > 60:
            score += 0.3                         # patchy ink
        if area > (h * w) * 0.03:                # huge stamp
            score += 0.2

        return {
            "stamp_score": round(min(1.0, score), 3),
            "available": True,
            "stamps_found": len(candidates),
            "circularity": round(float(circularity), 3),
            "edge_sharpness": round(float(lap_var), 2),
            "ink_density_std": round(density_std, 2),
        }