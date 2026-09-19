# backend/services/text_manipulation.py
#
# Rewritten to consume DualOCREngine output instead of pytesseract.
# Zero external OCR dependency — the OCR pass already happened upstream.
#
# Detection idea (unchanged from the original):
#   Authentic documents have uniformly high OCR confidence across text
#   regions. Spliced/painted text creates LOCALIZED confidence drops,
#   because pasted text has different anti-aliasing, ink density and
#   JPEG compression than its surroundings.

import numpy as np


class TextManipulationDetector:
    """Detects text tampering from OCR confidence distribution.

    Input:  ocr_lines — list of dicts with keys 'box', 'text', 'confidence'
            (the shape produced by DualOCREngine.extract_lines).

    If ocr_lines is empty or has too few words, returns available=False
    and text_score=0.0. Never fabricates a score.
    """

    LOW_CONF_THRESHOLD = 0.60   # TrOCR/Paddle confidences are 0..1

    def detect(self, image_path, ocr_lines=None) -> dict:
        # NOTE: image_path is kept in the signature for API compatibility
        # with the old call site, but we no longer read the image — the
        # OCR pass already gave us what we need.
        lines = ocr_lines or []
        if len(lines) < 10:
            return {
                "text_score": 0.0,
                "available": False,
                "reason": f"too few lines ({len(lines)})",
            }

        confs = np.array(
            [float(l.get("confidence", 0.0)) for l in lines],
            dtype=float,
        )
        if confs.size < 10:
            return {
                "text_score": 0.0,
                "available": False,
                "reason": "too little text",
            }

        # ---- Global statistics ---------------------------------------
        mean_conf = float(confs.mean())
        std_conf = float(confs.std())
        low_conf_ratio = float((confs < self.LOW_CONF_THRESHOLD).mean())

        # ---- Spatial variance: 4x4 grid on line centers --------------
        spatial_var = self._spatial_variance(lines, confs)

        # ---- Fusion (same weights as the original module) ------------
        #   std_conf / 0.30   → normalised to roughly [0,1]
        #   low_conf_ratio    → already [0,1]
        #   spatial_var / 0.30 → normalised to roughly [0,1]
        score = min(
            1.0,
            (std_conf / 0.30) * 0.4
            + low_conf_ratio * 0.4
            + (spatial_var / 0.30) * 0.2,
        )

        return {
            "text_score": round(float(score), 3),
            "available": True,
            "mean_confidence": round(mean_conf, 3),
            "confidence_std": round(std_conf, 3),
            "low_conf_ratio": round(low_conf_ratio, 3),
            "spatial_variance": round(spatial_var, 3),
        }

    # ------------------------------------------------------------------ #
    def _spatial_variance(self, lines: list, confs: np.ndarray) -> float:
        """Bin line confidences into a 4x4 grid (by box center),
        then return the std-dev of the per-cell means."""
        # Collect centers
        centers = []
        for ln in lines:
            box = ln.get("box")
            if not box:
                continue
            try:
                xs = [float(p[0]) for p in box]
                ys = [float(p[1]) for p in box]
            except (TypeError, ValueError, IndexError):
                continue
            centers.append(((min(xs) + max(xs)) / 2,
                            (min(ys) + max(ys)) / 2))
        if len(centers) != len(confs):
            # Box / confidence count mismatch — skip spatial term
            return 0.0

        cx = np.array([c[0] for c in centers])
        cy = np.array([c[1] for c in centers])
        w = float(cx.max() - cx.min()) or 1.0
        h = float(cy.max() - cy.min()) or 1.0

        gx = np.clip(((cx - cx.min()) / w * 4).astype(int), 0, 3)
        gy = np.clip(((cy - cy.min()) / h * 4).astype(int), 0, 3)

        grid = np.zeros((4, 4), dtype=float)
        counts = np.zeros((4, 4), dtype=int)
        for i in range(len(confs)):
            grid[gy[i], gx[i]] += confs[i]
            counts[gy[i], gx[i]] += 1

        valid = counts > 0
        if valid.sum() < 2:
            return 0.0
        means = grid[valid] / counts[valid]
        return float(means.std())