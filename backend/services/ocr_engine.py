import cv2
import numpy as np
import torch
import paddleocr
from paddleocr import PaddleOCR
from transformers import TrOCRProcessor, VisionEncoderDecoderModel

from .preprocess import upscale_for_trocr


def _paddle_major_version() -> int:
    try:
        return int(paddleocr.__version__.split(".")[0])
    except Exception:
        return 2


class DualOCREngine:
    TROCR_CONF_THRESHOLD = 0.85   # only re-read lines below this confidence

    def __init__(self):
        # PaddleOCR v2 vs v3 have different constructor + call signatures.
        if _paddle_major_version() >= 3:
            self.paddle = PaddleOCR(
                use_textline_orientation=True,
                lang="en",
            )
            self._paddle_v3 = True
        else:
            self.paddle = PaddleOCR(
                use_angle_cls=True,
                lang="en",
                show_log=False,
            )
            self._paddle_v3 = False

        self.trocr_proc = TrOCRProcessor.from_pretrained(
            "microsoft/trocr-base-printed",
        )
        self.trocr = VisionEncoderDecoderModel.from_pretrained(
            "microsoft/trocr-base-printed"
        )
        self.trocr.eval()
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        self.trocr.to(self.device)

    # ------------------------------------------------------------------ #
    #  PaddleOCR call — handles v2 and v3 return shapes
    # ------------------------------------------------------------------ #
    def _paddle_ocr(self, image) -> list[tuple]:
        """Return a flat list of (box, text, conf) tuples."""
        if self._paddle_v3:
            # v3: predict() -> list of dicts with 'rec_texts', 'rec_scores', 'dt_polys'
            results = self.paddle.predict(image)
            out = []
            for page in results or []:
                polys = page.get("dt_polys") or []
                texts = page.get("rec_texts") or []
                scores = page.get("rec_scores") or []
                for box, text, conf in zip(polys, texts, scores):
                    out.append((box, text, float(conf)))
            return out

        # v2: ocr() -> list of [ [box, (text, conf)], ... ] per page
        raw = self.paddle.ocr(image, cls=True)
        out = []
        for page in raw or []:
            for box, (text, conf) in page or []:
                out.append((box, text, float(conf)))
        return out

    # ------------------------------------------------------------------ #
    #  NEW — cheap PaddleOCR-only confidence probe (used by quality gate)
    # ------------------------------------------------------------------ #
    def probe_confidence(self, image) -> float:
        """
        Returns mean PaddleOCR recognition confidence over all detected
        lines, normalised to 0..1. Returns 0.0 on any failure or when no
        text is detected.

        Deliberately does NOT run TrOCR — that is reserved for
        extract_lines() so real OCR stays fast for the common case.
        """
        try:
            pairs = self._paddle_ocr(image)
        except Exception:
            return 0.0

        if not pairs:
            return 0.0

        confs = [float(conf) for _box, _text, conf in pairs if conf is not None]
        if not confs:
            return 0.0
        return sum(confs) / len(confs)

    # ------------------------------------------------------------------ #
    #  Main entry
    # ------------------------------------------------------------------ #
    def extract_lines(self, image) -> list[dict]:
        lines = []
        for box, text, conf in self._paddle_ocr(image):
            crop = self._crop_box(image, box)
            # Only verify uncertain lines with TrOCR (CPU cost control)
            if conf < self.TROCR_CONF_THRESHOLD:
                trocr_text, trocr_conf = self._trocr_read(crop)
            else:
                trocr_text, trocr_conf = "", 0.0

            final, confidence = self._resolve(text, conf, trocr_text, trocr_conf)
            lines.append({
                "box": box,
                "text": final,
                "paddle_text": text,
                "paddle_conf": conf,
                "trocr_text": trocr_text,
                "trocr_conf": trocr_conf,
                "confidence": confidence,
            })
        return lines

    # ------------------------------------------------------------------ #
    #  Helpers
    # ------------------------------------------------------------------ #
    def _crop_box(self, image, box):
        xs = [int(p[0]) for p in box]
        ys = [int(p[1]) for p in box]
        pad = 4
        x1, y1 = max(min(xs) - pad, 0), max(min(ys) - pad, 0)
        x2, y2 = min(max(xs) + pad, image.shape[1]), min(max(ys) + pad, image.shape[0])
        crop = image[y1:y2, x1:x2]
        if crop.size == 0:
            return crop
        return upscale_for_trocr(crop)

    @torch.inference_mode()
    def _trocr_read(self, crop) -> tuple[str, float]:
        if crop is None or crop.size == 0:
            return "", 0.0

        rgb = cv2.cvtColor(crop, cv2.COLOR_BGR2RGB)
        inputs = self.trocr_proc(images=rgb, return_tensors="pt").to(self.device)

        out = self.trocr.generate(
            **inputs,
            max_length=64,
            output_scores=True,
            return_dict_in_generate=True,
        )

        text = self.trocr_proc.batch_decode(
            out.sequences, skip_special_tokens=True
        )[0].strip()

        # Confidence = mean of per-step top-1 softmax probs (drops final EOS step)
        conf = 0.0
        scores = getattr(out, "scores", None)
        if scores:
            step_probs = []
            for step_logits in scores:
                probs = torch.softmax(step_logits, dim=-1)
                step_probs.append(float(probs.max(dim=-1).values.mean()))
            if step_probs:
                conf = float(np.mean(step_probs[:-1])) if len(step_probs) > 1 \
                    else float(step_probs[0])

        return text, conf

    def _resolve(self, paddle_text, paddle_conf, trocr_text, trocr_conf):
        # Rule 1: agreement -> accept
        if paddle_text.strip().upper() == trocr_text.strip().upper() and trocr_text:
            return trocr_text, max(paddle_conf, trocr_conf)
        # Rule 2: Paddle confident -> keep it
        if paddle_conf >= self.TROCR_CONF_THRESHOLD:
            return paddle_text, paddle_conf
        # Rule 3: disagreement + Paddle unsure -> trust TrOCR
        if trocr_text:
            return trocr_text, trocr_conf
        return paddle_text, paddle_conf