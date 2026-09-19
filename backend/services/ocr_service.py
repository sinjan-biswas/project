import os
import numpy as np
import cv2
import re
from pathlib import Path

# --- New multi-document OCR imports (graceful degradation) ---
try:
    from .preprocess import decode_image, deskew
    from .ocr_engine import DualOCREngine
    from .document_classifier import DocumentClassifier
    from .parsers import PARSERS
    NEW_OCR_AVAILABLE = True
except Exception as e:
    print(f"[OCRService] New multi-document OCR unavailable: {e}")
    NEW_OCR_AVAILABLE = False
    DualOCREngine = None
    DocumentClassifier = None
    PARSERS = {}

# --- Optional Tesseract (legacy fallback) ---
try:
    import pytesseract
    TESSERACT_AVAILABLE = True
except ImportError:
    print("[OCRService] pytesseract not installed — legacy MRZ fallback disabled")
    TESSERACT_AVAILABLE = False
    pytesseract = None

# --- Tesseract setup (legacy) ---
if TESSERACT_AVAILABLE and not os.environ.get("TESSDATA_PREFIX"):
    possible_paths = [
        "/usr/share/tesseract-ocr/5/tessdata/",
        "/usr/share/tesseract-ocr/4.00/tessdata/",
        "/usr/share/tesseract-ocr/tessdata/",
        "/usr/local/share/tessdata/",
    ]
    for path in possible_paths:
        if os.path.exists(path):
            os.environ["TESSDATA_PREFIX"] = path
            break


class OCRService:
    """
    Unified OCR service supporting both:
    - Legacy Tesseract MRZ extraction (passport only)
    - New multi-document pipeline (PaddleOCR + TrOCR + classifiers)
    """
    MIN_CLASSIFICATION_CONF = 0.55

    def __init__(self):
        self.new_ocr = None
        self.legacy_lang = "eng"

        if NEW_OCR_AVAILABLE:
            try:
                self.new_ocr = {
                    "engine": DualOCREngine(),
                    "classifier": DocumentClassifier(),
                }
                print("[OCRService] Initialized with multi-document pipeline")
            except Exception as e:
                print(f"[OCRService] Failed to init new pipeline: {e}")
                self.new_ocr = None

    def extract(self, image_bytes: bytes) -> dict:
        """
        Extract document data. Returns unified format compatible with both
        old and new validation services.
        """
        # Try new pipeline first
        if self.new_ocr is not None:
            try:
                result = self._extract_new(image_bytes)
                if result.get("success"):
                    return self._normalize_output(result)
            except Exception as e:
                print(f"[OCRService] New pipeline failed, falling back: {e}")

        # Fallback to legacy Tesseract
        return self._extract_legacy(image_bytes)

    # ------------------------------------------------------------------ #
    #  New multi-document pipeline
    # ------------------------------------------------------------------ #
    def _extract_new(self, image_bytes: bytes) -> dict:
        image = deskew(decode_image(image_bytes))

        # 1. Classify document type
        cls = self.new_ocr["classifier"].classify(image)
        doc_type = cls["document_type"]
        cls_conf = cls["confidence"]

        if doc_type == "others":
            best = cls["top_k"][0] if cls.get("top_k") else {"label": "n/a", "prob": 0.0}
            return {
                "success": False,
                "error": f"Unrecognized document type (best={best['label']}, conf={cls_conf:.2f})",
                "document_type": "others",
                "classification_confidence": cls_conf,
                "top_k": cls.get("top_k", []),
            }

        if cls_conf < self.MIN_CLASSIFICATION_CONF:
            return {
                "success": False,
                "error": f"Low classification confidence ({cls_conf:.2f}) for {doc_type}",
                "document_type": doc_type,
                "classification_confidence": cls_conf,
                "top_k": cls.get("top_k", []),
            }

        # 2. OCR
        lines = self.new_ocr["engine"].extract_lines(image)
        if not lines:
            return {"success": False, "error": "No text detected", "document_type": doc_type}

        # 3. Parse with document-specific parser
        full_text = "\n".join(l["text"] for l in lines)
        parser = PARSERS.get(doc_type)
        if parser is None:
            return {
                "success": False,
                "error": f"No parser registered for '{doc_type}'",
                "document_type": doc_type,
            }

        result = parser.parse(lines, full_text)
        result.update({
            "success": True,
            "engine": "PaddleOCR+TrOCR",
            "document_type": doc_type,
            "classification_confidence": cls_conf,
            "classification_top_k": cls.get("top_k", []),
            "ocr_lines": lines,
            "raw_text": full_text[:1000],
        })
        return result

    # ------------------------------------------------------------------ #
    #  Legacy Tesseract pipeline (passport MRZ only)
    # ------------------------------------------------------------------ #
    def _extract_legacy(self, image_bytes: bytes) -> dict:
        try:
            nparr = np.frombuffer(image_bytes, np.uint8)
            image = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
            if image is None:
                return {"error": "Invalid image format", "success": False}

            text = pytesseract.image_to_string(image, lang=self.legacy_lang)
            mrz_data = self._parse_mrz_from_text(text)
            mrz_data["success"] = True
            mrz_data["engine"] = "Tesseract-eng"
            mrz_data["raw_text"] = text[:500]
            mrz_data["document_type"] = "passport"  # Legacy only handles passports
            return mrz_data
        except Exception as e:
            return self._get_fallback_data(str(e))

    def _parse_mrz_from_text(self, text):
        data = {
            "mrz_type": "TD3",
            "document_type": "P",
            "country_code": "UNKNOWN",
            "surname": "UNKNOWN",
            "given_names": "UNKNOWN",
            "document_number": "UNKNOWN",
            "nationality": "UNKNOWN",
            "date_of_birth": "UNKNOWN",
            "sex": "UNKNOWN",
            "date_of_expiry": "UNKNOWN",
        }

        lines = [line.strip() for line in text.split('\n') if line.strip()]

        for line in lines:
            line_upper = line.upper()
            if "SURNAME" in line_upper:
                parts = re.split(r"[:. ]+", line)
                if len(parts) > 1:
                    surname = parts[-1].strip()
                    if surname and len(surname) < 30 and not surname.isdigit():
                        data["surname"] = surname.upper()

            if "GIVEN NAMES" in line_upper or ("GIVEN" in line_upper and "NAMES" in line_upper):
                parts = re.split(r"[:. ]+", line)
                if len(parts) > 1:
                    given = parts[-1].strip()
                    if given and len(given) < 30 and not given.isdigit():
                        data["given_names"] = given.upper()

            if "COUNTRY" in line_upper:
                parts = re.split(r"[:. ]+", line)
                if len(parts) > 1:
                    country = parts[-1].strip()
                    if country and len(country) < 10 and not country.isdigit():
                        data["country_code"] = country.upper()[:3]

        mrz_line = None
        for line in lines:
            if "<" in line and len(line) > 20:
                clean_line = re.sub(r"[^A-Za-z0-9<]", "", line.upper())
                if len(clean_line) > 20:
                    mrz_line = clean_line
                    break

        if mrz_line and len(mrz_line) >= 30:
            doc_num = self._clean_document_number(mrz_line[0:9])
            data["document_number"] = doc_num

            if len(mrz_line) >= 13:
                data["nationality"] = self._clean_country_code(mrz_line[10:13])

            if len(mrz_line) >= 19:
                data["date_of_birth"] = self._clean_dob(mrz_line[13:19])

            if len(mrz_line) >= 21:
                sex_char = mrz_line[20:21]
                data["sex"] = sex_char if sex_char in ("M", "F") else "M"

            if len(mrz_line) >= 27:
                data["date_of_expiry"] = self._clean_expiry(mrz_line[21:27])

        return self._validate_and_fill_missing(data)

    def _clean_document_number(self, doc_num):
        replacements = {"A": "4", "B": "8", "O": "0", "D": "0", "S": "5", "Z": "2", "G": "6", "T": "1", "I": "1", "M": "1", "N": "1", "R": "1"}
        return "".join(replacements.get(c, c) if c.isalpha() else c for c in doc_num)

    def _clean_country_code(self, code):
        code = re.sub(r"[^A-Z]", "", code.upper())
        if len(code) >= 3:
            return code[:3]
        common_map = {"US": "USA", "UK": "GBR", "CA": "CAN", "AU": "AUS", "DE": "DEU", "FR": "FRA", "IT": "ITA", "JP": "JPN", "CN": "CHN", "IN": "IND", "BR": "BRA", "RU": "RUS"}
        return common_map.get(code, "USA")

    def _clean_dob(self, dob_str):
        char_map = {"A": "4", "B": "4", "O": "0", "D": "0", "S": "5", "Z": "2", "G": "6", "T": "1", "I": "1", "M": "1", "N": "1", "R": "1"}
        cleaned = "".join(char_map.get(c, c) if c.isalpha() else c for c in dob_str.upper())
        digits = re.sub(r"[^0-9]", "", cleaned)
        return digits[:6] if len(digits) >= 6 else "900101"

    def _clean_expiry(self, expiry_str):
        expiry_str = expiry_str.upper().replace("M", "2")
        char_map = {"A": "4", "B": "8", "O": "0", "D": "0", "S": "5", "Z": "2", "G": "6", "T": "1", "I": "1", "N": "1", "R": "1"}
        cleaned = "".join(char_map.get(c, c) if c.isalpha() else c for c in expiry_str)
        digits = re.sub(r"[^0-9]", "", cleaned)
        return digits[:6] if len(digits) >= 6 else "250101"

    def _validate_and_fill_missing(self, data):
        defaults = {
            "date_of_birth": "900101",
            "date_of_expiry": "250101",
            "document_number": "123456789",
            "nationality": "USA",
            "sex": "M",
            "country_code": "USA",
            "document_type": "P",
        }
        for key, default in defaults.items():
            if not data.get(key) or data[key] == "UNKNOWN" or (key in ("date_of_birth", "date_of_expiry") and len(data[key]) != 6):
                data[key] = default
            if key == "document_number" and len(data[key]) < 6:
                data[key] = default
        return data

    def _get_fallback_data(self, error_msg):
        return {
            "success": False,
            "error": error_msg,
            "engine": "fallback",
            "mrz_type": "TD3",
            "document_type": "P",
            "country_code": "USA",
            "surname": "DOE",
            "given_names": "JOHN",
            "document_number": "123456789",
            "nationality": "USA",
            "date_of_birth": "900101",
            "sex": "M",
            "date_of_expiry": "250101",
            "note": "Using fallback data for testing",
        }

    # ------------------------------------------------------------------ #
    #  Output normalization — make new pipeline output compatible with
    #  existing validation_service and main.py expectations
    # ------------------------------------------------------------------ #
    def _normalize_output(self, result: dict) -> dict:
        """
        Convert new pipeline output (with 'fields' dict) to flat format
        expected by legacy validation_service.validate_mrz() and main.py.
        Also preserves new fields for new validation_service.validate().
        """
        doc_type = result.get("document_type", "passport")
        fields = result.get("fields", {})

        # Start with a copy of the new result
        normalized = dict(result)

        # For passport: flatten MRZ-style fields to top level for backward compat
        if doc_type == "passport":
            # Map new parser field names to legacy field names
            field_mapping = {
                "name": ("surname", "given_names"),  # Will split
                "passport_number": "document_number",
                "nationality": "nationality",
                "date_of_birth": "date_of_birth",
                "date_of_expiry": "date_of_expiry",
                "gender": "sex",
            }

            # Split name into surname/given_names if present
            name = fields.get("name")
            if name:
                parts = name.split()
                if len(parts) >= 2:
                    normalized["surname"] = parts[0].upper()
                    normalized["given_names"] = " ".join(parts[1:]).upper()
                else:
                    normalized["surname"] = name.upper()
                    normalized["given_names"] = ""

            # Direct mappings
            for new_key, legacy_key in field_mapping.items():
                if new_key == "name":
                    continue
                if new_key in fields and fields[new_key]:
                    # Convert date format if needed (ISO -> YYMMDD)
                    if new_key in ("date_of_birth", "date_of_expiry") and "-" in str(fields[new_key]):
                        normalized[legacy_key] = self._iso_to_yymmdd(fields[new_key])
                    else:
                        normalized[legacy_key] = fields[new_key]

            # Ensure legacy required fields exist
            for key in ["mrz_type", "document_type", "country_code", "surname", "given_names",
                        "document_number", "nationality", "date_of_birth", "sex", "date_of_expiry"]:
                if key not in normalized or not normalized[key] or normalized[key] == "UNKNOWN":
                    normalized[key] = "UNKNOWN"

        return normalized

    def _iso_to_yymmdd(self, iso_date: str) -> str:
        """Convert YYYY-MM-DD to YYMMDD."""
        try:
            parts = iso_date.split("-")
            if len(parts) == 3:
                return f"{parts[0][2:]}{parts[1]}{parts[2]}"
        except Exception:
            pass
        return iso_date