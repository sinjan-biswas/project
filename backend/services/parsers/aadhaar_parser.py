import re
from .base import DocumentParser


class AadhaarParser(DocumentParser):
    document_type = "aadhaar"
    REQUIRED_FIELDS = ["aadhaar_number", "name"]

    # Lines that are definitely NOT a person's name
    _NAME_BLACKLIST = re.compile(
        r"aadhaar|uidai|gov|india|government|details|address|"
        r"proof|identity|male|female|transgender|dob|birth|"
        r"number|issued|help|www|1947",
        re.I,
    )

    def parse(self, lines, full_text):
        f = {"name": None, "aadhaar_number": None,
             "date_of_birth": None, "gender": None}
        text = "\n".join(l["text"] for l in lines)

        # ---------- Aadhaar number (multi-strategy) -------------------
        f["aadhaar_number"] = self._find_aadhaar_number(text, lines)

        # ---------- DOB -----------------------------------------------
        m = re.search(
            r"(?:DOB|DATE\s*OF\s*BIRTH|जन्म\s*तारीख)[.:\s]*"
            r"(\d{2}[/-]\d{2}[/-]\d{4})", text, re.I)
        if m:
            f["date_of_birth"] = m.group(1)

        # ---------- Gender --------------------------------------------
        m = re.search(r"\b(MALE|FEMALE|TRANSGENDER|पुरुष|महिला)\b",
                      text, re.I)
        if m:
            tok = m.group(1).upper()
            if tok in ("पुरुष",):
                tok = "MALE"
            elif tok in ("महिला",):
                tok = "FEMALE"
            f["gender"] = tok

        # ---------- Name (filtered) -----------------------------------
        for ln in lines:
            t = ln["text"].strip()
            if not re.match(r"^[A-Za-z][A-Za-z .]{2,40}$", t):
                continue
            if self._NAME_BLACKLIST.search(t):
                continue
            # Prefer 2-4 word names
            words = t.split()
            if not (1 <= len(words) <= 4):
                continue
            f["name"] = t.title()
            break

        return self._finalize(f, 0.85)

    # ================================================================== #
    #  Aadhaar number extraction — 4 fallback strategies
    # ================================================================== #
    def _find_aadhaar_number(self, text: str, lines: list):
        # Strategy 1: standard 12 digits with optional spaces/hyphens
        for m in re.finditer(
                r"\b(\d{4})[\s\-]?(\d{4})[\s\-]?(\d{4})\b", text):
            num = m.group(1) + m.group(2) + m.group(3)
            if self._verhoeff_ok(num):
                return num

        # Strategy 2: contiguous 12 digits anywhere
        for m in re.finditer(r"\b(\d{12})\b", text):
            num = m.group(1)
            if self._verhoeff_ok(num):
                return num

        # Strategy 3: combine a 4-digit fragment and an 8-digit fragment
        #   (this is what your Aadhaar card produced)
        fours  = [(m.start(), m.group(1)) for m in
                  re.finditer(r"\b(\d{4})\b", text)]
        eights = [(m.start(), m.group(1)) for m in
                  re.finditer(r"\b(\d{8})\b", text)]
        candidates = []
        for pos4, n4 in fours:
            for pos8, n8 in eights:
                num = n4 + n8
                if self._verhoeff_ok(num):
                    candidates.append((abs(pos4 - pos8), num))
        if candidates:
            candidates.sort(key=lambda x: x[0])
            return candidates[0][1]

        # Strategy 4: strip all non-digits, slide a 12-digit window
        digits = re.sub(r"\D", "", text)
        for i in range(len(digits) - 11):
            num = digits[i:i + 12]
            if self._verhoeff_ok(num):
                return num

        return None

    # ================================================================== #
    #  Verhoeff checksum (unchanged)
    # ================================================================== #
    def _verhoeff_ok(self, num: str) -> bool:
        if not (isinstance(num, str) and len(num) == 12 and num.isdigit()):
            return False
        d = [[0,1,2,3,4,5,6,7,8,9],[1,2,3,4,0,6,7,8,9,5],
             [2,3,4,0,1,7,8,9,5,6],[3,4,0,1,2,8,9,5,6,7],
             [4,0,1,2,3,9,5,6,7,8],[5,9,8,7,6,0,4,3,2,1],
             [6,5,9,8,7,1,0,4,3,2],[7,6,5,9,8,2,1,0,4,3],
             [8,7,6,5,9,3,2,1,0,4],[9,8,7,6,5,4,3,2,1,0]]
        p = [[0,1,2,3,4,5,6,7,8,9],[1,5,7,6,2,8,3,0,9,4],
             [5,8,0,3,7,9,6,1,4,2],[8,9,1,6,0,4,3,5,2,7],
             [9,4,5,3,1,2,6,8,7,0],[4,2,8,6,5,7,3,9,0,1],
             [2,7,9,3,8,0,6,4,1,5],[7,0,4,6,9,1,3,2,5,8]]
        c = 0
        for i, ch in enumerate(reversed(num)):
            c = d[c][p[(i + 1) % 8][int(ch)]]
        return c == 0