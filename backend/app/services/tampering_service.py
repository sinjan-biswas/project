import sys
import os

# Add tampering-dl to path
TAMPERING_PATH = os.path.join(os.path.dirname(__file__), '../../tampering-dl')
if TAMPERING_PATH not in sys.path:
    sys.path.insert(0, TAMPERING_PATH)

# Import the tampering detector
from tampering_service import TamperingDetector

# Re-export for the main app
__all__ = ['TamperingDetector']