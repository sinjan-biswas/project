# app/services/liveness.py
import cv2
import numpy as np
import mediapipe as mp
from typing import Optional

mp_face_mesh = mp.solutions.face_mesh
face_mesh = mp_face_mesh.FaceMesh(
    static_image_mode=False,
    max_num_faces=1,
    refine_landmarks=True,
    min_detection_confidence=0.5,
    min_tracking_confidence=0.5,
)

# MediaPipe FaceMesh eye landmark indices (6-point contour)
LEFT_EYE = [33, 160, 158, 133, 153, 144]
RIGHT_EYE = [362, 385, 387, 263, 373, 380]


def _euclidean(p1, p2) -> float:
    return float(np.linalg.norm(np.array(p1) - np.array(p2)))


def eye_aspect_ratio(landmarks, eye_indices) -> float:
    """EAR = (||p2-p6|| + ||p3-p5||) / (2 * ||p1-p4||)"""
    pts = [landmarks[i] for i in eye_indices]
    A = _euclidean(pts[1], pts[5])  # p2-p6
    B = _euclidean(pts[2], pts[4])  # p3-p5
    C = _euclidean(pts[0], pts[3])  # p1-p4
    if C == 0:
        return 0.0
    return (A + B) / (2.0 * C)


def extract_landmarks(frame_bgr: np.ndarray) -> Optional[list[tuple[float, float]]]:
    """Extract FaceMesh landmarks from a BGR frame."""
    rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
    results = face_mesh.process(rgb)
    if not results.multi_face_landmarks:
        return None
    h, w = frame_bgr.shape[:2]
    return [(lm.x * w, lm.y * h) for lm in results.multi_face_landmarks[0].landmark]


def compute_ear_from_landmarks(landmarks) -> float:
    """Compute averaged EAR from both eyes."""
    if landmarks is None:
        return 0.0
    left = eye_aspect_ratio(landmarks, LEFT_EYE)
    right = eye_aspect_ratio(landmarks, RIGHT_EYE)
    return (left + right) / 2.0


class BlinkDetector:
    def __init__(self, ear_threshold: float = 0.21, consec_frames: int = 2):
        self.ear_threshold = ear_threshold
        self.consec_frames = consec_frames
        self.frame_counter = 0
        self.blink_in_progress = False

    def update(self, ear: float) -> bool:
        blink_detected = False
        if ear < self.ear_threshold:
            self.frame_counter += 1
            if self.frame_counter >= self.consec_frames:
                self.blink_in_progress = True
        else:
            if self.blink_in_progress:
                blink_detected = True
                self.blink_in_progress = False
            self.frame_counter = 0
        return blink_detected


def check_face_aligned(landmarks, frame_shape, margin: float = 0.05) -> bool:
    """Face is present, roughly centered, and at reasonable size."""
    if landmarks is None:
        return False
    h, w = frame_shape[:2]
    xs = [p[0] for p in landmarks]
    ys = [p[1] for p in landmarks]
    face_w = max(xs) - min(xs)
    face_h = max(ys) - min(ys)

    # face must occupy at least 15% of frame
    if face_w < w * 0.15 or face_h < h * 0.15:
        return False

    cx = (max(xs) + min(xs)) / 2
    cy = (max(ys) + min(ys)) / 2
    return (w * margin < cx < w * (1 - margin) and
            h * margin < cy < h * (1 - margin))