import re
from .base import DocumentParser


class PermitParser(DocumentParser):
    document_type = "permit"
    REQUIRED_FIELDS = ["permit_number"]

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
            f["holder_name"] = m.group(1).strip().title()

        return self._finalize(f, 0.6)