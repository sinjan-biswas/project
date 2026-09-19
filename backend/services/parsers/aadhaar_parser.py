import re
from collections import Counter
from .base import DocumentParser


class AadhaarParser(DocumentParser):
    document_type = "aadhaar"
    REQUIRED_FIELDS = ["aadhaar_number", "name"]

    # Lines that are definitely NOT a person's name
    _NAME_BLACKLIST = re.compile(
        r"aadhaar|uidai|gov|india|government|details|address|"
        r"proof|identity|male|female|transgender|dob|birth|"
        r"number|issued|help|www|1947|xml|qr|authentication|"
        r"verification|scanning|offline|citizenship|date",
        re.I,
    )

    # Junk tokens that OCR often produces on Aadhaar cards
    _JUNK_TOKENS = {"SIL", "3TR", "HAAR", "WWWWWWWW", "RM", "DIST", "PO"}

    def parse(self, lines, full_text):
        f = {"name": None, "aadhaar_number": None,
             "date_of_birth": None, "gender": None}
        text = "\n".join(l["text"] for l in lines)

        # ---------- DOB -----------------------------------------------
        # Found first so its digits can be excluded from Aadhaar-number
        # fragment merging below (see _find_aadhaar_number).
        f["date_of_birth"] = self._find_dob(text)

        # ---------- Aadhaar number (multi-strategy) -------------------
        f["aadhaar_number"] = self._find_aadhaar_number(
            text, lines, dob=f["date_of_birth"])

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

        # ---------- Name (filtered + spatially aware) -----------------
        f["name"] = self._find_name(lines)

        return self._finalize(f, 0.85)

    # ================================================================== #
    #  DOB extraction — handles OCR transpositions of "DOB"
    # ================================================================== #
    def _find_dob(self, text: str):
        # Strategy 1: explicit label, tolerant of OCR noise in the label
        #   matches: "DOB : 08/01/1995", "D0B:08/01/1995", "/DB08/01/1995",
        #             "जन्म तारीख / DOB : 08/01/1995"
        m = re.search(
            r"(?:DOB|D0B|DO8|D08|/DB|DB|जन्म\s*तारीख)"
            r"[\s/.:\-]*"
            r"(\d{2}[\-/]\d{2}[\-/]\d{4})",
            text, re.I)
        if m:
            return m.group(1)

        # Strategy 2: any well-formed date on the card (Aadhaar has only DOB)
        m = re.search(r"\b(\d{2}[\-/]\d{2}[\-/]\d{4})\b", text)
        if m:
            return m.group(1)

        # Strategy 3: date split across lines by OCR, e.g. "08/01/" + "1995"
        m = re.search(r"(\d{2}[\-/]\d{2}[\-/])\s*\n\s*(\d{4})", text)
        if m:
            return m.group(1) + m.group(2)

        return None

    # ================================================================== #
    #  Name extraction — reject junk, prefer spatial position
    # ================================================================== #
    def _find_name(self, lines: list):
        candidates = []
        for idx, ln in enumerate(lines):
            t = ln["text"].strip()
            # Basic shape: letters + spaces/dots only
            if not re.match(r"^[A-Za-z][A-Za-z .]{2,60}$", t):
                continue
            # Reject blacklisted words
            if self._NAME_BLACKLIST.search(t):
                continue
            # Reject known junk tokens
            if t.upper() in self._JUNK_TOKENS:
                continue

            words = t.split()

            # OCR sometimes merges a printed name into one CamelCase
            # token with no spaces (e.g. "ElonMusk" instead of
            # "Elon Musk"). If we see a single word that cleanly
            # decomposes into 2-4 capitalized runs, split it apart
            # before applying the word-count filter below. The
            # length-sum check guards against partial/garbage matches
            # (e.g. stray lowercase junk) slipping through.
            if len(words) == 1:
                camel_parts = re.findall(r"[A-Z][a-z]*", words[0])
                if (2 <= len(camel_parts) <= 4
                        and sum(len(p) for p in camel_parts) == len(words[0])):
                    words = camel_parts
                    t = " ".join(words)

            # Aadhaar names are 2-4 words; single-word names are rare
            # and usually OCR junk like "SIL"
            if not (2 <= len(words) <= 4):
                continue
            # Reject all-caps single tokens mixed with noise
            if len(t) < 5:
                continue
            # Each word should be at least 2 chars (initials like "J."
            # are possible but rare on Aadhaar)
            if any(len(w) < 2 for w in words if w not in ("S", "K")):
                continue
            # Score: prefer lines in the upper 40% of the card
            # (name is printed near the photo, upper-middle area)
            y_center = None
            if "box" in ln and ln["box"]:
                try:
                    ys = [p[1] for p in ln["box"]]
                    y_center = sum(ys) / len(ys)
                except Exception:
                    pass
            score = 0
            if y_center is not None:
                # Normalize: assume Aadhaar card aspect, upper part = name zone
                score += max(0, 1.0 - (y_center / 1000.0))  # rough prior
            # Bonus for title-case or all-caps (printed names)
            if t.istitle() or t.isupper():
                score += 0.5
            # Bonus for 2-3 word names (most common)
            if 2 <= len(words) <= 3:
                score += 0.3
            candidates.append((score, idx, t))

        if not candidates:
            return None

        # Highest score wins; tie-break by earliest line (top of card)
        candidates.sort(key=lambda x: (-x[0], x[1]))
        best = candidates[0][2]
        return best.title()

    # ================================================================== #
    #  Aadhaar number extraction — spatial fragment merging
    # ================================================================== #
    # Matches a DOB-shaped date anywhere in a line, e.g. "28/06/1971",
    # "08-01-1995". Lines that match this are date lines, not
    # Aadhaar-number lines, and must be excluded from fragment collection.
    _DATE_LINE_RE = re.compile(r"\d{1,2}[/\-]\d{1,2}[/\-]\d{2,4}")

    # Dominant weight applied per unit of OCR line-index gap when
    # scoring a fragment merge. The Aadhaar number's digit fragments
    # are always parts of the same printed field (same OCR line, or
    # split across immediately adjacent ones) — never fragments pulled
    # from a visually distant, unrelated field like an address PIN.
    # This is set high enough to dominate over pixel-distance noise,
    # which can vary a lot with card layout/OCR box quality and isn't
    # a reliable enough signal on its own to rule out a distant,
    # coincidentally-nearby cross-field merge.
    _LINE_GAP_WEIGHT = 5000

    def _find_aadhaar_number(self, text: str, lines: list, dob: str = None):
        """
        Aadhaar number extraction with spatial fragment merging.

        The Aadhaar number is printed in the LARGEST font on the card.
        When OCR fragments it, the fragments are the largest digit
        fragments and are spatially adjacent (same visual line or
        nearby lines on the same card side).

        Strategy:
        1. Try direct regex patterns (formatted/contiguous)
        2. Collect digit fragments with box coordinates, excluding
           digits that come from a DOB/date line
        3. Merge fragments that are spatially close AND form 12 digits
        4. Score by (spatial proximity, line adjacency, font size,
           verhoeff, plausibility)
        """
        dob_digits = re.sub(r"[^\d]", "", dob) if dob else None
        # ── Step 1: Direct patterns ───────────────────────────────────
        direct = []
        for m in re.finditer(r"\b(\d{4})[\s\-](\d{4})[\s\-](\d{4})\b", text):
            num = m.group(1) + m.group(2) + m.group(3)
            direct.append({"num": num, "font": 50, "dist": 0, "frags": 1})
        for m in re.finditer(r"\b(\d{12})\b", text):
            direct.append({"num": m.group(1), "font": 50, "dist": 0, "frags": 1})

        if direct:
            # If we found well-formatted numbers, use consensus
            counts = Counter(d["num"] for d in direct)
            best, cnt = counts.most_common(1)[0]
            if cnt >= 2:
                return best
            if len(direct) == 1:
                return direct[0]["num"]
            # Multiple different candidates: fall through to spatial merging

        # ── Step 2: Collect fragments with spatial metadata ───────────
        frags = []
        for idx, ln in enumerate(lines):
            # A DOB/date line's digits (e.g. the "1971" in "28/06/1971")
            # are never valid Aadhaar-number fragments, even though the
            # bare digit regex below would otherwise match them.
            if self._DATE_LINE_RE.search(ln["text"]):
                continue

            box = ln.get("box")
            y_c = x_c = h = 0
            if box:
                try:
                    ys = [p[1] for p in box]
                    xs = [p[0] for p in box]
                    y_c = sum(ys) / len(ys)
                    x_c = sum(xs) / len(xs)
                    h = max(ys) - min(ys)
                except Exception:
                    pass

            t = ln["text"]
            for m in re.finditer(r"\b(\d{4,12})\b", t):
                frags.append({
                    "digits": m.group(1),
                    "line_idx": idx,
                    "y": y_c,
                    "x": x_c,
                    "h": h or 10,
                })

        if not frags:
            return None

        # ── Step 3: Spatial fragment merging ──────────────────────────
        candidates = []

        # 2-fragment merges
        for i, f1 in enumerate(frags):
            for j, f2 in enumerate(frags):
                if i >= j:
                    continue
                merged = f1["digits"] + f2["digits"]
                if len(merged) != 12:
                    continue
                # NOTE: plausibility is intentionally NOT a hard filter
                # here — see the comment on the scoring function below
                # for why. A genuinely printed (if fraud-suspicious)
                # number must still be extractable as the OCR value;
                # fraud signals belong in risk scoring downstream, not
                # in silently discarding the correct OCR result.
                plausible = self._is_plausible_aadhaar(merged, dob_digits)
                # Spatial distance (same visual line = small distance).
                # Line-index gap is weighted in on top of raw pixel
                # distance: fragments from the same or adjacent OCR
                # lines are far more likely to belong to the same
                # printed number than fragments that merely happen to
                # land close together in pixel space across unrelated
                # fields (e.g. the Aadhaar number vs. an address PIN).
                line_gap = abs(f1["line_idx"] - f2["line_idx"])
                dist = (abs(f1["y"] - f2["y"]) + abs(f1["x"] - f2["x"])
                        + self._LINE_GAP_WEIGHT * line_gap)
                font = max(f1["h"], f2["h"])
                candidates.append({
                    "num": merged,
                    "font": font,
                    "dist": dist,
                    "frags": 2,
                    "verhoeff": self._verhoeff_ok(merged),
                    "plausible": plausible,
                })

        # 3-fragment merges (for 4+4+4 splits)
        for i, f1 in enumerate(frags):
            for j, f2 in enumerate(frags):
                for k, f3 in enumerate(frags):
                    if i >= j or j >= k:
                        continue
                    merged = f1["digits"] + f2["digits"] + f3["digits"]
                    if len(merged) != 12:
                        continue
                    plausible = self._is_plausible_aadhaar(merged, dob_digits)
                    line_gap = (abs(f1["line_idx"] - f2["line_idx"]) +
                                abs(f2["line_idx"] - f3["line_idx"]))
                    dist = (abs(f1["y"] - f2["y"]) + abs(f2["y"] - f3["y"]) +
                            abs(f1["x"] - f2["x"]) + abs(f2["x"] - f3["x"]) +
                            self._LINE_GAP_WEIGHT * line_gap)
                    font = max(f1["h"], f2["h"], f3["h"])
                    candidates.append({
                        "num": merged,
                        "font": font,
                        "dist": dist,
                        "frags": 3,
                        "verhoeff": self._verhoeff_ok(merged),
                        "plausible": plausible,
                    })

        if not candidates:
            return None

        # ── Step 4: Score ─────────────────────────────────────────────
        # Key: spatial proximity is the STRONGEST signal.
        # Fragments of the same number are on the same visual line.
        # Font size is secondary. Verhoeff is a bonus.
        #
        # "plausible" is a SOFT penalty, not a hard gate: a candidate
        # that trips the fraud-style heuristics in
        # _is_plausible_aadhaar (looks like a repeated/sequential/
        # trivial number) is heavily deprioritized, but can still win
        # if it's the strongest spatial match and nothing better
        # exists — because that heuristic is a fraud SIGNAL to surface
        # downstream (risk scoring), not grounds to silently discard
        # the number actually printed on the card and substitute a
        # worse OCR guess instead.
        def score(c):
            s = 1000.0 / (1.0 + c["dist"])       # spatial proximity dominant
            s *= c["font"] / 10.0                 # font size secondary
            if c["verhoeff"]:
                s *= 1.5                          # verhoeff bonus
            if not c["plausible"]:
                s *= 0.2                          # fraud-heuristic penalty
            s *= (4.0 - c["frags"])               # fewer fragments better
            return s

        candidates.sort(key=score, reverse=True)
        return candidates[0]["num"]

    # ================================================================== #
    #  Plausibility check for 12-digit candidates
    # ================================================================== #
    def _is_plausible_aadhaar(self, num: str, dob_digits: str = None) -> bool:
        """Reject obvious non-Aadhaar 12-digit sequences."""
        # Reject if the candidate contains the card's own DOB digits —
        # either the full date or just its 4-digit year — as a
        # contiguous substring at the tail end (where a merged
        # fragment would land). This is defense in depth on top of
        # excluding date lines during fragment collection in
        # _find_aadhaar_number; it catches a leaked year fragment
        # (e.g. "1971" from "28/06/1971") even if only part of the
        # date made it into the merge.
        if dob_digits:
            if len(dob_digits) >= 8 and dob_digits in num:
                return False
            year = dob_digits[-4:]
            if len(year) == 4 and num.endswith(year):
                return False
        # Reject if it contains a date-like pattern: YYYYMMDD or DDMMYYYY
        if re.search(r"(19|20)\d{2}(0[1-9]|1[0-2])(0[1-9]|[12]\d|3[01])", num):
            return False
        if re.search(r"(0[1-9]|[12]\d|3[01])(0[1-9]|1[0-2])(19|20)\d{2}", num):
            return False
        # Reject if first 6 digits == last 6 digits (repeated PIN)
        if num[:6] == num[6:]:
            return False
        # Reject if all digits are the same
        if len(set(num)) == 1:
            return False
        # Reject simple arithmetic sequences (mod 10, so wraparound
        # sequences like 4567890123 -> ...2345, where each digit is
        # prior+1 wrapping 9->0, are also caught)
        diffs = [(int(num[i + 1]) - int(num[i])) % 10 for i in range(11)]
        if all(d == diffs[0] for d in diffs):
            return False
        return True

    # ================================================================== #
    #  Verhoeff checksum (kept as tiebreaker, not hard gate)
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