import sys
import os
import cv2
import numpy as np
from PIL import Image
import json

# Add DocAuth to path
DOCAUTH_PATH = os.path.join(os.path.dirname(__file__), 'docauth')
sys.path.insert(0, DOCAUTH_PATH)

# Try to import DocAuth components
DOCAUTH_AVAILABLE = False
try:
    try:
        from docauth import CopyMoveDetector, ELAnalyzer, EdgeDetector
        DOCAUTH_AVAILABLE = True
    except ImportError:
        try:
            from docauth.detectors import CopyMoveDetector, ELAnalyzer, EdgeDetector
            DOCAUTH_AVAILABLE = True
        except ImportError:
            try:
                from docauth.copy_move.detector import CopyMoveDetector
                from docauth.analysis.ela import ELAnalyzer
                from docauth.analysis.edge import EdgeDetector
                DOCAUTH_AVAILABLE = True
            except ImportError:
                print("⚠️ DocAuth not found, using fallback")
                DOCAUTH_AVAILABLE = False
except Exception as e:
    print(f"⚠️ DocAuth import error: {e}")
    DOCAUTH_AVAILABLE = False

def convert_to_native(obj):
    """Convert numpy types to Python native types for JSON serialization"""
    if isinstance(obj, np.float32) or isinstance(obj, np.float64):
        return float(obj)
    elif isinstance(obj, np.int32) or isinstance(obj, np.int64):
        return int(obj)
    elif isinstance(obj, np.bool_):
        return bool(obj)
    elif isinstance(obj, dict):
        return {k: convert_to_native(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [convert_to_native(item) for item in obj]
    elif isinstance(obj, tuple):
        return tuple(convert_to_native(item) for item in obj)
    elif isinstance(obj, np.ndarray):
        return obj.tolist()
    return obj

class TamperingDetector:
    def __init__(self):
        self.weights = {
            'ela': 0.35,
            'copy_move': 0.35,
            'edge': 0.30
        }
        self.thresholds = {
            'ela_warn': 0.12,
            'ela_reject': 0.22,
            'copy_move': 0.50,
            'edge': 0.40
        }
        
        # Initialize detectors if available
        self.ela_detector = None
        self.copy_move_detector = None
        self.edge_detector = None
        
        if DOCAUTH_AVAILABLE:
            try:
                self.ela_detector = ELAnalyzer()
                self.copy_move_detector = CopyMoveDetector()
                self.edge_detector = EdgeDetector()
                print("✅ DocAuth detectors initialized")
            except Exception as e:
                print(f"⚠️ Failed to initialize detectors: {e}")
        
        if not DOCAUTH_AVAILABLE or self.ela_detector is None:
            print("⚠️ Using simple ELA fallback")
    
    def analyze(self, image_path: str):
        """Analyze document for tampering"""
        if not os.path.exists(image_path):
            return convert_to_native(self._get_fallback_data("Image not found"))
        
        try:
            # Load image
            image = cv2.imread(image_path)
            if image is None:
                return convert_to_native(self._get_fallback_data("Could not load image"))
            
            # If DocAuth is not available, use simple ELA
            if not DOCAUTH_AVAILABLE or self.ela_detector is None:
                ela_score = self._simple_ela(image_path)
                # Convert numpy types to Python types
                ela_score = float(ela_score) if isinstance(ela_score, (np.float32, np.float64)) else ela_score
                is_tampered = ela_score > self.thresholds['ela_warn']
                
                result = {
                    "tampering_score": round(float(ela_score * 100), 2),
                    "ela_score": round(float(ela_score * 100), 2),
                    "copy_move_score": 0.0,
                    "edge_score": 0.0,
                    "heatmap_path": None,
                    "is_tampered": bool(is_tampered),
                    "note": "Using simple ELA detection (DocAuth not available)"
                }
                return convert_to_native(result)
            
            # Run ELA analysis
            ela_score = 0.0
            try:
                ela_result = self.ela_detector.analyze(image)
                ela_score = ela_result.get('score', 0.0)
                ela_score = float(ela_score) if isinstance(ela_score, (np.float32, np.float64)) else ela_score
                print(f"📊 ELA Score: {ela_score}")
            except Exception as e:
                print(f"⚠️ ELA analysis failed: {e}")
                ela_score = float(self._simple_ela(image_path))
            
            # Run Copy-Move detection
            copy_move_score = 0.0
            if self.copy_move_detector:
                try:
                    copy_move_result = self.copy_move_detector.detect(image)
                    copy_move_score = copy_move_result.get('score', 0.0)
                    copy_move_score = float(copy_move_score) if isinstance(copy_move_score, (np.float32, np.float64)) else copy_move_score
                    print(f"📊 Copy-Move Score: {copy_move_score}")
                except Exception as e:
                    print(f"⚠️ Copy-Move detection failed: {e}")
            
            # Run Edge detection
            edge_score = 0.0
            if self.edge_detector:
                try:
                    edge_result = self.edge_detector.detect(image)
                    edge_score = edge_result.get('score', 0.0)
                    edge_score = float(edge_score) if isinstance(edge_score, (np.float32, np.float64)) else edge_score
                    print(f"📊 Edge Score: {edge_score}")
                except Exception as e:
                    print(f"⚠️ Edge detection failed: {e}")
            
            # Calculate final weighted score
            final_score = (
                float(self.weights['ela']) * float(ela_score) +
                float(self.weights['copy_move']) * float(copy_move_score) +
                float(self.weights['edge']) * float(edge_score)
            )
            
            # Determine if tampered
            is_tampered = (
                ela_score > self.thresholds['ela_warn'] or
                copy_move_score > self.thresholds['copy_move'] or
                edge_score > self.thresholds['edge']
            )
            
            result = {
                "tampering_score": round(float(final_score * 100), 2),
                "ela_score": round(float(ela_score * 100), 2),
                "copy_move_score": round(float(copy_move_score * 100), 2),
                "edge_score": round(float(edge_score * 100), 2),
                "heatmap_path": None,
                "is_tampered": bool(is_tampered),
                "note": "Using DocAuth tampering detection" if DOCAUTH_AVAILABLE else "Using ELA fallback"
            }
            
            return convert_to_native(result)
            
        except Exception as e:
            print(f"❌ Tampering analysis error: {e}")
            import traceback
            traceback.print_exc()
            return convert_to_native(self._get_fallback_data(str(e)))
    
    def _simple_ela(self, image_path):
        """Simple Error Level Analysis"""
        try:
            from PIL import Image
            import numpy as np
            
            original = Image.open(image_path).convert('RGB')
            temp_path = "/tmp/ela_temp.jpg"
            original.save(temp_path, 'JPEG', quality=90)
            compressed = Image.open(temp_path)
            
            orig_array = np.array(original).astype(np.float32)
            comp_array = np.array(compressed).astype(np.float32)
            
            diff = np.abs(orig_array - comp_array)
            avg_diff = np.mean(diff) / 255.0
            
            # Ensure Python float
            avg_diff = float(avg_diff) if isinstance(avg_diff, (np.float32, np.float64)) else avg_diff
            
            if os.path.exists(temp_path):
                os.remove(temp_path)
            
            return avg_diff
        except Exception as e:
            print(f"⚠️ Simple ELA failed: {e}")
            return 0.0
    
    def _get_fallback_data(self, error_msg):
        return {
            "tampering_score": 0.0,
            "ela_score": 0.0,
            "copy_move_score": 0.0,
            "edge_score": 0.0,
            "heatmap_path": None,
            "is_tampered": False,
            "note": f"Fallback: {error_msg}"
        }