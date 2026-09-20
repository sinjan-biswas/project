import re
from .base import DocumentParser
 
 
class PANParser(DocumentParser):
    document_type = "pan"
    REQUIRED_FIELDS = ["pan_number", "name"]
 
    # Lines that are definitely NOT a person's/father's name
    _NAME_BLACKLIST = re.compile(
        r"income\s*tax|govt|government|india|permanent|account|number|"
        r"department|signature|card|date|birth|father|dob|verify|"
        r"www|gov\.in|qr|e-pan",
        re.I,
    )
 
    def parse(self, lines, full_text):
        f = {"name": None, "father_name": None,
             "pan_number": None, "date_of_birth": None}
        text = "\n".join(l["text"] for l in lines)
 
        # ---------- PAN number (tolerant of OCR O/0, I/1 confusion) ----
        f["pan_number"] = self._find_pan(text)
 
        # ---------- DOB -------------------------------------------------
        m = re.search(
            r"(?:DOB|D0B|DATE\s*OF\s*BIRTH)[\s/.:\-]*"
            r"(\d{2}[/\-.]\d{2}[/\-.]\d{4})", text, re.I)
        if m:
            f["date_of_birth"] = m.group(1)
        else:
            m = re.search(r"\b(\d{2}/\d{2}/\d{4})\b", text)
            if m:
                f["date_of_birth"] = m.group(1)
 
        # ---------- Names (blacklist-filtered, in document order) -------
        names = self._find_names(lines)
        if names:
            f["name"] = names[0]
        if len(names) > 1:
            f["father_name"] = names[1]
 
        return self._finalize(f, 0.75)
 
    def _find_pan(self, text: str):
        # Strategy 1: strict pattern
        m = re.search(r"\b([A-Z]{5}[0-9]{4}[A-Z])\b", text.upper())
        if m:
            return m.group(1)
        # Strategy 2: label-anchored, tolerant of a stray space/dash
        m = re.search(
            r"(?:PAN|PERMANENT\s*ACCOUNT\s*NUMBER)[.:\s]*"
            r"([A-Z]{5}[\s\-]?[0-9]{4}[\s\-]?[A-Z])", text.upper(), re.I)
        if m:
            return re.sub(r"[\s\-]", "", m.group(1))
        return None
 
    def _find_names(self, lines: list):
        candidates = []
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
            # (transliterated to English on an Indian ID) essentially
            # always contains at least one vowel. A word with no
            # vowel at all — e.g. "WRCHY" — is almost always a
            # misread heading, watermark, or security-pattern
            # artifact rather than a real name, and would otherwise
            # win a name/father_name slot ahead of the real names on
            # the card. Short tokens (<=2 chars, e.g. initials like
            # "MD") are exempt since real initials can lack vowels.
            if any(len(w) >= 3 and not re.search(r"[aeiouAEIOU]", w)
                   for w in words):
                continue
 
            candidates.append(t.title())
        return candidates
