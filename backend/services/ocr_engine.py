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


def _paddle_cuda_available() -> bool:
    try:
        import paddle
        return bool(paddle.device.is_compiled_with_cuda())
    except Exception as e:
        print(f"[ocr_engine] paddle CUDA check failed: {e}")
        return False


class DualOCREngine:
    TROCR_CONF_THRESHOLD = 0.70

    def __init__(self):
        use_gpu = _paddle_cuda_available()
        print(f"[ocr_engine] PaddleOCR gpu={use_gpu}, "
              f"version_major={_paddle_major_version()}")

        if _paddle_major_version() >= 3:
            self.paddle = PaddleOCR(
                use_textline_orientation=True,
                lang="en",
                device="gpu:0" if use_gpu else "cpu",
            )
            self._paddle_v3 = True
        else:
            self.paddle = PaddleOCR(
                use_angle_cls=True,
                lang="en",
                show_log=False,
                use_gpu=use_gpu,
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
        print(f"[ocr_engine] TrOCR device={self.device}")

    def _paddle_ocr(self, image) -> list[tuple]:
        if self._paddle_v3:
            results = self.paddle.predict(image)
            out = []
            for page in results or []:
                polys = page.get("dt_polys") or []
                texts = page.get("rec_texts") or []
                scores = page.get("rec_scores") or []
                for box, text, conf in zip(polys, texts, scores):
                    out.append((box, text, float(conf)))
            return out

        raw = self.paddle.ocr(image, cls=True)
        out = []
        for page in raw or []:
            for box, (text, conf) in page or []:
                out.append((box, text, float(conf)))
        return out

    def probe_confidence(self, image) -> float:
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

    def extract_lines(self, image) -> list[dict]:
        paddle_pairs = self._paddle_ocr(image)

        needs_trocr = []
        lines: list[dict] = []
        for box, text, conf in paddle_pairs:
            idx = len(lines)
            if conf < self.TROCR_CONF_THRESHOLD:
                crop = self._crop_box(image, box)
                needs_trocr.append((idx, crop))
                trocr_text, trocr_conf = None, None
            else:
                trocr_text, trocr_conf = "", 0.0
            lines.append({
                "box": box,
                "text": text,
                "paddle_text": text,
                "paddle_conf": conf,
                "trocr_text": trocr_text,
                "trocr_conf": trocr_conf,
                "confidence": conf,
            })

        if needs_trocr:
            crops = [c for _idx, c in needs_trocr]
            trocr_results = self._trocr_read_batch(crops)
            for (idx, _crop), (tt, tc) in zip(needs_trocr, trocr_results):
                lines[idx]["trocr_text"] = tt
                lines[idx]["trocr_conf"] = tc

        for ln in lines:
            final, conf = self._resolve(
                ln["paddle_text"], ln["paddle_conf"],
                ln["trocr_text"] or "", ln["trocr_conf"] or 0.0,
            )
            ln["text"] = final
            ln["confidence"] = conf

        return lines

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
    def _trocr_read_batch(self, crops: list) -> list[tuple[str, float]]:
        valid = [(i, c) for i, c in enumerate(crops)
                 if c is not None and getattr(c, "size", 0) > 0]
        results: list[tuple[str, float]] = [("", 0.0)] * len(crops)
        if not valid:
            return results

        rgb_images = [cv2.cvtColor(c, cv2.COLOR_BGR2RGB) for _i, c in valid]
        inputs = self.trocr_proc(
            images=rgb_images, return_tensors="pt", padding=True,
        ).to(self.device)

        out = self.trocr.generate(
            **inputs,
            max_length=64,
            output_scores=True,
            return_dict_in_generate=True,
        )

        texts = self.trocr_proc.batch_decode(out.sequences, skip_special_tokens=True)

        confs: list[float] = []
        scores = getattr(out, "scores", None)
        if scores:
            step_probs = torch.stack(
                [torch.softmax(s, dim=-1).max(dim=-1).values for s in scores],
                dim=0,
            )
            if step_probs.shape[0] > 1:
                step_probs = step_probs[:-1]
            confs = step_probs.mean(dim=0).cpu().tolist()
        else:
            confs = [0.0] * len(texts)

        for (orig_idx, _crop), text, conf in zip(valid, texts, confs):
            results[orig_idx] = (text.strip(), float(conf))

        return results

    def _resolve(self, paddle_text, paddle_conf, trocr_text, trocr_conf):
        if paddle_text.strip().upper() == trocr_text.strip().upper() and trocr_text:
            return trocr_text, max(paddle_conf, trocr_conf)
        if paddle_conf >= self.TROCR_CONF_THRESHOLD:
            return paddle_text, paddle_conf
        if trocr_text:
            return trocr_text, trocr_conf
        return paddle_text, paddle_conf