import re
from .base import DocumentParser

def mrz_check_digit(s: str) -> int:
    weights = [7, 3, 1]
    val = {str(d): d for d in range(10)}
    val.update({c: i for i, c in enumerate("ABCDEFGHIJKLMNOPQRSTUVWXYZ")})
    val["<"] = 0
    return sum(val.get(c, 0) * weights[i % 3] for i, c in enumerate(s)) % 10

def yyMMdd_to_iso(s: str) -> str:
    year = int(s[:2])
    century = "19" if year > 30 else "20"
    return f"{century}{s[0:2]}-{s[2:4]}-{s[4:6]}"

class PassportParser(DocumentParser):
    document_type = "passport"

    def parse(self, lines, full_text):
        mrz = self._find_td3_mrz(lines)
        fields = {
            "name": None, "passport_number": None, "nationality": None,
            "date_of_birth": None, "date_of_expiry": None, "gender": None,
        }
        conf = 0.0
        if mrz:
            l1, l2 = mrz
            # Names: positions 5..44 of line 1, split on '<<'
            names = l1[5:].split("<<")
            fields["name"] = " ".join(
                n.replace("<", " ").strip() for n in names if n).strip()

            doc_num = l2[0:9].replace("<", "")
            if mrz_check_digit(l2[0:9]) == int(l2[9]):
                fields["passport_number"] = doc_num
            fields["nationality"] = l2[10:13].replace("<", "")
            if mrz_check_digit(l2[13:19]) == int(l2[19]):
                fields["date_of_birth"] = yyMMdd_to_iso(l2[13:19])
            fields["gender"] = {"M": "M", "F": "F"}.get(l2[20], "X")
            if mrz_check_digit(l2[21:27]) == int(l2[27]):
                fields["date_of_expiry"] = yyMMdd_to_iso(l2[21:27])
            conf = 0.95
        else:
            # Visual-zone fallback
            text = "\n".join(l["text"] for l in lines)
            m = re.search(r"(?i)passport\s*(?:no|number)[.:\s]*([A-Z0-9]{6,9})", text)
            if m:
                fields["passport_number"] = m.group(1).upper()
            m = re.search(r"(?i)(?:surname|given\s*names?)[.:\s]*([A-Za-z ]+)", text)
            if m:
                fields["name"] = m.group(1).strip().title()
            conf = 0.5

        filled = sum(v is not None for v in fields.values())
        return {
            "document_type": self.document_type,
            "fields": fields,
            "confidence": conf * (filled / len(fields)),
        }

    def _find_td3_mrz(self, lines):
        candidates = []
        for ln in lines:
            clean = re.sub(r"[^A-Z0-9<]", "", ln["text"].upper())
            if len(clean) == 44 and "<" in clean:
                candidates.append(clean)
        for i in range(len(candidates) - 1):
            if candidates[i].startswith("P<") and not candidates[i + 1].startswith("P<"):
                return candidates[i], candidates[i + 1]
        return None