# backend/services/document_classifier.py
import json
from pathlib import Path

import cv2
import numpy as np
import torch
import torch.nn as nn
from torchvision.models import efficientnet_b0


class DocumentClassifier:
    """EfficientNet-B0 classifier for ID document type.

    Loads weights from MODELS_DIR/doc_classifier.pt plus a .json sidecar
    containing class order and preprocessing constants. Falls back to a
    structural heuristic if the checkpoint is absent.

    Guards against garbage input:
      * low-information images (blank / uniform) are rejected before
        the network sees them,
      * a margin check between top-1 and top-2 is required so the
        classifier cannot pick a class by coin-flip.
    """

    MODEL_PATH = Path("models/doc_classifier.pt")
    META_PATH  = Path("models/doc_classifier.json")

    # Classifier must be at least this confident AND beat the runner-up
    # by MARGIN, otherwise we say "others".
    CONF_THRESHOLD   = 0.70
    MARGIN_THRESHOLD = 0.15

    # Below this pixel std-dev the image is effectively uniform.
    # Pure white / pure black / solid gray all land here.
    MIN_IMAGE_STD    = 8.0

    def __init__(self, model_path: str | Path | None = None):
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        self.model: nn.Module | None = None
        self.classes: list[str] = []
        self.mean = [0.485, 0.456, 0.406]
        self.std  = [0.229, 0.224, 0.225]
        self.input_size = 224
        self._load(Path(model_path) if model_path else self.MODEL_PATH)

    # ------------------------------------------------------------------ #
    #  Load
    # ------------------------------------------------------------------ #
    def _load(self, model_path: Path):
        meta_path = model_path.with_suffix(".json")

        if not model_path.exists():
            print(f"[DocumentClassifier] no checkpoint at {model_path} "
                  f"— using heuristic fallback")
            return
        if not meta_path.exists():
            print(f"[DocumentClassifier] missing {meta_path}; cannot "
                  f"guarantee class order — skipping CNN load")
            return

        meta = json.loads(meta_path.read_text())
        self.classes    = meta["classes"]
        self.mean       = meta.get("imagenet_mean", self.mean)
        self.std        = meta.get("imagenet_std",  self.std)
        self.input_size = meta.get("input_size", 224)

        model = efficientnet_b0(weights=None)
        model.classifier[1] = nn.Linear(
            model.classifier[1].in_features, len(self.classes),
        )
        state = torch.load(model_path, map_location=self.device)
        model.load_state_dict(state)
        model.eval().to(self.device)

        self.model = model
        print(f"[DocumentClassifier] loaded {model_path.name} — "
              f"{len(self.classes)} classes, "
              f"val_acc={meta.get('val_acc'):.3f}")

    # ------------------------------------------------------------------ #
    #  Classify
    # ------------------------------------------------------------------ #
    def classify(self, image: np.ndarray) -> dict:
        # ---- 0. Blank / low-information guard -----------------------
        # A uniform image has nothing to classify. Reject before the
        # network sees it so we don't get a "passport 79%" on white.
        if self._is_low_information(image):
            return {
                "document_type": "others",
                "confidence": 0.0,
                "top_k": [],
                "reason": "low-information image (blank/uniform)",
            }

        if self.model is None:
            return self._heuristic_fallback(image)

        inp = self._preprocess(image)
        with torch.inference_mode():
            probs = torch.softmax(self.model(inp), dim=-1)[0].cpu().numpy()

        # ---- 1. Margin check ----------------------------------------
        # top1 must beat top2 by MARGIN, else it's a coin flip.
        order = np.argsort(probs)[::-1]
        top1_idx, top2_idx = int(order[0]), int(order[1])
        top1_prob = float(probs[top1_idx])
        top2_prob = float(probs[top2_idx])
        margin = top1_prob - top2_prob

        if top1_prob < self.CONF_THRESHOLD or margin < self.MARGIN_THRESHOLD:
            return {
                "document_type": "others",
                "confidence": top1_prob,
                "top_k": self._top_k(probs, k=3),
                "reason": (
                    f"low confidence (top1={top1_prob:.2f}, "
                    f"margin={margin:.2f})"
                ),
            }

        return {
            "document_type": self.classes[top1_idx],
            "confidence": top1_prob,
            "top_k": self._top_k(probs, k=3),
        }

    # ------------------------------------------------------------------ #
    #  Low-information detector
    # ------------------------------------------------------------------ #
    @classmethod
    def _is_low_information(cls, image: np.ndarray) -> bool:
        """True when the image is essentially uniform (blank/white/black).

        Uses grayscale std-dev plus a coarse unique-value count.
        Both must be low for the check to fire — a high-contrast photo
        with a large white background still passes.
        """
        if image is None or image.size == 0:
            return True
        try:
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        except cv2.error:
            return True

        std = float(gray.std())
        if std >= cls.MIN_IMAGE_STD:
            return False

        # Second opinion: bucket pixel values into 8 bins and count
        # how many bins hold >1% of the pixels. Uniform images use 1 bin.
        hist = cv2.calcHist([gray], [0], None, [8], [0, 256]).flatten()
        hist /= max(hist.sum(), 1.0)
        significant_bins = int((hist > 0.01).sum())
        return significant_bins <= 1

    # ------------------------------------------------------------------ #
    #  Preprocess / helpers
    # ------------------------------------------------------------------ #
    def _preprocess(self, image: np.ndarray) -> torch.Tensor:
        img = cv2.resize(image, (self.input_size, self.input_size))
        img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB).astype(np.float32) / 255.0
        img = (img - np.array(self.mean, dtype=np.float32)) \
            / np.array(self.std, dtype=np.float32)
        img = np.transpose(img, (2, 0, 1))
        return torch.from_numpy(img).unsqueeze(0).to(self.device)

    def _top_k(self, probs: np.ndarray, k: int = 3) -> list[dict]:
        idx = np.argsort(probs)[::-1][:k]
        return [{"label": self.classes[i], "prob": float(probs[i])}
                for i in idx]

    # ------------------------------------------------------------------ #
    #  Heuristic fallback (no CNN checkpoint)
    # ------------------------------------------------------------------ #
    def _heuristic_fallback(self, image: np.ndarray) -> dict:
        if self._is_low_information(image):
            return {"document_type": "others", "confidence": 0.0,
                    "top_k": [], "reason": "low-information image"}

        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        h = gray.shape[0]
        region = gray[int(h * 0.55):, :]
        _, bw = cv2.threshold(region, 0, 255,
                              cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
        rows = (bw > 0).sum(axis=1)
        dense = (rows > region.shape[1] * 0.4).sum()
        if dense >= 6:
            return {"document_type": "passport", "confidence": 0.4,
                    "top_k": []}
        return {"document_type": "others", "confidence": 0.3, "top_k": []}