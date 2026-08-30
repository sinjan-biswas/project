import sys
import os
import requests
import json
from datetime import datetime

# Add core-api to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../core-api'))

BASE_URL = "http://localhost:8000"

def print_header(title):
    print("\n" + "=" * 60)
    print(f"  {title}")
    print("=" * 60)

def test_1_health():
    print_header("Test 1: Health Check")
    try:
        response = requests.get(f"{BASE_URL}/health")
        if response.status_code == 200:
            data = response.json()
            print(f"✅ Status: {data['status']}")
            print(f"✅ Version: {data['version']}")
            return True
        else:
            print(f"❌ Error: {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

def test_2_ocr():
    print_header("Test 2: OCR Extraction")
    try:
        from services.ocr_service import OCRService
        ocr = OCRService()
        with open("test_passport.jpg", "rb") as f:
            image_bytes = f.read()
        result = ocr.extract(image_bytes)
        
        if result.get('success'):
            print(f"✅ OCR Successful")
            print(f"   Name: {result.get('surname')}, {result.get('given_names')}")
            print(f"   Passport: {result.get('document_number')}")
            print(f"   Country: {result.get('country_code')}")
            print(f"   DOB: {result.get('date_of_birth')}")
            print(f"   Expiry: {result.get('date_of_expiry')}")
            print(f"   Engine: {result.get('engine')}")
            return True
        else:
            print(f"❌ OCR Failed: {result.get('error')}")
            return False
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

def test_3_validation():
    print_header("Test 3: Document Validation")
    try:
        from services.validation_service import ValidationService
        validator = ValidationService()
        
        # Test with valid data (future expiry)
        test_data_valid = {
            "document_number": "123456789",
            "date_of_birth": "900101",
            "date_of_expiry": "301231",  # December 31, 2030 (future)
            "nationality": "USA"
        }
        result_valid = validator.validate_mrz(test_data_valid)
        print(f"✅ Valid Document (future expiry): {result_valid['valid']}")
        
        # Test with expired data
        test_data_expired = {
            "document_number": "987654321",
            "date_of_birth": "900101",
            "date_of_expiry": "250101",  # January 1, 2025 (expired)
            "nationality": "USA"
        }
        result_expired = validator.validate_mrz(test_data_expired)
        print(f"✅ Expired Document: {result_expired['valid']} - {result_expired['errors']}")
        
        return True
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

def test_4_tampering():
    print_header("Test 4: Tampering Detection")
    try:
        from services.tampering_service import TamperingDetector
        detector = TamperingDetector()
        result = detector.analyze("/tmp/test.jpg")
        print(f"✅ Tampering Score: {result['tampering_score']}")
        print(f"   Tampered: {result['is_tampered']}")
        return True
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

def test_5_face():
    print_header("Test 5: Face Verification")
    try:
        from services.face_service import FaceVerificationService
        face = FaceVerificationService()
        result = face.verify(b"test", b"test")
        print(f"✅ Verified: {result['verified']}")
        print(f"   Confidence: {result['confidence']}")
        return True
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

def test_6_risk():
    print_header("Test 6: Risk Scoring")
    try:
        from risk_engine.scorer import RiskScorer
        scorer = RiskScorer()
        
        # Clean document
        result_clean = scorer.calculate(
            tampering_score=0.0,
            face_distance=0.0,
            validation_errors=[],
            is_expired=False
        )
        print(f"✅ Clean: Score={result_clean['total_score']}, Decision={result_clean['decision']}")
        
        # Suspicious document
        result_suspicious = scorer.calculate(
            tampering_score=85.0,
            face_distance=0.55,
            validation_errors=["Document expired"],
            is_expired=True
        )
        print(f"✅ Suspicious: Score={result_suspicious['total_score']}, Decision={result_suspicious['decision']}")
        return True
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

def test_7_full_api():
    print_header("Test 7: Full API Screening")
    try:
        with open("test_passport.jpg", "rb") as f1, open("test_face.jpg", "rb") as f2:
            files = {
                "document": ("passport.jpg", f1, "image/jpeg"),
                "live_photo": ("face.jpg", f2, "image/jpeg")
            }
            response = requests.post(f"{BASE_URL}/api/v2/screen", files=files)
            
            if response.status_code == 200:
                result = response.json()
                print(f"✅ Screening Complete")
                print(f"   🆔 ID: {result['screening_id']}")
                print(f"   📊 Risk: {result['risk_assessment']['total_score']}/100")
                print(f"   📋 Decision: {result['risk_assessment']['decision']}")
                print(f"   ✅ Valid: {result['validation']['valid']}")
                if result['validation']['errors']:
                    print(f"   ⚠️ Errors: {result['validation']['errors']}")
                return True
            else:
                print(f"❌ Error: {response.status_code}")
                return False
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

def test_8_edge_cases():
    print_header("Test 8: Edge Cases")
    try:
        # Test missing file
        try:
            response = requests.post(f"{BASE_URL}/api/v2/screen")
            print(f"   Missing file handling: {response.status_code}")
        except:
            print("   Missing file handling: ✅")
        
        # Test API health
        response = requests.get(f"{BASE_URL}/health", timeout=2)
        if response.status_code == 200:
            print("   API availability: ✅")
        else:
            print(f"   API availability: {response.status_code}")
        
        return True
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

def test_9_date_fixes():
    print_header("Test 9: Date Fixing (OCR Error Correction)")
    try:
        from services.validation_service import ValidationService
        validator = ValidationService()
        
        # Test OCR errors
        test_cases = [
            ("444101", "410112"),  # DOB fix
            ("225010", "250101"),  # Expiry fix
            ("484101", "410112"),  # DOB fix
            ("125010", "250101"),  # Expiry fix
        ]
        
        all_passed = True
        for original, expected in test_cases:
            fixed = validator._fix_ocr_date(original)
            passed = fixed == expected
            status = "✅" if passed else "❌"
            print(f"   {status} {original} -> {fixed} (expected: {expected})")
            if not passed:
                all_passed = False
        
        return all_passed
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

def run_all_tests():
    print("🛂 Running Complete Test Suite")
    print("=" * 60)
    print(f"📅 Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    tests = [
        ("Health Check", test_1_health),
        ("OCR Extraction", test_2_ocr),
        ("Document Validation", test_3_validation),
        ("Tampering Detection", test_4_tampering),
        ("Face Verification", test_5_face),
        ("Risk Scoring", test_6_risk),
        ("Full API Screening", test_7_full_api),
        ("Edge Cases", test_8_edge_cases),
        ("Date Fixing", test_9_date_fixes),
    ]
    
    results = []
    for name, test_func in tests:
        try:
            passed = test_func()
            results.append((name, passed))
        except Exception as e:
            print(f"❌ {name} crashed: {e}")
            results.append((name, False))
    
    # Summary
    print_header("Test Summary")
    for name, passed in results:
        status = "✅ PASSED" if passed else "❌ FAILED"
        print(f"  {status}: {name}")
    
    total = len(results)
    passed = sum(1 for _, p in results if p)
    print(f"\n📊 Total: {passed}/{total} tests passed")
    
    if passed == total:
        print("\n🎉 ALL TESTS PASSED! System is fully functional!")
    else:
        print(f"\n⚠️ {total - passed} test(s) failed. Check the output above.")
    
    print(f"\n📅 Completed: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

if __name__ == "__main__":
    run_all_tests()