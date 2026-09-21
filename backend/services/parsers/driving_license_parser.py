import re
from .base import DocumentParser
 
 
class DrivingLicenseParser(DocumentParser):
    document_type = "driving_license"
    REQUIRED_FIELDS = ["dl_number", "name"]
 
    # Lines that are definitely NOT a person's name
    _NAME_BLACKLIST = re.compile(
        r"driving|licen[cs]e|transport|govt|government|india|union|"
        r"territory|form|class|validity|authorization|authorisation|"
        r"vehicle|address|blood|group|signature|hologram|issued|www|"
        r"date|invalid|non\s*transport",
        re.I,
    )
 
    def parse(self, lines, full_text):
        f = {"name": None, "dl_number": None, "date_of_birth": None,
             "validity_from": None, "validity_to": None,
             "vehicle_class": None}
        text = "\n".join(l["text"] for l in lines)
 
        # ---------- DL number (multiple state formats, OCR-tolerant) ---
        m = re.search(
            r"\b([A-Z]{2}[-\s]?\d{2}[-\s]?\d{4}[-\s]?\d{7})\b",
            text.upper())
        if m:
            f["dl_number"] = re.sub(r"\s", "", m.group(1))
        else:
            m = re.search(
                r"(?:DL\s*NO|LICENCE\s*NO|LICENSE\s*NO)[.:\s]*"
                r"([A-Z0-9\-\s]{10,20})", text, re.I)
            if m:
                f["dl_number"] = re.sub(r"\s", "", m.group(1).upper())
 
        # ---------- DOB, tolerant of OCR label noise --------------------
        m = re.search(
            r"(?:DOB|D0B|DOE|DATE\s*OF\s*BIRTH)[.:\s]*"
            r"(\d{2}[-/.]\d{2}[-/.]\d{4})", text, re.I)
        if m:
            f["date_of_birth"] = m.group(1)
        dates = re.findall(r"\d{2}[-/.]\d{2}[-/.]\d{4}", text)
        if f["date_of_birth"] is None and dates:
            f["date_of_birth"] = dates[0]
        remaining = [d for d in dates if d != f["date_of_birth"]]
        if len(remaining) >= 2:
            f["validity_from"], f["validity_to"] = remaining[0], remaining[1]
 
        m = re.search(r"(?:CLASS|COV)[.:\s]*([A-Z0-9, ]{1,15})", text, re.I)
        if m:
            f["vehicle_class"] = m.group(1).strip()
 
        f["name"] = self._find_name(lines)
        return self._finalize(f, 0.7)
 
    def _find_name(self, lines: list):
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
            # essentially always contains at least one vowel. A word
            # with no vowel at all is almost always a misread of a
            # heading, watermark, or security-pattern artifact, not a
            # real name. Short tokens (<=2 chars, e.g. initials) are
            # exempt.
            if any(len(w) >= 3 and not re.search(r"[aeiouAEIOU]", w)
                   for w in words):
                continue
            candidates.append(t.title())
        return candidates[0] if candidates else None
