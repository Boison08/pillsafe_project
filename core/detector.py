"""
PillSafe — Face Detector
Haar Cascade face and eye detection with greyscale preprocessing
and histogram equalisation (§3.3.2).
"""

import cv2
import numpy as np
from utils.config import get_config
from utils.logger import setup_logger

logger = setup_logger("pillsafe.detector")


class FaceDetector:
    """Haar Cascade-based face detection with preprocessing."""

    def __init__(self):
        cfg = get_config()
        self.image_size = tuple(cfg.face.image_size)
        self.scale_factor = getattr(cfg.face, "scale_factor", 1.1)
        self.min_neighbors = getattr(cfg.face, "min_neighbors", 3)
        self.min_face_size = tuple(getattr(cfg.face, "min_face_size", [50, 50]))

        self.face_cascade = cv2.CascadeClassifier(
            cv2.data.haarcascades + cfg.face.cascade_path
        )
        if self.face_cascade.empty():
            raise RuntimeError("Failed to load face cascade classifier")

        logger.info(
            "Face detector initialised (ROI size: %s, scaleFactor=%.2f, "
            "minNeighbors=%d, minSize=%s)",
            self.image_size, self.scale_factor, self.min_neighbors, self.min_face_size,
        )

    def preprocess(self, frame: np.ndarray) -> np.ndarray:
        """Convert to greyscale and apply histogram equalisation."""
        grey = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        return cv2.equalizeHist(grey)

    def detect_faces(self, grey_frame: np.ndarray) -> list[tuple[int, int, int, int]]:
        """Detect faces in a greyscale frame. Returns list of (x, y, w, h)."""
        faces = self.face_cascade.detectMultiScale(
            grey_frame,
            scaleFactor=self.scale_factor,
            minNeighbors=self.min_neighbors,
            minSize=self.min_face_size,
        )
        if len(faces) == 0:
            return []
        return [(x, y, w, h) for (x, y, w, h) in faces]

    def extract_roi(self, grey_frame: np.ndarray,
                    bbox: tuple[int, int, int, int]) -> np.ndarray:
        """Crop the face region and resize to standard dimensions."""
        x, y, w, h = bbox
        roi = grey_frame[y:y + h, x:x + w]
        return cv2.resize(roi, self.image_size)

    def detect_and_extract(self, frame: np.ndarray) -> list[tuple[np.ndarray, tuple]]:
        """Full pipeline: preprocess → detect → extract ROIs.
        Returns list of (roi, bbox) tuples."""
        grey = self.preprocess(frame)
        faces = self.detect_faces(grey)
        results = []
        for bbox in faces:
            roi = self.extract_roi(grey, bbox)
            results.append((roi, bbox))
        return results
