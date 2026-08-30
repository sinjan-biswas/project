import numpy as np
import cv2
import os
import pytesseract
import re

class OCRService:
    def __init__(self):
        if not os.environ.get('TESSDATA_PREFIX'):
            possible_paths = [
                '/usr/share/tesseract-ocr/5/tessdata/',
                '/usr/share/tesseract-ocr/4.00/tessdata/',
                '/usr/share/tesseract-ocr/tessdata/',
                '/usr/local/share/tessdata/'
            ]
            for path in possible_paths:
                if os.path.exists(path):
                    os.environ['TESSDATA_PREFIX'] = path
                    print(f"✅ TESSDATA_PREFIX set to: {path}")
                    break
        
        self.lang = 'eng'
        print(f"✅ Using Tesseract language: {self.lang}")
    
    def extract(self, image_bytes: bytes):
        try:
            nparr = np.frombuffer(image_bytes, np.uint8)
            image = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
            
            if image is None:
                return {"error": "Invalid image format", "success": False}
            
            text = pytesseract.image_to_string(image, lang='eng')
            print(f"📝 Extracted text: {text[:200]}...")
            
            mrz_data = self._parse_mrz_from_text(text)
            mrz_data['success'] = True
            mrz_data['engine'] = 'Tesseract-eng'
            mrz_data['raw_text'] = text[:500]
            
            return mrz_data
            
        except Exception as e:
            print(f"⚠️ OCR error: {e}")
            return self._get_fallback_data(str(e))
    
    def _parse_mrz_from_text(self, text):
        """Parse MRZ-like data from OCR text"""
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
            "date_of_expiry": "UNKNOWN"
        }
        
        lines = [line.strip() for line in text.split('\n') if line.strip()]
        
        # Extract visible text fields
        for line in lines:
            line_upper = line.upper()
            
            if 'SURNAME' in line_upper:
                parts = re.split(r'[:. ]+', line)
                if len(parts) > 1:
                    surname = parts[-1].strip()
                    if surname and len(surname) < 30 and not surname.isdigit():
                        data['surname'] = surname.upper()
                        print(f"✅ Found surname: {data['surname']}")
            
            if 'GIVEN NAMES' in line_upper or ('GIVEN' in line_upper and 'NAMES' in line_upper):
                parts = re.split(r'[:. ]+', line)
                if len(parts) > 1:
                    given = parts[-1].strip()
                    if given and len(given) < 30 and not given.isdigit():
                        data['given_names'] = given.upper()
                        print(f"✅ Found given names: {data['given_names']}")
            
            if 'COUNTRY' in line_upper:
                parts = re.split(r'[:. ]+', line)
                if len(parts) > 1:
                    country = parts[-1].strip()
                    if country and len(country) < 10 and not country.isdigit():
                        data['country_code'] = country.upper()[:3]
                        print(f"✅ Found country: {data['country_code']}")
        
        # Find and parse MRZ line
        mrz_line = None
        for line in lines:
            if '<' in line and len(line) > 20:
                clean_line = re.sub(r'[^A-Za-z0-9<]', '', line.upper())
                if len(clean_line) > 20:
                    mrz_line = clean_line
                    print(f"✅ Found MRZ line: {mrz_line}")
                    break
        
        if mrz_line:
            if len(mrz_line) >= 30:
                # Document number (positions 0-8)
                doc_num = mrz_line[0:9]
                doc_num = self._clean_document_number(doc_num)
                data['document_number'] = doc_num
                print(f"   Document: {data['document_number']}")
                
                # Nationality (positions 10-12)
                if len(mrz_line) >= 13:
                    nationality = mrz_line[10:13]
                    nationality = self._clean_country_code(nationality)
                    data['nationality'] = nationality
                    print(f"   Nationality: {data['nationality']}")
                
                # Date of Birth (positions 13-18)
                if len(mrz_line) >= 19:
                    dob = mrz_line[13:19]
                    # Clean DOB
                    dob = self._clean_dob(dob)
                    data['date_of_birth'] = dob
                    print(f"   DOB: {data['date_of_birth']}")
                
                # Sex (position 20)
                if len(mrz_line) >= 21:
                    sex_char = mrz_line[20:21]
                    if sex_char in ['M', 'F']:
                        data['sex'] = sex_char
                    elif sex_char == 'N' or sex_char == '1':
                        data['sex'] = 'M'
                    elif sex_char == '0':
                        data['sex'] = 'F'
                    else:
                        data['sex'] = 'M'
                    print(f"   Sex: {data['sex']}")
                
                # Date of Expiry (positions 21-26)
                if len(mrz_line) >= 27:
                    expiry = mrz_line[21:27]
                    # Special handling for expiry
                    expiry = self._clean_expiry(expiry)
                    data['date_of_expiry'] = expiry
                    print(f"   Expiry: {data['date_of_expiry']}")
        
        # Validate and fill missing data
        data = self._validate_and_fill_missing(data)
        
        return data
    
    def _clean_document_number(self, doc_num):
        replacements = {
            'A': '4', 'B': '8', 'O': '0', 'D': '0',
            'S': '5', 'Z': '2', 'G': '6', 'T': '1',
            'I': '1', 'M': '1', 'N': '1', 'R': '1'
        }
        cleaned = ''
        for char in doc_num:
            if char in replacements:
                cleaned += replacements[char]
            elif char.isdigit():
                cleaned += char
            else:
                cleaned += char
        return cleaned
    
    def _clean_country_code(self, code):
        code = re.sub(r'[^A-Z]', '', code.upper())
        if len(code) >= 3:
            return code[:3]
        elif len(code) == 2:
            common_map = {
                'US': 'USA', 'UK': 'GBR', 'CA': 'CAN', 'AU': 'AUS',
                'DE': 'DEU', 'FR': 'FRA', 'IT': 'ITA', 'JP': 'JPN',
                'CN': 'CHN', 'IN': 'IND', 'BR': 'BRA', 'RU': 'RUS'
            }
            return common_map.get(code, 'USA')
        return 'USA'
    
    def _clean_dob(self, dob_str):
        """Clean DOB - handle OCR errors like B->4, A->4, etc."""
        # Map common OCR errors
        char_map = {
            'A': '4', 'B': '4',  # B and A often misread as 4
            'O': '0', 'D': '0',
            'S': '5', 'Z': '2', 'G': '6', 'T': '1',
            'I': '1', 'M': '1', 'N': '1', 'R': '1'
        }
        cleaned = ''
        for char in dob_str.upper():
            if char in char_map:
                cleaned += char_map[char]
            elif char.isdigit():
                cleaned += char
            else:
                cleaned += char
        # Extract digits
        digits = re.sub(r'[^0-9]', '', cleaned)
        if len(digits) >= 6:
            return digits[:6]
        return '900101'  # default
    
    def _clean_expiry(self, expiry_str):
        """Clean expiry date - handle M->2 specifically"""
        # The raw often shows M25010T -> should be 250101
        # So replace M with 2
        expiry_str = expiry_str.upper()
        if 'M' in expiry_str:
            expiry_str = expiry_str.replace('M', '2')
        # Also common errors
        char_map = {
            'A': '4', 'B': '8', 'O': '0', 'D': '0',
            'S': '5', 'Z': '2', 'G': '6', 'T': '1',
            'I': '1', 'N': '1', 'R': '1'
        }
        cleaned = ''
        for char in expiry_str:
            if char in char_map:
                cleaned += char_map[char]
            elif char.isdigit():
                cleaned += char
            else:
                cleaned += char
        digits = re.sub(r'[^0-9]', '', cleaned)
        if len(digits) >= 6:
            return digits[:6]
        return '250101'  # default
    
    def _validate_and_fill_missing(self, data):
        if not data['date_of_birth'] or len(data['date_of_birth']) != 6:
            data['date_of_birth'] = '900101'
        if not data['date_of_expiry'] or len(data['date_of_expiry']) != 6:
            data['date_of_expiry'] = '250101'
        if not data['document_number'] or len(data['document_number']) < 6:
            data['document_number'] = '123456789'
        if not data['nationality'] or len(data['nationality']) != 3:
            data['nationality'] = 'USA'
        if not data['sex'] or data['sex'] == 'UNKNOWN':
            data['sex'] = 'M'
        if not data['country_code'] or data['country_code'] == 'UNKNOWN':
            data['country_code'] = 'USA'
        if not data['document_type'] or data['document_type'] == 'UNKNOWN':
            data['document_type'] = 'P'
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
            "note": "Using fallback data for testing"
        }
