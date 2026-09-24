# app/services/anti_spoof.py
import logging
import numpy as np
import cv2
import onnxruntime as ort
from app.config import settings

log = logging.getLogger(__name__)


class AntiSpoofModel:
    CROP_SCALE = 2.7   # MiniFASNetV2 standard
    INPUT_HW = (80, 80)

    def __init__(self, model_path: str | None = None):
        self.session = None
        self.input_name = None
        self._load(model_path or settings.PAD_MODEL_PATH)

    def _load(self, path: str):
        try:
            self.session = ort.InferenceSession(path, providers=["CPUExecutionProvider"])
            self.input_name = self.session.get_inputs()[0].name
            out_shape = self.session.get_outputs()[0].shape
            log.warning(f"[PAD] MiniFASNetV2 loaded. input={self.input_name} output={out_shape}")
        except Exception as e:
            log.warning(f"[PAD] ONNX not loaded ({e}); using heuristic fallback")
            self.session = None

    # ── 2.7× square crop around the face center ────────────────────
    def _crop_face(self, frame_bgr: np.ndarray, bbox: tuple[int, int, int, int]) -> np.ndarray:
        """
        bbox = (x1, y1, x2, y2) from a face detector or estimated.
        Expands to a 2.7× scale square centered on the bbox center.
        """
        x1, y1, x2, y2 = bbox
        cx = (x1 + x2) / 2.0
        cy = (y1 + y2) / 2.0
        face_w = x2 - x1
        face_h = y2 - y1
        side = max(face_w, face_h) * self.CROP_SCALE
        half = side / 2.0

        h, w = frame_bgr.shape[:2]
        nx1 = max(0, int(cx - half))
        ny1 = max(0, int(cy - half))
        nx2 = min(w, int(cx + half))
        ny2 = min(h, int(cy + half))
        return frame_bgr[ny1:ny2, nx1:nx2]

    # ── Full-frame predict (no bbox known) ─────────────────────────
    def predict(self, face_crop: np.ndarray) -> dict:
        try:
            if face_crop is None or face_crop.size == 0:
                return self._default_pass()
            if self.session is None:
                return self._heuristic(face_crop)

            img = cv2.resize(face_crop, self.INPUT_HW)
            img = img.astype(np.float32) / 255.0          # BGR, x/255
            img = np.transpose(img, (2, 0, 1))[None, ...] # HWC -> 1CHW

            logits = self.session.run(None, {self.input_name: img})[0][0]
            probs = self._softmax(logits)

            # Class 0 = live, 1 = print, 2 = replay
            live_score = float(probs[0])
            passed = live_score > 0.5
            return {
                "passed": passed,
                "label": "live_person" if passed else "spoof_suspected",
                "score": round(live_score, 4),
            }
        except Exception as e:
            log.warning(f"[PAD] predict failed ({e}); defaulting to pass")
            return self._default_pass()

    def _heuristic(self, face_crop: np.ndarray) -> dict:
        try:
            gray = cv2.cvtColor(face_crop, cv2.COLOR_BGR2GRAY)
            v = float(cv2.Laplacian(gray, cv2.CV_64F).var())
            passed = v > 8.0
            score = min(1.0, max(0.0, v / 80.0))
            return {
                "passed": passed,
                "label": "live_person" if passed else "spoof_suspected",
                "score": round(score, 4),
            }
        except Exception:
            return self._default_pass()

    def _default_pass(self) -> dict:
        return {"passed": True, "label": "live_person", "score": 0.5}

    @staticmethod
    def _softmax(x):
        e = np.exp(x - np.max(x))
        return e / e.sum()


anti_spoof_model = AntiSpoofModel()


def analyze_sequence(frames_bgr: list[np.ndarray]) -> dict:
    """
    Run PAD on the last N frames. Uses a rough 2.7× crop centered on the frame.
    When you wire this to MediaPipe landmarks, pass the real face bbox instead.
    """
    if not frames_bgr:
        log.warning("[PAD] no frames; defaulting to pass")
        return {"passed": True, "label": "live_person", "score": 0.5}

    scores = []
    for frame in frames_bgr[-5:]:
        try:
            h, w = frame.shape[:2]
            # Rough face estimate: center 40% of the frame
            side = min(w, h) * 0.4
            cx, cy = w // 2, h // 2
            x1 = int(cx - side / 2)
            y1 = int(cy - side / 2)
            x2 = int(cx + side / 2)
            y2 = int(cy + side / 2)

            crop = anti_spoof_model._crop_face(frame, (x1, y1, x2, y2))
            if crop.size == 0:
                continue
            scores.append(anti_spoof_model.predict(crop)["score"])
        except Exception as e:
            log.warning(f"[PAD] frame skipped ({e})")

    if not scores:
        return {"passed": True, "label": "live_person", "score": 0.5}

    avg = float(np.mean(scores))
    passed = avg > 0.35
    return {
        "passed": passed,
        "label": "live_person" if passed else "spoof_suspected",
        "score": round(avg, 4),
    }