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
    # Signal weights (sum = 1.0 when all are available).
    WEIGHTS = {
        "cnn":          0.45,
        "substitution": 0.20,
        "text":         0.15,
        "stamp":        0.10,
        "exif":         0.10,
    }
    IS_TAMPERED_THRESHOLD = 0.45
    BLANK_STD_THRESHOLD   = 8.0

    def __init__(self):
        self.model = TamperNet() if TamperNet else None
        self.substitution = (PhotoSubstitutionDetector()
                             if PhotoSubstitutionDetector else None)
        self.text = (TextManipulationDetector()
                     if TextManipulationDetector else None)
        self.stamp = (StampForgeryDetector()
                      if StampForgeryDetector else None)
        self.ela_threshold = 0.12

    # ---------- blank image guard ----------
    def _is_blank(self, image_path: str) -> bool:
        try:
            gray = cv2.imread(str(image_path), cv2.IMREAD_GRAYSCALE)
            if gray is None:
                return False
            return float(gray.std()) < self.BLANK_STD_THRESHOLD
        except Exception:
            return False

    # ---------- ELA (telemetry-only) ----------
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

    # ---------- fallback result ----------
    def _result(self, score: float, is_tampered: bool,
                note: str = "", ela: float = 0.0) -> dict:
        return {
            "tampering_score": round(score * 100, 2),
            "ela_score": round(ela * 100, 2),
            "dl_score": 0.0,
            "copy_move_score": 0.0,
            "edge_score": 0.0,
            "text_score": 0.0,
            "stamp_score": 0.0,
            "heatmap_path": None,
            "is_tampered": is_tampered,
            "model": "ELA-only (fallback)",
            "risk_factors": [],
            "note": note or ("Tampering detected" if is_tampered
                             else "No tampering detected"),
            "details": {
                "photo_substitution": {},
                "text_manipulation": {},
                "stamp_forgery": {},
                "exif_flags": [],
            },
        }

    # ---------- main entry ----------
    def analyze(self, image_path: str, ocr_lines: list | None = None) -> dict:
        if not os.path.exists(image_path):
            return self._result(0.0, False, "Image not found")

        is_blank = self._is_blank(image_path)
        heatmap_path = HEATMAP_DIR / f"{uuid.uuid4().hex}.jpg"
        reasons: list[str] = []

        try:
            # 1. CNN forgery score + Grad-CAM
            dl_prob = 0.0
            dl_heatmap = None
            dl_available = False
            dl_skipped_blank = False
            if self.model is not None:
                if is_blank:
                    dl_skipped_blank = True
                else:
                    dl = self.model.predict(image_path, str(heatmap_path))
                    dl_prob = float(dl.get("forgery_probability", 0.0) or 0.0)
                    dl_heatmap = dl.get("heatmap")
                    dl_available = dl.get("available", False)

            # 2. Photo substitution
            subst_score = 0.0
            subst: dict = {}
            if self.substitution is not None and not is_blank:
                subst = self.substitution.detect(image_path)
                subst_score = float(subst.get("substitution_score") or 0.0)

            # 3. Text manipulation — consumes the OCR lines we already have
            text_score = 0.0
            text: dict = {}
            if self.text is not None and ocr_lines:
                text = self.text.detect(image_path, ocr_lines=ocr_lines)
                if text.get("available"):
                    text_score = float(text.get("text_score", 0.0) or 0.0)

            # 4. Stamp forgery
            stamp_score = 0.0
            stamp: dict = {}
            if self.stamp is not None and not is_blank:
                stamp = self.stamp.detect(image_path)
                stamp_score = float(stamp.get("stamp_score", 0.0) or 0.0)

            # 5. EXIF metadata
            exif_flags = []
            if analyze_metadata is not None:
                try:
                    exif_flags = analyze_metadata(image_path)
                except Exception:
                    exif_flags = []
            exif_score = min(1.0, len(exif_flags) * 0.25)

            # 6. ELA — telemetry only, not fused
            ela = self._simple_ela(image_path)

            # ---------- weighted fusion w/ dynamic renormalization ----
            signals = {
                "cnn":          (None if dl_skipped_blank else dl_prob),
                "substitution": subst_score,
                "text":         (text_score if text.get("available") else None),
                "stamp":        stamp_score,
                "exif":         exif_score,
            }
            active = {k: v for k, v in signals.items() if v is not None}
            total_w = sum(self.WEIGHTS[k] for k in active) or 1.0
            score = sum(self.WEIGHTS[k] * active[k] for k in active) / total_w
            is_tampered = score > self.IS_TAMPERED_THRESHOLD

            # ---------- explainability ----------
            if dl_prob > 0.5:
                reasons.append(
                    f"CNN detected forgery artifacts ({dl_prob:.0%})")
            if subst_score > 0.5:
                reasons.append(
                    "Face photo region inconsistent with document texture")
            if text_score > 0.5:
                reasons.append(
                    "OCR confidence anomalies suggest text splicing")
            if stamp_score > 0.5:
                reasons.append("Stamp geometry/ink density suspicious")
            for f in exif_flags:
                if isinstance(f, dict):
                    reasons.append(
                        f"{f.get('type', 'EXIF')}: {f.get('detail', '')}")
            if (not dl_available and self.model is not None
                    and not dl_skipped_blank):
                reasons.append(
                    "CNN checkpoint missing — running heuristics-only")
            if self.model is None:
                reasons.append(
                    "CNN service unavailable — running heuristics-only")

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
                "note": ("; ".join(reasons) if reasons
                         else "No tampering detected"),
                "details": {
                    "photo_substitution": subst,
                    "text_manipulation": text,
                    "stamp_forgery": stamp,
                    "exif_flags": exif_flags,
                    "cnn_skipped_blank": dl_skipped_blank,
                },
            }

        except Exception as e:
            return self._result(0.0, False,
                                f"Tampering analysis error: {e}")