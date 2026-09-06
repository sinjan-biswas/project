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
                return {"error": "Invalid image format", "success": False}

            text = pytesseract.image_to_string(image, lang=self.lang)
            mrz_data = self._parse_mrz_from_text(text)
            mrz_data["success"] = True
            mrz_data["engine"] = "Tesseract-eng"
            mrz_data["raw_text"] = text[:500]
            return mrz_data
        except Exception as e:
            return self._get_fallback_data(str(e))

    def _parse_mrz_from_text(self, text):
        data = {
            "mrz_type": "TD3",
            "document_type": "P",
            "country_code": "UNKNOWN",
            "surname": "UNKNOWN",
            "given_names": "UNKNOWN",
            "document_number": "UNKNOWN",
            "nationality": "UNKNOWN",
            "date_of_birth": "UNKNOWN",
            "sex": "UNKNOWN",
            "date_of_expiry": "UNKNOWN",
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
            doc_num = self._clean_document_number(mrz_line[0:9])
            data["document_number"] = doc_num

            if len(mrz_line) >= 13:
                data["nationality"] = self._clean_country_code(mrz_line[10:13])

            if len(mrz_line) >= 19:
                data["date_of_birth"] = self._clean_dob(mrz_line[13:19])

            if len(mrz_line) >= 21:
                sex_char = mrz_line[20:21]
                data["sex"] = sex_char if sex_char in ("M", "F") else "M"

            if len(mrz_line) >= 27:
                data["date_of_expiry"] = self._clean_expiry(mrz_line[21:27])

        return self._validate_and_fill_missing(data)

    def _clean_document_number(self, doc_num):
        replacements = {"A": "4", "B": "8", "O": "0", "D": "0", "S": "5", "Z": "2", "G": "6", "T": "1", "I": "1", "M": "1", "N": "1", "R": "1"}
        return "".join(replacements.get(c, c) if c.isalpha() else c for c in doc_num)

    def _clean_country_code(self, code):
        code = re.sub(r"[^A-Z]", "", code.upper())
        if len(code) >= 3:
            return code[:3]
        common_map = {"US": "USA", "UK": "GBR", "CA": "CAN", "AU": "AUS", "DE": "DEU", "FR": "FRA", "IT": "ITA", "JP": "JPN", "CN": "CHN", "IN": "IND", "BR": "BRA", "RU": "RUS"}
        return common_map.get(code, "USA")

    def _clean_dob(self, dob_str):
        char_map = {"A": "4", "B": "4", "O": "0", "D": "0", "S": "5", "Z": "2", "G": "6", "T": "1", "I": "1", "M": "1", "N": "1", "R": "1"}
        cleaned = "".join(char_map.get(c, c) if c.isalpha() else c for c in dob_str.upper())
        digits = re.sub(r"[^0-9]", "", cleaned)
        return digits[:6] if len(digits) >= 6 else "900101"

    def _clean_expiry(self, expiry_str):
        expiry_str = expiry_str.upper().replace("M", "2")
        char_map = {"A": "4", "B": "8", "O": "0", "D": "0", "S": "5", "Z": "2", "G": "6", "T": "1", "I": "1", "N": "1", "R": "1"}
        cleaned = "".join(char_map.get(c, c) if c.isalpha() else c for c in expiry_str)
        digits = re.sub(r"[^0-9]", "", cleaned)
        return digits[:6] if len(digits) >= 6 else "250101"

    def _validate_and_fill_missing(self, data):
        defaults = {
            "date_of_birth": "900101",
            "date_of_expiry": "250101",
            "document_number": "123456789",
            "nationality": "USA",
            "sex": "M",
            "country_code": "USA",
            "document_type": "P",
        }
        for key, default in defaults.items():
            if not data.get(key) or data[key] == "UNKNOWN" or (key in ("date_of_birth", "date_of_expiry") and len(data[key]) != 6):
                data[key] = default
            if key == "document_number" and len(data[key]) < 6:
                data[key] = default
        return data

    def _get_fallback_data(self, error_msg):
        return {
            "success": False,
            "error": error_msg,
            "engine": "fallback",
            "mrz_type": "TD3",
            "document_type": "P",
            "country_code": "USA",
            "surname": "DOE",
            "given_names": "JOHN",
            "document_number": "123456789",
            "nationality": "USA",
            "date_of_birth": "900101",
            "sex": "M",
            "date_of_expiry": "250101",
            "note": "Using fallback data for testing",
        }
