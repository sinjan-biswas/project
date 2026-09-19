import re
from .base import DocumentParser

class PANParser(DocumentParser):
    document_type = "pan"

    def parse(self, lines, full_text):
        f = {"name": None, "father_name": None,
             "pan_number": None, "date_of_birth": None}
        text = "\n".join(l["text"] for l in lines)

        m = re.search(r"\b([A-Z]{5}[0-9]{4}[A-Z])\b", text.upper())
        if m: f["pan_number"] = m.group(1)
        m = re.search(r"(\d{2}/\d{2}/\d{4})", text)
        if m: f["date_of_birth"] = m.group(1)

        alpha_lines = [l["text"].strip() for l in lines
                       if re.match(r"^[A-Za-z][A-Za-z .]{2,40}$", l["text"].strip())]
        if alpha_lines: f["name"] = alpha_lines[0].title()
        if len(alpha_lines) > 1: f["father_name"] = alpha_lines[1].title()

        return {"document_type": "pan", "fields": f, "confidence": 0.75}