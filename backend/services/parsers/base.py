import re


class BaseParser:
    """Contract for document parsers.

    RULES:
      1. Every field is read from OCR text. No defaults, no fabrication.
      2. A missing field is stored as None — never a placeholder string.
      3. parse() must return via self._finalize(fields, confidence).
      4. _finalize() fails the parse if any REQUIRED_FIELD is None.
    """

    document_type: str = "unknown"
    REQUIRED_FIELDS: list[str] = []

    def parse(self, lines: list, full_text: str) -> dict:
        raise NotImplementedError

    def _grab(self, pattern: str, text: str, group: int = 1,
              flags: int = re.IGNORECASE) -> str | None:
        m = re.search(pattern, text, flags)
        if not m:
            return None
        val = (m.group(group) or "").strip()
        return val or None

    def _finalize(self, fields: dict, confidence: float = 0.0) -> dict:
        # Normalize empty strings / whitespace to None.
        for k, v in list(fields.items()):
            if isinstance(v, str):
                v = v.strip()
                if v == "" or v.upper() in ("UNKNOWN", "N/A", "NA", "NULL"):
                    fields[k] = None
                else:
                    fields[k] = v

        missing = [k for k in self.REQUIRED_FIELDS if fields.get(k) is None]
        if missing:
            return {
                "success": False,
                "error": f"Parser could not locate required fields: {missing}",
                "document_type": self.document_type,
                "fields": fields,
                "confidence": confidence,
            }

        return {
            "success": True,
            "document_type": self.document_type,
            "fields": fields,
            "confidence": confidence,
        }


# Backwards-compatible alias — parsers import DocumentParser.
DocumentParser = BaseParser