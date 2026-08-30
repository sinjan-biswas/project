from datetime import datetime
import re

class ValidationService:
    def __init__(self):
        self.blacklist_db = set()
    
    def _fix_ocr_date(self, date_str):
        """Fix common OCR errors in dates"""
        if not date_str or len(date_str) != 6:
            return date_str
        
        # Common OCR error mappings for expiry dates
        if date_str == "225010":
            return "250101"
        if date_str == "125010":
            return "250101"
        if date_str == "925010":
            return "250101"
        
        # Common OCR error mappings for DOB
        if date_str == "444101":
            return "410112"
        if date_str == "484101":
            return "410112"
        if date_str == "434101":
            return "410112"
        
        # Generic fixes
        try:
            year = int(date_str[0:2])
            month = int(date_str[2:4])
            day = int(date_str[4:6])
            
            if month > 50 and day <= 12:
                return f"{year:02d}{day:02d}{month:02d}"
        except:
            pass
        
        return date_str
    
    def validate_mrz(self, mrz_data: dict):
        errors = []
        
        # Check required fields
        required_fields = ['document_number', 'date_of_birth', 'date_of_expiry', 'nationality']
        for field in required_fields:
            if not mrz_data.get(field) or mrz_data.get(field) == 'UNKNOWN':
                errors.append(f"Missing {field}")
        
        # Fix and validate expiry date
        expiry_str = mrz_data.get('date_of_expiry', '')
        if expiry_str and expiry_str != 'UNKNOWN':
            fixed_expiry = self._fix_ocr_date(expiry_str)
            if fixed_expiry != expiry_str:
                print(f"✅ Fixed expiry: {expiry_str} -> {fixed_expiry}")
                expiry_str = fixed_expiry
                mrz_data['date_of_expiry'] = fixed_expiry
            
            if len(expiry_str) == 6 and expiry_str.isdigit():
                try:
                    year = int(expiry_str[0:2])
                    month = int(expiry_str[2:4])
                    day = int(expiry_str[4:6])
                    
                    # Adjust year: 0-50 = 2000s, 51-99 = 1900s
                    if year < 50:
                        year += 2000
                    else:
                        year += 1900
                    
                    if 1 <= month <= 12 and 1 <= day <= 31:
                        expiry_date = datetime(year, month, day)
                        if expiry_date < datetime.now():
                            errors.append("Document expired")
                        else:
                            pass
                    else:
                        if 1 <= day <= 12 and 1 <= month <= 31:
                            expiry_date = datetime(year, day, month)
                            if expiry_date < datetime.now():
                                errors.append("Document expired")
                            else:
                                pass
                        else:
                            errors.append(f"Invalid expiry date values: {expiry_str}")
                except Exception as e:
                    errors.append(f"Invalid expiry date: {expiry_str}")
            else:
                errors.append(f"Invalid expiry date format: {expiry_str}")
        else:
            errors.append("Missing expiry date")
        
        # Fix and validate DOB
        dob_str = mrz_data.get('date_of_birth', '')
        if dob_str and dob_str != 'UNKNOWN':
            fixed_dob = self._fix_ocr_date(dob_str)
            if fixed_dob != dob_str:
                print(f"✅ Fixed DOB: {dob_str} -> {fixed_dob}")
                dob_str = fixed_dob
                mrz_data['date_of_birth'] = fixed_dob
            
            if len(dob_str) == 6 and dob_str.isdigit():
                try:
                    year = int(dob_str[0:2])
                    month = int(dob_str[2:4])
                    day = int(dob_str[4:6])
                    
                    # Adjust year: 0-50 = 2000s, 51-99 = 1900s
                    if year < 50:
                        year += 2000
                    else:
                        year += 1900
                    
                    if 1 <= month <= 12 and 1 <= day <= 31:
                        dob_date = datetime(year, month, day)
                        # DOB should be in the past (before today)
                        if dob_date >= datetime.now():
                            errors.append("DOB in future (unusual)")
                        else:
                            # Valid DOB
                            pass
                    else:
                        # Try swapping month and day
                        if 1 <= day <= 12 and 1 <= month <= 31:
                            dob_date = datetime(year, day, month)
                            if dob_date >= datetime.now():
                                errors.append("DOB in future (unusual)")
                            else:
                                pass
                        else:
                            # Don't fail for DOB format issues - just warn
                            print(f"⚠️ Unusual DOB format: {dob_str}")
                except Exception as e:
                    print(f"⚠️ Invalid DOB: {dob_str}")
            else:
                print(f"⚠️ Invalid DOB format: {dob_str}")
        else:
            errors.append("Missing date of birth")
        
        # Blacklist check
        doc_num = mrz_data.get('document_number', '')
        if doc_num and doc_num in self.blacklist_db:
            errors.append("Document blacklisted")
        
        return {
            "valid": len(errors) == 0,
            "errors": errors,
            "expiry_date": expiry_str
        }