import os
import re
import json
import numpy as np
import cv2
import onnxruntime as ort


class DocumentClassifier:
    """Singleton, mirrors FaceVerificationService pattern."""

    _instance = None
    _initialized = False

    CONFIDENCE_THRESHOLD = 0.55

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if self._initialized:
            return

        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        model_dir = os.path.join(base_dir, "models", "document_classifier")
        self.model_path = os.path.join(model_dir, "document_classifier.onnx")
        self.labels_path = os.path.join(model_dir, "labels.json")

        self.input_size = 224
        self.imagenet_mean = np.array([0.485, 0.456, 0.406], dtype=np.float32)
        self.imagenet_std = np.array([0.229, 0.224, 0.225], dtype=np.float32)

        self.session = None
        self.labels = []

        env_thr = os.getenv("DOC_CLASSIFIER_THRESHOLD")
        if env_thr:
            try:
                self.CONFIDENCE_THRESHOLD = float(env_thr)
            except ValueError:
                pass

        if os.path.exists(self.model_path) and os.path.exists(self.labels_path):
            with open(self.labels_path) as f:
                self.labels = json.load(f)
            providers = ["CUDAExecutionProvider", "CPUExecutionProvider"]
            available = ort.get_available_providers()
            self.session = ort.InferenceSession(
                self.model_path,
                providers=[p for p in providers if p in available],
            )
            print(f"[DocumentClassifier] CNN loaded: {self.model_path}")
            print(f"[DocumentClassifier] providers={self.session.get_providers()}, classes={self.labels}")
            print(f"[DocumentClassifier] confidence threshold = {self.CONFIDENCE_THRESHOLD}")
        else:
            print("[DocumentClassifier] model not found under backend/models/document_classifier/")
            print("[DocumentClassifier] running in HEURISTIC mode (train + export a model to enable CNN)")

        self._initialized = True

    def classify(self, image_bytes: bytes):
        if self.session is not None:
            return self._cnn_classify(image_bytes)
        return self._heuristic_classify(image_bytes)

    def _cnn_classify(self, image_bytes: bytes):
        x = self._preprocess(image_bytes)
        if x is None:
            return self._result("unknown", 0.0, "invalid image", heuristic=True)

        input_name = self.session.get_inputs()[0].name
        logits = self.session.run(None, {input_name: x})[0][0]
        probs = self._softmax(logits)
        top = int(np.argmax(probs))
        top_confidence = float(probs[top])

        # Bug A: gate on confidence. Below threshold, refuse to name a class.
        if top_confidence < self.CONFIDENCE_THRESHOLD:
            doc_type = "unknown"
        else:
            doc_type = self.labels[top] if top < len(self.labels) else "unknown"

        all_scores = {
            self.labels[i]: round(float(probs[i]), 4)
            for i in range(min(len(self.labels), len(probs)))
        }
        return self._result(
            doc_type,
            top_confidence,
            f"cnn/onnx ({self.session.get_providers()[0]})",
            heuristic=False,
            all_scores=all_scores,
        )

    def _preprocess(self, image_bytes: bytes):
        nparr = np.frombuffer(image_bytes, np.uint8)
        img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        if img is None:
            return None
        img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        img = cv2.resize(img, (self.input_size, self.input_size))
        img = img.astype(np.float32) / 255.0
        img = (img - self.imagenet_mean) / self.imagenet_std
        return np.ascontiguousarray(img.transpose(2, 0, 1)[np.newaxis, ...], dtype=np.float32)

    @staticmethod
    def _softmax(logits):
        logits = logits - np.max(logits)
        e = np.exp(logits)
        return e / np.sum(e)

    def _heuristic_classify(self, image_bytes: bytes):
        import pytesseract

        try:
            nparr = np.frombuffer(image_bytes, np.uint8)
            img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
            text = pytesseract.image_to_string(img).upper()
        except Exception:
            # Bug A: never fabricate a label on failure.
            return self._result("unknown", 0.0, "heuristic (ocr failed)", heuristic=True)

        if "AADHAAR" in text or re.search(r"\d{4}\s\d{4}\s\d{4}", text):
            doc_type = "aadhaar"
        elif re.search(r"\b[A-Z]{5}[0-9]{4}[A-Z]\b", text):
            doc_type = "pan"
        elif re.search(r"\b[A-Z]{3}[0-9]{7}\b", text) or "ELECTOR" in text:
            doc_type = "voter_id"
        elif "DRIVING LICEN" in text or "DRIVE LICEN" in text or "DL NO" in text:
            doc_type = "driving_license"
        elif "VISA" in text:
            doc_type = "visa"
        else:
            lines = [re.sub(r"[^A-Z0-9<]", "", l) for l in text.splitlines()]
            td1 = [l for l in lines if 28 <= len(l) <= 31]
            td3 = [l for l in lines if len(l) >= 42]
            if len(td1) >= 3:
                doc_type = "national_id"
            elif td3 and td3[0].startswith("V"):
                doc_type = "visa"
            else:
                doc_type = "passport"

        return self._result(doc_type, 0.35, "heuristic (no model)", heuristic=True)

    @staticmethod
    def _result(doc_type, confidence, source, heuristic, all_scores=None):
        return {
            "document_type": doc_type,
            "confidence": round(confidence, 4),
            "source": source,
            "heuristic": heuristic,
            "all_scores": all_scores or {},
        }