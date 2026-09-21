import re
from .base import DocumentParser
 
 
class VisaParser(DocumentParser):
    document_type = "visa"
    REQUIRED_FIELDS = ["visa_number", "visa_type"]
 
    _NAME_BLACKLIST = re.compile(
        r"visa|embassy|consulate|govt|government|entries|stay|"
        r"duration|type|valid|remarks|passport|issue|expiry|"
        r"signature|www|date",
        re.I,
    )
 
    def parse(self, lines, full_text):
        f = {"visa_number": None, "visa_type": None, "entries": None,
             "stay_duration_days": None, "name": None, "passport_number": None,
             "valid_from": None, "valid_until": None}
        text = "\n".join(l["text"] for l in lines)
 
        m = re.search(r"VISA\s*(?:NO|NUMBER)?[.:\s]*([A-Z0-9]{6,12})",
                      text, re.I)
        if m:
            f["visa_number"] = m.group(1).upper()
 
        m = re.search(r"TYPE[.:\s]*([A-Z]\d?)", text, re.I)
        if m:
            f["visa_type"] = m.group(1).upper()
 
        m = re.search(
            r"\b(ENTRIES?[.:\s]*\w+|DOUBLE|MULTIPLE|SINGLE)\b", text, re.I)
        if m:
            f["entries"] = m.group(1).split()[-1].upper()
 
        m = re.search(r"STAY[.:\s]*(\d+)\s*(DAYS?|MONTHS?)", text, re.I)
        if m:
            n = int(m.group(1))
            f["stay_duration_days"] = n * (
                30 if "MONTH" in m.group(2).upper() else 1)
 
        m = re.search(
            r"(?:VALID\s*(?:FROM|BETWEEN)?)[.:\s]*"
            r"(\d{2}[./-]\d{2}[./-]\d{2,4})", text, re.I)
        if m:
            f["valid_from"] = m.group(1)
 
        m = re.search(
            r"(?:UNTIL|EXPIRY|VALID\s*TILL)[.:\s]*"
            r"(\d{2}[./-]\d{2}[./-]\d{2,4})", text, re.I)
        if m:
            f["valid_until"] = m.group(1)
 
        m = re.search(r"PASSPORT\s*(?:NO|NUMBER)?[.:\s]*([A-Z0-9]{6,9})",
                      text, re.I)
        if m:
            f["passport_number"] = m.group(1).upper()
 
        m = re.search(r"(?:NAME|HOLDER)[.:\s]*([A-Za-z .]+)", text, re.I)
        if m and not self._NAME_BLACKLIST.search(m.group(1)):
            f["name"] = m.group(1).strip().title()
        else:
            f["name"] = self._find_name(lines)
 
        return self._finalize(f, 0.7)
 
    def _find_name(self, lines: list):
        for ln in lines:
            t = ln["text"].strip()
            if not re.match(r"^[A-Za-z][A-Za-z .]{2,40}$", t):
                continue
            if self._NAME_BLACKLIST.search(t):
                continue
            words = t.split()
            if not (2 <= len(words) <= 4):
                continue
            if len(t) < 5:
                continue
            # Reject OCR garbage that slips past the blacklist and
            # shape checks: a genuine name token of 3+ letters
            # essentially always contains at least one vowel. A word
            # with no vowel at all is almost always a misread of a
            # heading, watermark, or security-pattern artifact, not a
            # real name. Short tokens (<=2 chars, e.g. initials) are
            # exempt.
            if any(len(w) >= 3 and not re.search(r"[aeiouAEIOU]", w)
                   for w in words):
                continue
            return t.title()
        return None
