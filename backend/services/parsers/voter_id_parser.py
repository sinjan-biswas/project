import re
from .base import DocumentParser
 
 
class VoterIDParser(DocumentParser):
    document_type = "voter_id"
    REQUIRED_FIELDS = ["epic_number", "name"]
 
    _NAME_BLACKLIST = re.compile(
        r"election|commission|india|govt|government|elector|photo|"
        r"identity|card|address|assembly|constituency|part\s*no|"
        r"serial|father|husband|relation|gender|male|female|www|date",
        re.I,
    )
 
    def parse(self, lines, full_text):
        f = {"name": None, "epic_number": None,
             "assembly_constituency": None, "date_of_birth": None}
        text = "\n".join(l["text"] for l in lines)
 
        # ---------- EPIC number, OCR-tolerant fallback -------------------
        m = re.search(r"\b([A-Z]{3}[0-9]{7})\b", text.upper())
        if m:
            f["epic_number"] = m.group(1)
        else:
            m = re.search(
                r"\b([A-Z]{3}[\s\-]?[0-9]{7})\b", text.upper())
            if m:
                f["epic_number"] = re.sub(r"[\s\-]", "", m.group(1))
 
        # ---------- Name: label-based, then blacklist-filtered fallback --
        m = re.search(r"ELECTOR'?S?\s*NAME[.:\s]*([A-Za-z .]+)", text, re.I)
        if m:
            f["name"] = m.group(1).strip().title()
        else:
            f["name"] = self._find_name(lines)
 
        m = re.search(
            r"ASSEMBLY\s*CONSTITUENCY[.:\s]*([A-Za-z0-9 ().-]+)", text, re.I)
        if m:
            f["assembly_constituency"] = m.group(1).strip()
 
        m = re.search(
            r"(?:DOB|D0B|DATE\s*OF\s*BIRTH)[.:\s]*(\d{2}/\d{2}/\d{4})",
            text, re.I)
        if m:
            f["date_of_birth"] = m.group(1)
        else:
            m = re.search(r"(\d{2}/\d{2}/\d{4})", text)
            if m:
                f["date_of_birth"] = m.group(1)
 
        return self._finalize(f, 0.7)
 
    def _find_name(self, lines: list):
        for ln in lines:
            t = ln["text"].strip()
            if not re.match(r"^[A-Za-z][A-Za-z .]{2,60}$", t):
                continue
            if self._NAME_BLACKLIST.search(t):
                continue
            words = t.split()
            if not (2 <= len(words) <= 4):
                continue
            if len(t) < 5:
                continue
            return t.title()
        return None
 
