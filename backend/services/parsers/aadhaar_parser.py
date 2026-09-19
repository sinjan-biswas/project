import re
from .base import DocumentParser

class AadhaarParser(DocumentParser):
    document_type = "aadhaar"

    def parse(self, lines, full_text):
        f = {"name": None, "aadhaar_number": None,
             "date_of_birth": None, "gender": None}
        text = "\n".join(l["text"] for l in lines)

        m = re.search(r"\b(\d{4}[\s-]?\d{4}[\s-]?\d{4})\b", text)
        if m:
            num = re.sub(r"\D", "", m.group(1))
            if self._verhoeff_ok(num):
                f["aadhaar_number"] = num

        m = re.search(r"(?:DOB|DATE\s*OF\s*BIRTH)[.:\s]*(\d{2}/\d{2}/\d{4})", text, re.I)
        if m:
            f["date_of_birth"] = m.group(1)
        else:
            m = re.search(r"YEAR\s*OF\s*BIRTH[.:\s]*(\d{4})", text, re.I)
            if m:
                f["date_of_birth"] = m.group(1)

        m = re.search(r"\b(MALE|FEMALE|TRANSGENDER)\b", text, re.I)
        if m:
            f["gender"] = m.group(1).upper()

        for ln in lines:
            t = ln["text"].strip()
            if (re.match(r"^[A-Za-z][A-Za-z .]{2,40}$", t)
                    and not re.search(r"aadhaar|uidai|gov|india", t, re.I)):
                f["name"] = t.title()
                break

        return {"document_type": "aadhaar", "fields": f, "confidence": 0.75}

    def _verhoeff_ok(self, num: str) -> bool:
        d = [[0,1,2,3,4,5,6,7,8,9],[1,2,3,4,0,6,7,8,9,5],[2,3,4,0,1,7,8,9,5,6],
             [3,4,0,1,2,8,9,5,6,7],[4,0,1,2,3,9,5,6,7,8],[5,9,8,7,6,0,4,3,2,1],
             [6,5,9,8,7,1,0,4,3,2],[7,6,5,9,8,2,1,0,4,3],[8,7,6,5,9,3,2,1,0,4],
             [9,8,7,6,5,4,3,2,1,0]]
        p = [[0,1,2,3,4,5,6,7,8,9],[1,5,7,6,2,8,3,0,9,4],[5,8,0,3,7,9,6,1,4,2],
             [8,9,1,6,0,4,3,5,2,7],[9,4,5,3,1,2,6,8,7,0],[4,2,8,6,5,7,3,9,0,1],
             [2,7,9,3,8,0,6,4,1,5],[7,0,4,6,9,1,3,2,5,8]]
        c = 0
        for i, ch in enumerate(reversed(num)):
            c = d[c][p[(i + 1) % 8][int(ch)]]
        return c == 0