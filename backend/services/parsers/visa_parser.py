import re
from .base import DocumentParser


class VisaParser(DocumentParser):
    document_type = "visa"
    REQUIRED_FIELDS = ["visa_number", "visa_type"]

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

        return self._finalize(f, 0.7)