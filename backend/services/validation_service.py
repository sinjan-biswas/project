from datetime import datetime
import re


class ValidationService:
    """Per-document-type validation dispatcher.

    - Passport → strict MRZ-style checks (6-digit YYMMDD dates, expiry, blacklist)
    - Other types → REQUIRED-fields + expiry check

    Rule: a missing/uncertain field is a validation ERROR. Never fake-fill.
    """

    # Required fields per document type (keys must match what your parsers emit)
    REQUIRED = {
        "passport":        ["name", "passport_number", "date_of_birth",
                            "date_of_expiry", "nationality"],
        "visa":            ["visa_number", "visa_type"],
        "aadhaar":         ["aadhaar_number", "name"],
        "pan":             ["pan_number", "name"],
        "voter_id":        ["epic_number", "name"],
        "driving_license": ["dl_number", "name"],
        "permit":          ["permit_number"],
        "national_id":     ["name", "document_number"],
    }

    # Field name that holds the expiry date, per document type
    EXPIRY_KEY = {
        "passport":        "date_of_expiry",
        "visa":            "valid_until",
        "driving_license": "validity_to",
        "permit":          "expiry_date",
        "national_id":     "date_of_expiry",
    }

    def __init__(self):
        self.blacklist_db = set()

    # ------------------------------------------------------------------ #
    #  Public dispatcher
    # ------------------------------------------------------------------ #
    def validate(self, ocr_data: dict) -> dict:
        """Entry point used by main.py.

        Accepts the whole ocr_data dict (from OCRService.extract) and
        routes to the right validator based on document_type.
        """
        doc_type = (ocr_data.get("document_type") or "passport").lower()
        fields = ocr_data.get("fields") or {}

        # Backwards-compat: if fields is empty but top-level keys look like MRZ,
        # treat the whole dict as the field bag (old MRZ-style callers).
        if not fields:
            fields = {k: v for k, v in ocr_data.items()
                      if k not in ("success", "error", "document_type",
                                   "ocr_lines", "raw_text", "engine",
                                   "classification_confidence")}

        if doc_type == "passport":
            return self._validate_passport(fields)

        return self._validate_generic(doc_type, fields)

    # ------------------------------------------------------------------ #
    #  Passport (MRZ-aware)
    # ------------------------------------------------------------------ #
    def _validate_passport(self, fields: dict) -> dict:
        errors = []

        for req in self.REQUIRED["passport"]:
            val = fields.get(req)
            if not val or val == "UNKNOWN":
                errors.append(f"Missing {req}")

        expiry_str = fields.get("date_of_expiry")
        if expiry_str and expiry_str != "UNKNOWN":
            expiry_str = self._fix_ocr_date(expiry_str)
            fields["date_of_expiry"] = expiry_str
            errors.extend(self._check_date(expiry_str, "expiry",
                                           future_ok=False))

        dob_str = fields.get("date_of_birth")
        if dob_str and dob_str != "UNKNOWN":
            dob_str = self._fix_ocr_date(dob_str)
            fields["date_of_birth"] = dob_str
            errors.extend(self._check_date(dob_str, "DOB", future_ok=True))

        doc_num = fields.get("passport_number") or fields.get("document_number")
        if doc_num and doc_num in self.blacklist_db:
            errors.append("Document blacklisted")

        return {
            "valid": not errors,
            "errors": errors,
            "document_type": "passport",
            "expiry_date": fields.get("date_of_expiry"),
        }

    # ------------------------------------------------------------------ #
    #  Generic validator (visa / aadhaar / pan / voter_id / dl / permit)
    # ------------------------------------------------------------------ #
    def _validate_generic(self, doc_type: str, fields: dict) -> dict:
        errors = []

        for req in self.REQUIRED.get(doc_type, []):
            val = fields.get(req)
            if not val or val == "UNKNOWN":
                errors.append(f"Missing {req}")

        expiry_key = self.EXPIRY_KEY.get(doc_type)
        expiry_val = None
        if expiry_key and fields.get(expiry_key):
            expiry_val = self._normalize_date(fields[expiry_key])
            fields[expiry_key] = expiry_val
            errors.extend(self._check_flexible_date(expiry_val, "expiry"))

        # Blacklist check across every number-like field
        for k, v in fields.items():
            if v and isinstance(v, str) and v in self.blacklist_db:
                errors.append(f"{k} blacklisted")
                break

        return {
            "valid": not errors,
            "errors": errors,
            "document_type": doc_type,
            "expiry_date": expiry_val,
        }

    # ------------------------------------------------------------------ #
    #  Date helpers
    # ------------------------------------------------------------------ #
    def _fix_ocr_date(self, date_str: str) -> str:
        """Repair common OCR month/day swaps on 6-digit YYMMDD strings.

        No hard-coded document-specific fixes — the previous table was
        silently rewriting real document dates to a single hard-coded
        value, which defeats the purpose of validation.
        """
        if not date_str or len(date_str) != 6 or not date_str.isdigit():
            return date_str

        yy, mm, dd = int(date_str[0:2]), int(date_str[2:4]), int(date_str[4:6])

        # Case 1: month > 12 but day is a valid month → swap
        if mm > 12 and 1 <= dd <= 12:
            return f"{yy:02d}{dd:02d}{mm:02d}"

        # Case 2: day > 31 but month is a valid day → swap
        if dd > 31 and 1 <= mm <= 31:
            return f"{yy:02d}{dd:02d}{mm:02d}"

        return date_str

    def _check_date(self, date_str: str, label: str, future_ok: bool):
        """Validate a 6-digit YYMMDD (MRZ style). Returns list of errors."""
        errors = []
        if not (len(date_str) == 6 and date_str.isdigit()):
            errors.append(f"Invalid {label} date format: {date_str}")
            return errors

        yy, mm, dd = int(date_str[0:2]), int(date_str[2:4]), int(date_str[4:6])
        year = yy + (2000 if yy < 50 else 1900)

        dt = None
        try:
            if 1 <= mm <= 12 and 1 <= dd <= 31:
                dt = datetime(year, mm, dd)
            elif 1 <= dd <= 12 and 1 <= mm <= 31:
                dt = datetime(year, dd, mm)
        except ValueError:
            pass

        if dt is None:
            errors.append(f"Invalid {label} date values: {date_str}")
            return errors

        if label == "expiry" and dt < datetime.now():
            errors.append("Document expired")
        elif label == "DOB" and not future_ok and dt >= datetime.now():
            errors.append("DOB in future (unusual)")

        return errors

    def _normalize_date(self, date_str: str) -> str:
        """Normalize a flexible date (DD/MM/YYYY, DD-MM-YYYY, YYYY-MM-DD)
        to ISO YYYY-MM-DD. Returns the original on failure."""
        if not date_str:
            return date_str
        for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%d.%m.%Y",
                    "%d/%m/%y", "%d-%m-%y"):
            try:
                return datetime.strptime(date_str, fmt).strftime("%Y-%m-%d")
            except ValueError:
                continue
        return date_str

    def _check_flexible_date(self, date_str: str, label: str):
        """Validate an already-normalized ISO date."""
        errors = []
        try:
            dt = datetime.strptime(date_str, "%Y-%m-%d")
        except (ValueError, TypeError):
            errors.append(f"Invalid {label} date: {date_str}")
            return errors

        if label == "expiry" and dt < datetime.now():
            errors.append("Document expired")
        return errors