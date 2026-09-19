import re
from .base import DocumentParser

class VoterIDParser(DocumentParser):
    document_type = "voter_id"

    def parse(self, lines, full_text):
        f = {"name": None, "epic_number": None,
             "assembly_constituency": None, "date_of_birth": None}
        text = "\n".join(l["text"] for l in lines)

        m = re.search(r"\b([A-Z]{3}[0-9]{7})\b", text.upper())
        if m: f["epic_number"] = m.group(1)
        m = re.search(r"ELECTOR'?S?\s*NAME[.:\s]*([A-Za-z .]+)", text, re.I)
        if m: f["name"] = m.group(1).strip().title()
        m = re.search(r"ASSEMBLY\s*CONSTITUENCY[.:\s]*([A-Za-z0-9 ().-]+)", text, re.I)
        if m: f["assembly_constituency"] = m.group(1).strip()
        m = re.search(r"(\d{2}/\d{2}/\d{4})", text)
        if m: f["date_of_birth"] = m.group(1)

        return {"document_type": "voter_id", "fields": f, "confidence": 0.7}