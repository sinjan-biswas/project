import re
from .base import DocumentParser
 
 
class PermitParser(DocumentParser):
    document_type = "permit"
    REQUIRED_FIELDS = ["permit_number"]
 
    _NAME_BLACKLIST = re.compile(
        r"permit|govt|government|department|ministry|authority|"
        r"work|residence|study|entry|transit|employment|issue|"
        r"expiry|valid|address|signature|www|date|type",
        re.I,
    )
 
    def parse(self, lines, full_text):
        f = {"permit_number": None, "permit_type": None,
             "holder_name": None, "issue_date": None, "expiry_date": None}
        text = "\n".join(l["text"] for l in lines)
 
        m = re.search(
            r"(?:PERMIT|CARD|CERTIFICATE)\s*(?:NO|NUMBER|ID)?[.:\s#]*"
            r"([A-Z0-9/-]{5,20})", text, re.I)
        if m:
            f["permit_number"] = m.group(1).upper()
 
        m = re.search(
            r"(WORK|RESIDENCE|STUDY|ENTRY|TRANSIT|EMPLOYMENT)\s*PERMIT",
            text, re.I)
        if m:
            f["permit_type"] = m.group(1).upper() + " PERMIT"
 
        dates = re.findall(r"\d{2}[-/.]\d{2}[-/.]\d{4}", text)
        if dates:
            f["issue_date"] = dates[0]
        if len(dates) > 1:
            f["expiry_date"] = dates[-1]
 
        m = re.search(r"(?:NAME|HOLDER)[.:\s]*([A-Za-z .]+)", text, re.I)
        if m:
            candidate = m.group(1).strip()
            if not self._NAME_BLACKLIST.search(candidate):
                f["holder_name"] = candidate.title()
        if not f["holder_name"]:
            f["holder_name"] = self._find_name(lines)
 
        return self._finalize(f, 0.6)
 
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
