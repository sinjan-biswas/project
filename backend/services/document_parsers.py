"""
Template-specific document parsers.

MRZ formats (ICAO 9303):
    TD3  - 2 lines x 44 chars  -> passports, visas
    TD2  - 2 lines x 36 chars  -> visas, older ID cards
    TD1  - 3 lines x 30 chars  -> national ID cards, residence permits

Non-MRZ Indian documents handled with pattern extraction:
    Aadhaar (12-digit), PAN (AAAAA9999A), Voter ID (EPIC AAA9999999),
    Driving License (state code + number)
"""

import re
from datetime import datetime

MRZ_VALUE = {c: i for i, c in enumerate("0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ<")}


def mrz_check_digit(s: str) -> int:
    weights = (7, 3, 1)
    total = 0
    for i, ch in enumerate(s):
        total += MRZ_VALUE.get(ch, 0) * weights[i % 3]
    return total % 10


def _verify(s: str, digit_char: str) -> bool:
    try:
        return mrz_check_digit(s) == int(digit_char)
    except (ValueError, TypeError):
        return False


def _clean(s: str) -> str:
    return re.sub(r"\s+", " ", s.replace("<", " ")).strip()


def _clean_num(s: str) -> str:
    return s.replace("<", "").strip()


def mrz_date(s: str, kind: str = "dob"):
    out = {"raw": s, "iso": None, "valid_shape": False}
    if len(s) != 6 or not s.isdigit():
        return out
    yy, mm, dd = int(s[0:2]), int(s[2:4]), int(s[4:6])
    if not (1 <= mm <= 12 and 1 <= dd <= 31):
        return out
    year = 2000 + yy
    now_year = datetime.now().year
    if kind == "dob":
        if year > now_year:
            year -= 100
    else:
        if year > now_year + 50:
            year -= 100
    out["iso"] = f"{year:04d}-{mm:02d}-{dd:02d}"
    out["valid_shape"] = True
    return out


def parse_mrz_name(s: str):
    parts = s.split("<<")
    surname = _clean(parts[0]) if parts else ""
    given = _clean(parts[1]) if len(parts) > 1 else ""
    return surname, given


def find_mrz_block(text: str):
    lines = [re.sub(r"[^A-Z0-9<]", "", l.upper()) for l in text.split("\n")]
    best, cur = [], []
    for l in lines:
        if len(l) >= 24 and "<" in l and re.fullmatch(r"[A-Z0-9<]+", l):
            cur.append(l)
        else:
            if cur and sum(map(len, cur)) > sum(map(len, best)):
                best = cur
            cur = []
    if cur and sum(map(len, cur)) > sum(map(len, best)):
        best = cur
    return best


def detect_mrz_format(block) -> str | None:
    if len(block) >= 3 and all(28 <= len(l) <= 31 for l in block[:3]):
        return "TD1"
    if len(block) >= 2:
        if len(block[0]) >= 42 and len(block[1]) >= 42:
            return "TD3"
        if 34 <= len(block[0]) <= 37 and 34 <= len(block[1]) <= 37:
            return "TD2"
    return None


def parse_td3(l1: str, l2: str):
    surname, given = parse_mrz_name(l1[5:])
    fields = {
        "document_code": l1[0:2],
        "issuing_country": l1[2:5],
        "surname": surname,
        "given_names": given,
        "document_number": _clean_num(l2[0:9]),
        "nationality": l2[10:13],
        "date_of_birth": mrz_date(l2[13:19], "dob"),
        "sex": l2[20] if l2[20] in ("M", "F") else "X",
        "date_of_expiry": mrz_date(l2[21:27], "expiry"),
        "optional_data": _clean(l2[28:43]),
    }
    checks = {
        "document_number": _verify(l2[0:9], l2[9]),
        "date_of_birth": _verify(l2[13:19], l2[19]),
        "date_of_expiry": _verify(l2[21:27], l2[27]),
        "optional_data": _verify(l2[28:42], l2[42]),
        "composite": _verify(l2[0:10] + l2[13:20] + l2[21:28] + l2[28:43], l2[43]),
    }
    return fields, checks


def parse_td2(l1: str, l2: str):
    surname, given = parse_mrz_name(l1[5:])
    fields = {
        "document_code": l1[0:2],
        "issuing_country": l1[2:5],
        "surname": surname,
        "given_names": given,
        "document_number": _clean_num(l2[0:9]),
        "nationality": l2[10:13],
        "date_of_birth": mrz_date(l2[13:19], "dob"),
        "sex": l2[20] if l2[20] in ("M", "F") else "X",
        "date_of_expiry": mrz_date(l2[21:27], "expiry"),
        "optional_data": _clean(l2[28:35]),
    }
    checks = {
        "document_number": _verify(l2[0:9], l2[9]),
        "date_of_birth": _verify(l2[13:19], l2[19]),
        "date_of_expiry": _verify(l2[21:27], l2[27]),
        "composite": _verify(l2[0:10] + l2[13:20] + l2[21:28] + l2[28:35], l2[35]),
    }
    return fields, checks


def parse_td1(l1: str, l2: str, l3: str):
    surname, given = parse_mrz_name(l3)
    fields = {
        "document_code": l1[0:2],
        "issuing_country": l1[2:5],
        "document_number": _clean_num(l1[5:14]),
        "date_of_birth": mrz_date(l2[0:6], "dob"),
        "sex": l2[7] if l2[7] in ("M", "F") else "X",
        "date_of_expiry": mrz_date(l2[8:14], "expiry"),
        "nationality": l2[15:18],
        "optional_data": _clean(l1[15:30] + l2[18:29]),
        "surname": surname,
        "given_names": given,
    }
    checks = {
        "document_number": _verify(l1[5:14], l1[14]),
        "date_of_birth": _verify(l2[0:6], l2[6]),
        "date_of_expiry": _verify(l2[8:14], l2[14]),
        "composite": _verify(l1[5:15] + l2[0:7] + l2[8:15], l2[29]),
    }
    return fields, checks


class BaseParser:
    document_type = "unknown"
    required_fields = []

    def parse(self, text: str):
        raise NotImplementedError

    def _confidence(self, fields: dict) -> float:
        if not self.required_fields:
            return 0.5
        found = sum(1 for f in self.required_fields if fields.get(f))
        return round(found / len(self.required_fields), 2)

    def _finalize(self, fields, mrz=None, checks=None):
        checksum_valid = bool(checks) and all(checks.values()) if checks else None
        return {
            "document_type": self.document_type,
            "fields": fields,
            "mrz": mrz,
            "checksum_valid": checksum_valid,
            "confidence": self._confidence(fields),
        }


class GenericMRZParser(BaseParser):
    def parse(self, text: str):
        block = find_mrz_block(text)
        fmt = detect_mrz_format(block)
        if fmt == "TD3":
            fields, checks = parse_td3(block[0], block[1])
        elif fmt == "TD2":
            fields, checks = parse_td2(block[0], block[1])
        elif fmt == "TD1":
            fields, checks = parse_td1(block[0], block[1], block[2])
        else:
            fields, checks = {}, None
        mrz = {"format": fmt, "lines": block, "checks": checks} if fmt else None
        return self._finalize(fields, mrz=mrz, checks=checks)


class PassportParser(GenericMRZParser):
    document_type = "passport"
    required_fields = ["document_number", "surname", "date_of_birth", "date_of_expiry", "nationality"]

    def parse(self, text: str):
        result = super().parse(text)
        if result["mrz"]:
            result["mrz"]["checks"]["is_passport_code"] = result["fields"].get("document_code", "").startswith("P")
            result["document_type"] = "passport"
        return result


class VisaParser(GenericMRZParser):
    document_type = "visa"
    required_fields = ["document_number", "surname", "date_of_expiry", "issuing_country"]

    def parse(self, text: str):
        block = find_mrz_block(text)
        fmt = detect_mrz_format(block)
        if fmt == "TD2":
            fields, checks = parse_td2(block[0], block[1])
        else:
            fields, checks = parse_td3(block[0][:44], block[1][:44]) if len(block) >= 2 else ({}, None)
        if fields:
            fields["visa_number"] = fields.get("document_number")
            checks = checks or {}
            checks["is_visa_code"] = fields.get("document_code", "").startswith("V")
        mrz = {"format": fmt, "lines": block, "checks": checks} if fmt else None
        return self._finalize(fields, mrz=mrz, checks=checks)


class NationalIDParser(GenericMRZParser):
    document_type = "national_id"
    required_fields = ["document_number", "surname", "date_of_birth", "date_of_expiry"]


class ResidencePermitParser(NationalIDParser):
    document_type = "residence_permit"


# ------------------------- Indian documents --------------------------- #
class AadhaarParser(BaseParser):
    document_type = "aadhaar"
    required_fields = ["aadhaar_number", "name"]

    def parse(self, text: str):
        # Bug K: strict + Verhoeff-recovered candidates, sorted by validity.
        # If NOTHING passes Verhoeff, return None — an invalid number looks
        # authoritative and misleads downstream (validation, risk, audit).
        candidates = list(self._find_aadhaar_candidates(text))

        aadhaar = None
        verhoeff_ok = None
        for cand in candidates:
            if len(cand) != 12:
                continue
            if self._verhoeff(cand):
                aadhaar = cand
                verhoeff_ok = True
                break
        # NOTE: no fallback to "first 12-digit candidate". If Verhoeff
        # rejects every candidate, aadhaar stays None. Honest > wrong.

        dob = re.search(r"\b(\d{2}/\d{2}/\d{4})\b", text)

        name = None
        lines = [l.strip() for l in text.splitlines() if l.strip()]
        for i, l in enumerate(lines):
            if "AADHAAR" in l.upper() and i > 0:
                candidate = lines[i - 1]
                if re.fullmatch(r"[A-Za-z .]+", candidate) and len(candidate) < 40:
                    name = candidate
                    break
        if not name:
            for l in lines:
                if re.fullmatch(r"[A-Z][a-z]+(?:\s+[A-Z][a-z]+)+", l) and len(l) < 40:
                    name = l
                    break

        formatted = None
        if aadhaar and len(aadhaar) == 12:
            formatted = f"{aadhaar[:4]} {aadhaar[4:8]} {aadhaar[8:]}"

        fields = {
            "aadhaar_number": formatted,
            "name": name,
            "date_of_birth": dob.group(1) if dob else None,
            "masked": False,
            "checksum_valid": verhoeff_ok,
        }
        result = self._finalize(fields)
        result["checksum_valid"] = verhoeff_ok
        return result

    @staticmethod
    def _find_aadhaar_candidates(text: str):
        """Yield candidate 12-digit Aadhaar numbers, tolerating one dropped digit."""
        seen = set()

        # Attempt 1 — strict 4-4-4 with optional single space
        for m in re.finditer(r"\b(\d{4})\s?(\d{4})\s?(\d{4})\b", text):
            cand = "".join(m.groups())
            if cand not in seen:
                seen.add(cand)
                yield cand

        # Attempt 2 — any 12-digit run after stripping whitespace
        squeezed = re.sub(r"\s+", "", text)
        for m in re.finditer(r"\d{12}", squeezed):
            cand = m.group(0)
            if cand not in seen:
                seen.add(cand)
                yield cand

        # Attempt 3 — 11-digit fragments; recover the missing digit via
        # Verhoeff (exactly one completion will pass).
        for m in re.finditer(r"\b(\d{3,4})\s?(\d{3,4})\s?(\d{3,4})\b", text):
            base = "".join(m.groups())
            if len(base) == 11:
                for d in "0123456789":
                    for completed in (d + base, base + d):
                        if completed not in seen:
                            seen.add(completed)
                            yield completed
            elif len(base) == 12 and base not in seen:
                seen.add(base)
                yield base

    @staticmethod
    def _verhoeff(number: str):
        d = [[0,1,2,3,4,5,6,7,8,9],[1,2,3,4,0,6,7,8,9,5],[2,3,4,0,1,7,8,9,5,6],
             [3,4,0,1,2,8,9,5,6,7],[4,0,1,2,3,9,5,6,7,8],[5,9,8,7,6,0,4,3,2,1],
             [6,5,9,8,7,1,0,4,3,2],[7,6,5,9,8,2,1,0,4,3],[8,7,6,5,9,3,2,1,0,4],
             [9,8,7,6,5,4,3,2,1,0]]
        p = [[0,1,2,3,4,5,6,7,8,9],[1,5,7,6,2,8,3,0,9,4],[5,8,0,3,7,9,6,1,4,2],
             [8,9,1,6,0,4,3,5,2,7],[9,4,5,3,1,2,6,8,7,0],[4,2,8,6,5,7,3,9,0,1],
             [2,7,9,3,8,0,6,4,1,5],[7,0,4,6,9,1,3,2,5,8]]
        num = re.sub(r"\D", "", number or "")
        if len(num) != 12:
            return False
        c = 0
        for i, ch in enumerate(reversed(num)):
            c = d[c][p[(i + 1) % 8][int(ch)]]
        return c == 0


class PANParser(BaseParser):
    document_type = "pan"
    required_fields = ["pan_number", "name"]

    def parse(self, text: str):
        pan = re.search(r"\b([A-Z]{5}[0-9]{4}[A-Z])\b", text.upper())
        dob = re.search(r"\b(\d{2}/\d{2}/\d{4})\b", text)
        fields = {
            "pan_number": pan.group(1) if pan else None,
            "name": self._extract_name(text),
            "date_of_birth": dob.group(1) if dob else None,
        }
        result = self._finalize(fields)
        result["checksum_valid"] = bool(pan)
        return result

    @staticmethod
    def _extract_name(text):
        m = re.search(r"(?:NAME|N A M E)\s*[:\-]?\s*([A-Za-z .]{3,40})", text)
        return m.group(1).strip() if m else None


class VoterIDParser(BaseParser):
    document_type = "voter_id"
    required_fields = ["epic_number", "name"]

    def parse(self, text: str):
        epic = re.search(r"\b([A-Z]{3}[0-9]{7})\b", text.upper())
        fields = {
            "epic_number": epic.group(1) if epic else None,
            "name": self._extract_name(text),
        }
        result = self._finalize(fields)
        result["checksum_valid"] = bool(epic)
        return result

    @staticmethod
    def _extract_name(text):
        m = re.search(r"(?:ELECTOR|NAME)\s*[:\-]?\s*([A-Za-z .]{3,40})", text)
        return m.group(1).strip() if m else None


class DrivingLicenseParser(BaseParser):
    document_type = "driving_license"
    required_fields = ["license_number", "name"]

    def parse(self, text: str):
        dl = re.search(r"\b([A-Z]{2}[-\s]?\d{2}[-\s]?\d{4}[-\s]?\d{4,7})\b", text.upper())
        dob = re.search(r"(?:DOB|DATE OF BIRTH)[:\- ]*(\d{2}[-/]\d{2}[-/]\d{4})", text.upper())
        validity = re.search(r"(?:VALIDITY|VALID TILL)[:\- ]*(\d{2}[-/]\d{2}[-/]\d{4})", text.upper())
        fields = {
            "license_number": dl.group(1) if dl else None,
            "date_of_birth": dob.group(1) if dob else None,
            "validity": validity.group(1) if validity else None,
        }
        result = self._finalize(fields)
        result["checksum_valid"] = bool(dl)
        return result


class GenericParser(GenericMRZParser):
    document_type = "unknown"
    required_fields = ["document_number"]


class DocumentParserRouter:
    PARSERS = {
        "passport": PassportParser(),
        "visa": VisaParser(),
        "national_id": NationalIDParser(),
        "residence_permit": ResidencePermitParser(),
        "permit": VisaParser(),
        "aadhaar": AadhaarParser(),
        "pan": PANParser(),
        "voter_id": VoterIDParser(),
        "driving_license": DrivingLicenseParser(),
    }

    def parse(self, doc_type: str, ocr_text: str):
        parser = self.PARSERS.get(doc_type, GenericParser())
        return parser.parse(ocr_text or "")