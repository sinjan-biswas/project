import numpy as np
import cv2
import os
import pytesseract
import re


class OCRService:
    def __init__(self):
        if not os.environ.get("TESSDATA_PREFIX"):
            possible_paths = [
                "/usr/share/tesseract-ocr/5/tessdata/",
                "/usr/share/tesseract-ocr/4.00/tessdata/",
                "/usr/share/tesseract-ocr/tessdata/",
                "/usr/local/share/tessdata/",
            ]
            for path in possible_paths:
                if os.path.exists(path):
                    os.environ["TESSDATA_PREFIX"] = path
                    break
        self.lang = "eng"

    def extract(self, image_bytes: bytes):
        try:
            nparr = np.frombuffer(image_bytes, np.uint8)
            image = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
            if image is None:
                return self._empty_result(error="Invalid image format")

            variants = self._ocr_variants(image)
            name, text = max(variants, key=lambda v: self._content_score(v[1]))

            mrz_data = self._parse_mrz_from_text(text)
            mrz_data["success"] = True
            mrz_data["engine"] = f"Tesseract-eng ({name})"
            mrz_data["raw_text"] = text[:4000]
            return mrz_data
        except Exception as e:
            return self._empty_result(error=str(e))

    @staticmethod
    def _empty_result(error=None):
        return {
            "success": False,
            "error": error,
            "engine": "Tesseract-eng",
            "raw_text": "",
            "mrz_parsed": False,
            "mrz_type": None,
            "mrz_line": None,
            "document_type": None,
            "country_code": None,
            "surname": None,
            "given_names": None,
            "document_number": None,
            "nationality": None,
            "date_of_birth": None,
            "sex": None,
            "date_of_expiry": None,
        }

    def _ocr_variants(self, image):
        out = []
        base_cfg = "--oem 3 --dpi 300"

        try:
            out.append(("raw-psm3", pytesseract.image_to_string(
                image, lang=self.lang, config=f"{base_cfg} --psm 3")))
        except Exception:
            pass

        try:
            out.append(("raw-psm11", pytesseract.image_to_string(
                image, lang=self.lang, config=f"{base_cfg} --psm 11")))
        except Exception:
            pass

        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

        try:
            out.append(("gray-psm3", pytesseract.image_to_string(
                gray, lang=self.lang, config=f"{base_cfg} --psm 3")))
        except Exception:
            pass

        try:
            clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
            eq = clahe.apply(gray)
            out.append(("clahe-psm3", pytesseract.image_to_string(
                eq, lang=self.lang, config=f"{base_cfg} --psm 3")))
        except Exception:
            pass

        try:
            _, otsu = cv2.threshold(gray, 0, 255,
                                    cv2.THRESH_BINARY + cv2.THRESH_OTSU)
            if 0.02 < (otsu > 127).mean() < 0.98:
                out.append(("otsu-psm11", pytesseract.image_to_string(
                    otsu, lang=self.lang, config=f"{base_cfg} --psm 11")))
        except Exception:
            pass

        if not out:
            out.append(("none", ""))
        return out

    def _content_score(self, text: str) -> int:
        s = 0
        s += 10 * len(re.findall(r"\d{4}\s?\d{4}\s?\d{4}", text))
        s += 10 * len(re.findall(r"\d{3}\s?\d{4}\s?\d{4}", text))
        s +=  8 * len(re.findall(r"[A-Z]{5}\d{4}[A-Z]", text))
        s +=  8 * len(re.findall(r"\b[A-Z]{3}\d{7}\b", text))
        s +=  5 * len(re.findall(r"\d{2}/\d{2}/\d{4}", text))
        s +=  5 * len(re.findall(r"\b(?:19|20)\d{2}\b", text))
        s +=  3 * len(re.findall(r"[A-Z0-9<]{20,}", text))
        s +=  1 * len(re.findall(r"[A-Za-z]{3,}", text))
        return s

    def _parse_mrz_from_text(self, text):
        data = {
            "mrz_parsed": False,
            "mrz_type": None,
            "mrz_line": None,
            "document_type": None,
            "country_code": None,
            "surname": None,
            "given_names": None,
            "document_number": None,
            "nationality": None,
            "date_of_birth": None,
            "sex": None,
            "date_of_expiry": None,
        }

        lines = [line.strip() for line in text.split('\n') if line.strip()]

        for line in lines:
            line_upper = line.upper()

            if "SURNAME" in line_upper:
                parts = re.split(r"[:. ]+", line)
                if len(parts) > 1:
                    surname = parts[-1].strip()
                    if surname and len(surname) < 30 and not surname.isdigit():
                        data["surname"] = surname.upper()

            if "GIVEN NAMES" in line_upper or ("GIVEN" in line_upper and "NAMES" in line_upper):
                parts = re.split(r"[:. ]+", line)
                if len(parts) > 1:
                    given = parts[-1].strip()
                    if given and len(given) < 30 and not given.isdigit():
                        data["given_names"] = given.upper()

            if "COUNTRY" in line_upper:
                parts = re.split(r"[:. ]+", line)
                if len(parts) > 1:
                    country = parts[-1].strip()
                    if country and len(country) < 10 and not country.isdigit():
                        data["country_code"] = country.upper()[:3]

        mrz_line = None
        for line in lines:
            if "<" in line and len(line) > 20:
                clean_line = re.sub(r"[^A-Za-z0-9<]", "", line.upper())
                if len(clean_line) > 20:
                    mrz_line = clean_line
                    break

        if mrz_line and len(mrz_line) >= 30:
            data["mrz_parsed"] = True
            data["mrz_line"] = mrz_line
            data["mrz_type"] = "TD3"

            data["document_number"] = self._clean_document_number(mrz_line[0:9])

            if len(mrz_line) >= 13:
                data["nationality"] = self._clean_country_code(mrz_line[10:13])

            if len(mrz_line) >= 19:
                data["date_of_birth"] = self._clean_dob(mrz_line[13:19])

            if len(mrz_line) >= 21:
                sex_char = mrz_line[20:21]
                data["sex"] = sex_char if sex_char in ("M", "F") else None

            if len(mrz_line) >= 27:
                data["date_of_expiry"] = self._clean_expiry(mrz_line[21:27])

            if mrz_line[0:1] in ("P", "V", "I", "A", "C"):
                data["document_type"] = mrz_line[0:1]

        return data

    def _clean_document_number(self, doc_num):
        replacements = {"A": "4", "B": "8", "O": "0", "D": "0", "S": "5",
                        "Z": "2", "G": "6", "T": "1", "I": "1", "M": "1",
                        "N": "1", "R": "1"}
        cleaned = "".join(replacements.get(c, c) if c.isalpha() else c for c in doc_num)
        cleaned = cleaned.replace("<", "").strip()
        return cleaned if len(cleaned) >= 5 else None

    def _clean_country_code(self, code):
        code = re.sub(r"[^A-Z]", "", code.upper())
        if len(code) >= 3:
            return code[:3]
        common_map = {"US": "USA", "UK": "GBR", "CA": "CAN", "AU": "AUS",
                      "DE": "DEU", "FR": "FRA", "IT": "ITA", "JP": "JPN",
                      "CN": "CHN", "IN": "IND", "BR": "BRA", "RU": "RUS"}
        return common_map.get(code)

    def _clean_dob(self, dob_str):
        char_map = {"A": "4", "B": "4", "O": "0", "D": "0", "S": "5",
                    "Z": "2", "G": "6", "T": "1", "I": "1", "M": "1",
                    "N": "1", "R": "1"}
        cleaned = "".join(char_map.get(c, c) if c.isalpha() else c for c in dob_str.upper())
        digits = re.sub(r"[^0-9]", "", cleaned)
        return digits[:6] if len(digits) >= 6 else None

    def _clean_expiry(self, expiry_str):
        expiry_str = expiry_str.upper().replace("M", "2")
        char_map = {"A": "4", "B": "8", "O": "0", "D": "0", "S": "5",
                    "Z": "2", "G": "6", "T": "1", "I": "1", "N": "1",
                    "R": "1"}
        cleaned = "".join(char_map.get(c, c) if c.isalpha() else c for c in expiry_str)
        digits = re.sub(r"[^0-9]", "", cleaned)
        return digits[:6] if len(digits) >= 6 else None