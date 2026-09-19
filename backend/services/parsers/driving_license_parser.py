import re
from .base import DocumentParser


class DrivingLicenseParser(DocumentParser):
    document_type = "driving_license"
    REQUIRED_FIELDS = ["dl_number", "name"]

    def parse(self, lines, full_text):
        f = {"name": None, "dl_number": None, "date_of_birth": None,
             "validity_from": None, "validity_to": None,
             "vehicle_class": None}
        text = "\n".join(l["text"] for l in lines)

        m = re.search(
            r"\b([A-Z]{2}[-\s]?\d{2}[-\s]?\d{4}[-\s]?\d{7})\b",
            text.upper())
        if m:
            f["dl_number"] = re.sub(r"\s", "", m.group(1))

        m = re.search(
            r"(?:DOB|DATE\s*OF\s*BIRTH)[.:\s]*"
            r"(\d{2}[-/.]\d{2}[-/.]\d{4})", text, re.I)
        if m:
            f["date_of_birth"] = m.group(1)

        dates = re.findall(r"\d{2}[-/.]\d{2}[-/.]\d{4}", text)
        if len(dates) >= 3:
            f["validity_from"], f["validity_to"] = dates[1], dates[2]

        m = re.search(r"(?:CLASS|COV)[.:\s]*([A-Z0-9, ]{1,15})", text, re.I)
        if m:
            f["vehicle_class"] = m.group(1).strip()

        alpha = [l["text"].strip() for l in lines
                 if re.match(r"^[A-Za-z][A-Za-z .]{2,40}$",
                             l["text"].strip())]
        if alpha:
            f["name"] = alpha[0].title()

        return self._finalize(f, 0.7)