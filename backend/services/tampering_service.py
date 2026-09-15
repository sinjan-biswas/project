# backend/services/tampering_service.py
import os
import uuid
from pathlib import Path

import cv2
import numpy as np

# --- Optional imports (graceful degradation) ---
try:
    from tampering_dl.infer import TamperNet
except Exception as e:
    print(f"[TamperingDetector] TamperNet unavailable: {e}")
    TamperNet = None

try:
    from services.photo_substitution import PhotoSubstitutionDetector
except Exception as e:
    print(f"[TamperingDetector] PhotoSubstitution unavailable: {e}")
    PhotoSubstitutionDetector = None

try:
    from services.text_manipulation import TextManipulationDetector
except Exception as e:
    print(f"[TamperingDetector] TextManipulation unavailable: {e}")
    TextManipulationDetector = None

try:
    from services.stamp_forgery import StampForgeryDetector
except Exception as e:
    print(f"[TamperingDetector] StampForgery unavailable: {e}")
    StampForgeryDetector = None

try:
    from services.metadata_service import analyze_metadata
except Exception as e:
    print(f"[TamperingDetector] Metadata unavailable: {e}")
    analyze_metadata = None


BASE_DIR = Path(__file__).resolve().parent.parent
HEATMAP_DIR = BASE_DIR / "static" / "heatmaps"
HEATMAP_DIR.mkdir(parents=True, exist_ok=True)


class TamperingDetector:
    def __init__(self):
        self.model = TamperNet() if TamperNet else None
        self.substitution = PhotoSubstitutionDetector() if PhotoSubstitutionDetector else None
        self.text = TextManipulationDetector() if TextManipulationDetector else None
        self.stamp = StampForgeryDetector() if StampForgeryDetector else None
        self.ela_threshold = 0.12

    # ---------- ELA (legacy secondary signal) ----------
    def _simple_ela(self, image_path: str) -> float:
        try:
            img = cv2.imread(str(image_path))
            if img is None:
                return 0.0
            tmp = f"/tmp/_ela_{uuid.uuid4().hex}.jpg"
            cv2.imwrite(tmp, img, [cv2.IMWRITE_JPEG_QUALITY, 90])
            compressed = cv2.imread(tmp)
            if os.path.exists(tmp):
                os.remove(tmp)
            if compressed is None:
                return 0.0
            diff = cv2.absdiff(img, compressed).astype(np.float32)
            return float(diff.mean() / 255.0)
        except Exception:
            return 0.0

    # ---------- result builders ----------
    def _result(self, score: float, is_tampered: bool, note: str = "") -> dict:
        return {
            "tampering_score": round(score * 100, 2),
            "ela_score": round(score * 100, 2),
            "dl_score": 0.0,
            "copy_move_score": 0.0,
            "edge_score": 0.0,
            "text_score": 0.0,
            "stamp_score": 0.0,
            "heatmap_path": None,
            "is_tampered": is_tampered,
            "model": "ELA-only (fallback)",
            "risk_factors": [],
            "note": note or ("Tampering detected" if is_tampered else "No tampering detected"),
        }

    # ---------- main entry ----------
    def analyze(self, image_path: str) -> dict:
        if not os.path.exists(image_path):
            return self._result(0.0, False, "Image not found")

        heatmap_path = HEATMAP_DIR / f"{uuid.uuid4().hex}.jpg"
        reasons: list[str] = []

        try:
            # 1. CNN forgery score + Grad-CAM (weight 0.45)
            dl_prob = 0.0
            dl_heatmap = None
            dl_available = False
            if self.model is not None:
                dl = self.model.predict(image_path, str(heatmap_path))
                dl_prob = float(dl.get("forgery_probability", 0.0) or 0.0)
                dl_heatmap = dl.get("heatmap")
                dl_available = dl.get("available", False)

            # 2. Photo substitution (weight 0.20)
            subst_score = 0.0
            subst = {}
            if self.substitution is not None:
                subst = self.substitution.detect(image_path)
                subst_score = float(subst.get("substitution_score") or 0.0)

            # 3. Text manipulation (weight 0.15)
            text_score = 0.0
            text = {}
            if self.text is not None:
                text = self.text.detect(image_path)
                text_score = float(text.get("text_score", 0.0) or 0.0)

            # 4. Stamp forgery (weight 0.10)
            stamp_score = 0.0
            stamp = {}
            if self.stamp is not None:
                stamp = self.stamp.detect(image_path)
                stamp_score = float(stamp.get("stamp_score", 0.0) or 0.0)

            # 5. EXIF metadata (weight 0.10)
            exif_flags = []
            if analyze_metadata is not None:
                try:
                    exif_flags = analyze_metadata(image_path)
                except Exception:
                    exif_flags = []
            exif_score = min(1.0, len(exif_flags) * 0.25)

            # 6. ELA (secondary signal — not in fusion, kept for telemetry)
            ela = self._simple_ela(image_path)

            # ---------- weighted fusion ----------
            score = (
                0.45 * dl_prob
                + 0.20 * subst_score
                + 0.15 * text_score
                + 0.10 * stamp_score
                + 0.10 * exif_score
            )
            is_tampered = score > 0.45

            # ---------- explainability ----------
            if dl_prob > 0.5:
                reasons.append(f"CNN detected forgery artifacts ({dl_prob:.0%})")
            if subst_score > 0.5:
                reasons.append("Face photo region inconsistent with document texture")
            if text_score > 0.5:
                reasons.append("OCR confidence anomalies suggest text splicing")
            if stamp_score > 0.5:
                reasons.append("Stamp geometry/ink density suspicious")
            for f in exif_flags:
                if isinstance(f, dict):
                    reasons.append(f"{f.get('type', 'EXIF')}: {f.get('detail', '')}")
            if not dl_available and self.model is not None:
                reasons.append("CNN checkpoint missing — running heuristics-only")
            if self.model is None:
                reasons.append("CNN service unavailable — running heuristics-only")

            return {
                "tampering_score": round(score * 100, 2),
                "ela_score": round(ela * 100, 2),
                "dl_score": round(dl_prob * 100, 2),
                "copy_move_score": round(subst_score * 100, 2),
                "edge_score": round(stamp_score * 100, 2),
                "text_score": round(text_score * 100, 2),
                "stamp_score": round(stamp_score * 100, 2),
                "heatmap_path": dl_heatmap,
                "is_tampered": is_tampered,
                "model": "TamperNet-ResNet18 + 5-signal fusion",
                "risk_factors": reasons,
                "note": "; ".join(reasons) if reasons else "No tampering detected",
                "details": {
                    "photo_substitution": subst,
                    "text_manipulation": text,
                    "stamp_forgery": stamp,
                    "exif_flags": exif_flags,
                },
            }

        except Exception as e:
            return self._result(0.0, False, f"Tampering analysis error: {e}")