from .preprocess import decode_image, deskew
from .ocr_engine import DualOCREngine
from .document_classifier import DocumentClassifier
from .parsers import PARSERS


class OCRService:
    MIN_CLASSIFICATION_CONF = 0.55

    def __init__(self):
        self.engine = DualOCREngine()
        self.classifier = DocumentClassifier()
        # NOTE: pytesseract legacy fallback REMOVED. Do not re-add it.

    # ------------------------------------------------------------------ #
    #  NEW — quality-gate probe (Paddle-only, no deskew, no TrOCR)
    # ------------------------------------------------------------------ #
    def probe_confidence(self, image_bytes: bytes) -> float:
        """
        Cheap confidence probe used by ImageQualityGate.

        - Decodes WITHOUT deskewing so the gate can still see tilt.
        - Delegates to DualOCREngine.probe_confidence (PaddleOCR only).
        - Returns 0.0 on any failure — never raises.
        """
        try:
            image = decode_image(image_bytes)
        except ValueError:
            return 0.0
        return self.engine.probe_confidence(image)

    def extract(self, image_bytes: bytes) -> dict:
        # ---- 0. Preprocess -------------------------------------------
        try:
            image = deskew(decode_image(image_bytes))
        except ValueError as e:
            return {"success": False, "error": str(e)}

        # ---- 1. Classify --------------------------------------------
        cls = self.classifier.classify(image)
        doc_type = cls["document_type"]
        cls_conf = cls["confidence"]

        if doc_type == "others":
            top_k = cls.get("top_k") or []
            best = top_k[0] if top_k else {"label": "n/a", "prob": 0.0}
            return {
                "success": False,
                "error": f"Unrecognized document type "
                         f"(best={best['label']}, conf={cls_conf:.2f})",
                "document_type": "others",
                "classification_confidence": cls_conf,
                "top_k": top_k,
            }

        if cls_conf < self.MIN_CLASSIFICATION_CONF:
            return {
                "success": False,
                "error": f"Low classification confidence ({cls_conf:.2f}) "
                         f"for {doc_type}",
                "document_type": doc_type,
                "classification_confidence": cls_conf,
                "top_k": cls.get("top_k", []),
            }

        # ---- 2. OCR -------------------------------------------------
        lines = self.engine.extract_lines(image)
        if not lines:
            return {
                "success": False,
                "error": "No text detected",
                "document_type": doc_type,
                "classification_confidence": cls_conf,
            }

        # ---- 3. Parse ------------------------------------------------
        full_text = "\n".join(l["text"] for l in lines)
        parser = PARSERS.get(doc_type)
        if parser is None:
            return {
                "success": False,
                "error": f"No parser registered for '{doc_type}'",
                "document_type": doc_type,
            }

        result = parser.parse(lines, full_text)

        # Propagate parser failure instead of swallowing it.
        if not result.get("success", False):
            return {
                "success": False,
                "error": result.get("error", "Parser failed"),
                "document_type": doc_type,
                "classification_confidence": cls_conf,
                "parsed_fields": result.get("fields", {}),
                "ocr_lines": lines,
                "raw_text": full_text[:1000],
            }

        # Refuse to call this a success if every field is null.
        fields = result.get("fields") or {}
        non_null = [k for k, v in fields.items()
                    if v not in (None, "", "UNKNOWN")]
        if not non_null:
            return {
                "success": False,
                "error": "Parser returned no non-null fields",
                "document_type": doc_type,
                "classification_confidence": cls_conf,
                "ocr_lines": lines,
                "raw_text": full_text[:1000],
            }

        # Sanity check: reject hard-coded placeholder values.
        suspicious = self._check_placeholders(fields)
        if suspicious:
            return {
                "success": False,
                "error": f"Parser emitted placeholder values: {suspicious}",
                "document_type": doc_type,
                "classification_confidence": cls_conf,
                "parsed_fields": fields,
            }

        result.update({
            "success": True,
            "engine": "PaddleOCR+TrOCR",
            "document_type": doc_type,
            "classification_confidence": cls_conf,
            "classification_top_k": cls.get("top_k", []),
            "ocr_lines": lines,
            "raw_text": full_text[:1000],
            "extracted_field_count": len(non_null),
        })
        return result

    @staticmethod
    def _check_placeholders(fields: dict) -> list[str]:
        """Catch any parser that still fabricates default values."""
        bad = {
            "passport_number": {"123456789", "000000000", "A0000000", "X1234567"},
            "date_of_birth":   {"900101", "000101", "010100"},
            "date_of_expiry":  {"900101", "000101", "010100"},
            "nationality":     {"USA", "XXX"},
            "name":            {"JOHN DOE", "JOHN SMITH", "TEST USER"},
        }
        hits = []
        for k, vals in bad.items():
            v = fields.get(k)
            if isinstance(v, str) and v.upper() in {x.upper() for x in vals}:
                hits.append(k)
        return hits