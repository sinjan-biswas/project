import sys
sys.path.insert(0, '../core-api')
from services.ocr_service import OCRService
import json

ocr = OCRService()

with open("test_passport.jpg", "rb") as f:
    image_bytes = f.read()

result = ocr.extract(image_bytes)
print("OCR Result:")
print(json.dumps(result, indent=2))
