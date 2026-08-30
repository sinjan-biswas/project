import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../core-api'))

from services.ocr_service import OCRService
from services.validation_service import ValidationService
import json

print("🛂 Testing OCR + Validation")
print("=" * 50)

# 1. OCR
ocr = OCRService()
with open("test_passport.jpg", "rb") as f:
    image_bytes = f.read()

ocr_result = ocr.extract(image_bytes)
print("\n📝 OCR Result:")
print(json.dumps(ocr_result, indent=2, default=str))

# 2. Validation
validator = ValidationService()
validation_result = validator.validate_mrz(ocr_result)

print("\n✅ Validation Result:")
print(json.dumps(validation_result, indent=2))

# 3. Summary
print("\n📊 Summary:")
print(f"   Valid: {validation_result['valid']}")
if validation_result['errors']:
    print(f"   Errors: {validation_result['errors']}")
else:
    print("   ✅ No errors - Document is valid!")
print(f"   Expiry: {validation_result['expiry_date']}")
print(f"   DOB: {ocr_result.get('date_of_birth')}")
print(f"   Name: {ocr_result.get('surname')}, {ocr_result.get('given_names')}")