from datetime import datetime
import os


class ValidationService:
    """Per-document-type validation dispatcher.

    Design rule: NEVER fabricate a field. A missing or unreadable value
    is a hard validation error and forces escalation.
    """

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

    EXPIRY_KEY = {
        "passport":        "date_of_expiry",
        "visa":            "valid_until",
        "driving_license": "validity_to",
        "permit":          "expiry_date",
        "national_id":     "date_of_expiry",
    }

    _NULL_STRINGS = {"", "UNKNOWN", "N/A", "NA", "NULL", "NONE"}

    def __init__(self, blacklist_path: str | None = None):
        self.blacklist_db = set()
        if blacklist_path and os.path.exists(blacklist_path):
            with open(blacklist_path, encoding="utf-8") as fh:
                self.blacklist_db = {ln.strip() for ln in fh if ln.strip()}

    # ------------------------------------------------------------------
    @classmethod
    def _is_null(cls, v) -> bool:
        if v is None:
            return True
        if isinstance(v, str) and v.strip().upper() in cls._NULL_STRINGS:
            return True
        return False

    # ------------------------------------------------------------------
    def validate(self, ocr_data: dict) -> dict:
        doc_type = (ocr_data.get("document_type") or "").lower()
        fields = ocr_data.get("fields") or {}

        if not isinstance(fields, dict) or not fields:
            return {
                "valid": False,
                "errors": ["No structured fields extracted"],
                "document_type": doc_type or "unknown",
                "expiry_date": None,
            }

        if doc_type == "passport":
            return self._validate_passport(fields)
        return self._validate_generic(doc_type, fields)

    # ------------------------------------------------------------------
    def _validate_passport(self, fields: dict) -> dict:
        errors = []

        for req in self.REQUIRED["passport"]:
            if self._is_null(fields.get(req)):
                errors.append(f"Missing {req}")

        expiry_str = fields.get("date_of_expiry")
        if not self._is_null(expiry_str):
            errors.extend(self._check_date_field(expiry_str, "expiry",
                                                 future_ok=False))

        dob_str = fields.get("date_of_birth")
        if not self._is_null(dob_str):
            errors.extend(self._check_date_field(dob_str, "DOB",
                                                 future_ok=True))

        doc_num = fields.get("passport_number") or fields.get("document_number")
        if doc_num and doc_num in self.blacklist_db:
            errors.append("Document blacklisted")

        return {
            "valid": not errors,
            "errors": errors,
            "document_type": "passport",
            "expiry_date": fields.get("date_of_expiry"),
        }

    # ------------------------------------------------------------------
    def _validate_generic(self, doc_type: str, fields: dict) -> dict:
        errors = []

        for req in self.REQUIRED.get(doc_type, []):
            if self._is_null(fields.get(req)):
                errors.append(f"Missing {req}")

        expiry_key = self.EXPIRY_KEY.get(doc_type)
        expiry_val = None
        if expiry_key and not self._is_null(fields.get(expiry_key)):
            expiry_val = self._normalize_date(fields[expiry_key])
            if expiry_val is None:
                errors.append(
                    f"Unparseable expiry date: {fields[expiry_key]}")
            else:
                errors.extend(self._check_iso_date(expiry_val, "expiry"))

        for k, v in fields.items():
            if isinstance(v, str) and v in self.blacklist_db:
                errors.append(f"{k} blacklisted")
                break

        return {
            "valid": not errors,
            "errors": errors,
            "document_type": doc_type,
            "expiry_date": expiry_val,
        }

    # ------------------------------------------------------------------
    # Date helpers — strict. No silent MM/DD swaps, no invented values.
    # ------------------------------------------------------------------
    def _check_date_field(self, val, label: str, future_ok: bool):
        """Dispatch to MRZ (6-digit) or ISO (YYYY-MM-DD) checker."""
        if isinstance(val, str) and len(val) == 6 and val.isdigit():
            return self._check_mrz_date(val, label, future_ok)
        return self._check_iso_date(val, label, future_ok=future_ok)

    def _check_mrz_date(self, date_str: str, label: str, future_ok: bool):
        errors = []
        if not (isinstance(date_str, str)
                and len(date_str) == 6
                and date_str.isdigit()):
            errors.append(f"Invalid {label} date format: {date_str}")
            return errors

        yy, mm, dd = int(date_str[0:2]), int(date_str[2:4]), int(date_str[4:6])
        if not 1 <= mm <= 12:
            errors.append(f"Invalid {label} month in MRZ: {date_str}")
            return errors
        if not 1 <= dd <= 31:
            errors.append(f"Invalid {label} day in MRZ: {date_str}")
            return errors

        year = yy + (2000 if yy < 50 else 1900)
        try:
            dt = datetime(year, mm, dd)
        except ValueError:
            errors.append(f"Invalid {label} date values: {date_str}")
            return errors

        if label == "expiry" and dt < datetime.now():
            errors.append("Document expired")
        elif label == "DOB" and not future_ok and dt >= datetime.now():
            errors.append("DOB in future (unusual)")
        return errors

    def _normalize_date(self, date_str: str):
        """Return ISO YYYY-MM-DD or None. Never returns the raw input."""
        if not date_str:
            return None
        for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%d.%m.%Y",
                    "%d/%m/%y", "%d-%m-%y"):
            try:
                return datetime.strptime(date_str, fmt).strftime("%Y-%m-%d")
            except ValueError:
                continue
        return None

    def _check_iso_date(self, date_str: str, label: str, future_ok: bool = True):
        errors = []
        try:
            dt = datetime.strptime(date_str, "%Y-%m-%d")
        except (ValueError, TypeError):
            errors.append(f"Invalid {label} date: {date_str}")
            return errors

        if label == "expiry" and dt < datetime.now():
            errors.append("Document expired")
        elif label == "DOB" and not future_ok and dt >= datetime.now():
            errors.append("DOB in future (unusual)")
        return errors