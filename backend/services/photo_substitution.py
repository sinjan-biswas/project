from pathlib import Path
import cv2
import numpy as np
import insightface

BASE_DIR = Path(__file__).resolve().parent.parent
MODEL_DIR = BASE_DIR / "models" / "insightface"
MODEL_DIR.mkdir(parents=True, exist_ok=True)


class PhotoSubstitutionDetector:
    def __init__(self):
        # Auto-detect providers: use GPU if onnxruntime-gpu is installed, else CPU.
        try:
            import onnxruntime as ort
            available = ort.get_available_providers()
            use_gpu = "CUDAExecutionProvider" in available
        except Exception:
            use_gpu = False

        self.app = insightface.app.FaceAnalysis(
            name="buffalo_l",
            root=str(MODEL_DIR),
        )
        # ctx_id: 0 = GPU, -1 = CPU. providers arg is version-dependent → omit it.
        self.app.prepare(ctx_id=0 if use_gpu else -1, det_size=(640, 640))
    def detect(self, image_path: str) -> dict:
        img = cv2.imread(str(image_path))
        if img is None:
            return {"face_found": False, "substitution_score": 0.0}

        faces = self.app.get(img)
        if not faces:
            return {"face_found": False, "substitution_score": 0.0}

        # Largest face
        f = max(faces, key=lambda x: (x.bbox[2] - x.bbox[0]) * (x.bbox[3] - x.bbox[1]))
        x1, y1, x2, y2 = map(int, f.bbox)
        x1, y1 = max(0, x1), max(0, y1)
        x2, y2 = min(img.shape[1], x2), min(img.shape[0], y2)

        face_region = img[y1:y2, x1:x2]
        if face_region.size == 0:
            return {"face_found": True, "substitution_score": 0.0}

        # --- Texture energy: Laplacian variance of face vs surrounding ring ---
        lap_face = cv2.Laplacian(
            cv2.cvtColor(face_region, cv2.COLOR_BGR2GRAY), cv2.CV_64F
        ).var()

        pad = 40
        ry1, ry2 = max(0, y1 - pad), min(img.shape[0], y2 + pad)
        rx1, rx2 = max(0, x1 - pad), min(img.shape[1], x2 + pad)
        ring = img[ry1:ry2, rx1:rx2].copy()

        # Mask out the face area inside the ring
        fy1, fy2 = y1 - ry1, y2 - ry1
        fx1, fx2 = x1 - rx1, x2 - rx1
        ring_gray = cv2.cvtColor(ring, cv2.COLOR_BGR2GRAY).astype(np.float32)
        mask = np.ones_like(ring_gray, dtype=bool)
        mask[fy1:fy2, fx1:fx2] = False

        ring_vals = ring_gray[mask]
        if ring_vals.size == 0:
            return {"face_found": True, "substitution_score": 0.0}

        lap_ring = cv2.Laplacian(
            ring_gray.astype(np.uint8), cv2.CV_64F
        ).astype(np.float32)[mask].var()

        # *** THIS IS THE LINE THAT WENT MISSING ***
        texture_ratio = abs(lap_face - lap_ring) / max(lap_ring, 1.0)

        # --- Color temperature shift between face and ring ---
        mean_face = face_region.reshape(-1, 3).mean(0)
        ring_bgr = ring.reshape(-1, 3)[mask.ravel()]
        mean_ring = ring_bgr.mean(0) if ring_bgr.size else mean_face
        color_shift = float(np.linalg.norm(mean_face - mean_ring))

        # --- Calibrated scoring (softer curve — only extreme cases hit 1.0) ---
        texture_term = min(1.0, max(0.0, (texture_ratio - 0.5) / 2.0))
        color_term   = min(1.0, max(0.0, (color_shift  - 20.0) / 40.0))
        score = 0.5 * texture_term + 0.5 * color_term

        return {
            "face_found": True,
            "substitution_score": round(float(score), 3),
            "confidence": float(f.det_score),
            "texture_ratio": round(float(texture_ratio), 3),
            "color_shift": round(color_shift, 2),
        }