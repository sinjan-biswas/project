import sys
import os

# Add tampering-dl to path
TAMPERING_PATH = os.path.join(os.path.dirname(__file__), '../../tampering-dl')
if TAMPERING_PATH not in sys.path:
    sys.path.insert(0, TAMPERING_PATH)

# Import the tampering detector
try:
    from tampering_service import TamperingDetector
    print("✅ TamperingDetector imported successfully")
except Exception as e:
    print(f"⚠️ Failed to import TamperingDetector: {e}")
    # Fallback
    class TamperingDetector:
        def __init__(self):
            print("⚠️ Using fallback TamperingDetector")
        def analyze(self, image_path):
            return {
                "tampering_score": 0.0,
                "ela_score": 0.0,
                "copy_move_score": 0.0,
                "edge_score": 0.0,
                "heatmap_path": None,
                "is_tampered": False,
                "note": "Fallback detector"
            }

__all__ = ['TamperingDetector']
