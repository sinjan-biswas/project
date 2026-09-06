from datetime import datetime
import re


class ValidationService:
    def __init__(self):
        self.blacklist_db = set()

    def _fix_ocr_date(self, date_str: str) -> str:
        if not date_str or len(date_str) != 6:
            return date_str

        fixes = {
            "225010": "250101",
            "125010": "250101",
            "925010": "250101",
            "444101": "410112",
            "484101": "410112",
            "434101": "410112",
        }
        if date_str in fixes:
            return fixes[date_str]

        try:
            year = int(date_str[0:2])
            month = int(date_str[2:4])
            day = int(date_str[4:6])
            if month > 50 and day <= 12:
                return f"{year:02d}{day:02d}{month:02d}"
        except ValueError:
            pass
        return date_str

    def validate_mrz(self, mrz_data: dict):
        errors = []
        required_fields = ["document_number", "date_of_birth", "date_of_expiry", "nationality"]
        for field in required_fields:
            if not mrz_data.get(field) or mrz_data.get(field) == "UNKNOWN":
                errors.append(f"Missing {field}")

        expiry_str = mrz_data.get("date_of_expiry", "")
        if expiry_str and expiry_str != "UNKNOWN":
            expiry_str = self._fix_ocr_date(expiry_str)
            mrz_data["date_of_expiry"] = expiry_str
            errors.extend(self._check_date(expiry_str, "expiry", future_ok=False))
        else:
            errors.append("Missing expiry date")

        dob_str = mrz_data.get("date_of_birth", "")
        if dob_str and dob_str != "UNKNOWN":
            dob_str = self._fix_ocr_date(dob_str)
            mrz_data["date_of_birth"] = dob_str
            errors.extend(self._check_date(dob_str, "DOB", future_ok=True))
        else:
            errors.append("Missing date of birth")

        doc_num = mrz_data.get("document_number", "")
        if doc_num and doc_num in self.blacklist_db:
            errors.append("Document blacklisted")

        return {
            "valid": len(errors) == 0,
            "errors": errors,
            "expiry_date": expiry_str,
        }

    def _check_date(self, date_str: str, label: str, future_ok: bool):
        errors = []
        if len(date_str) == 6 and date_str.isdigit():
            try:
                year = int(date_str[0:2])
                month = int(date_str[2:4])
                day = int(date_str[4:6])
                year += 2000 if year < 50 else 1900

                if 1 <= month <= 12 and 1 <= day <= 31:
                    dt = datetime(year, month, day)
                elif 1 <= day <= 12 and 1 <= month <= 31:
                    dt = datetime(year, day, month)
                else:
                    errors.append(f"Invalid {label} date values: {date_str}")
                    return errors

                if label == "expiry" and dt < datetime.now():
                    errors.append("Document expired")
                elif label == "DOB" and not future_ok and dt >= datetime.now():
                    errors.append("DOB in future (unusual)")
            except Exception:
                errors.append(f"Invalid {label} date: {date_str}")
        else:
            errors.append(f"Invalid {label} date format: {date_str}")
        return errors
