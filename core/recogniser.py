"""
PillSafe — Facial Recogniser
LBPH-based facial recognition for enrolment training and verification.
Implements FR-05 through FR-10 from the SRS.
"""

import os
import cv2
import numpy as np
from utils.config import get_config
from utils.logger import setup_logger

logger = setup_logger("pillsafe.recogniser")


class FaceRecogniser:
    """LBPH face recogniser wrapper for PillSafe."""

    def __init__(self):
        cfg = get_config()
        self.model_path = cfg.face.model_path
        self.dataset_path = cfg.face.dataset_path
        self.confidence_threshold = cfg.face.confidence_threshold
        self.image_size = tuple(cfg.face.image_size)

        # Create LBPH recogniser
        self.recogniser = cv2.face.LBPHFaceRecognizer_create(
            radius=1,
            neighbors=8,
            grid_x=8,
            grid_y=8,
        )

        self._model_loaded = False
        self._load_model()

    def _load_model(self) -> None:
        """Load a pre-trained model from disk if it exists (FR-06)."""
        if os.path.exists(self.model_path):
            try:
                self.recogniser.read(self.model_path)
                self._model_loaded = True
                logger.info("LBPH model loaded from %s", self.model_path)
            except cv2.error as e:
                logger.error("Failed to load model: %s", e)
                self._model_loaded = False
        else:
            logger.info("No trained model found — enrolment required")

    def train(self) -> bool:
        """
        Train the LBPH model on all enrolled user datasets (FR-05, FR-09).
        Reads images from data/dataset/{user_id}/ directories.
        Returns True if training succeeded.
        """
        faces = []
        labels = []

        if not os.path.exists(self.dataset_path):
            logger.warning("Dataset path does not exist: %s", self.dataset_path)
            return False

        for user_dir in os.listdir(self.dataset_path):
            user_path = os.path.join(self.dataset_path, user_dir)
            if not os.path.isdir(user_path):
                continue

            try:
                user_id = int(user_dir)
            except ValueError:
                logger.warning("Skipping non-numeric directory: %s", user_dir)
                continue

            image_files = [
                f for f in os.listdir(user_path)
                if f.lower().endswith((".jpg", ".png", ".pgm"))
            ]

            if len(image_files) == 0:
                logger.warning("No images found for user %d", user_id)
                continue

            for img_file in image_files:
                img_path = os.path.join(user_path, img_file)
                img = cv2.imread(img_path, cv2.IMREAD_GRAYSCALE)
                if img is None:
                    continue
                img_resized = cv2.resize(img, self.image_size)
                faces.append(img_resized)
                labels.append(user_id)

        if len(faces) == 0:
            logger.error("No training data available — cannot train model")
            return False

        logger.info("Training LBPH on %d samples across %d users",
                     len(faces), len(set(labels)))

        self.recogniser = cv2.face.LBPHFaceRecognizer_create(
            radius=1, neighbors=8, grid_x=8, grid_y=8
        )
        self.recogniser.train(faces, np.array(labels))

        # Serialise the trained model to disk
        os.makedirs(os.path.dirname(self.model_path), exist_ok=True)
        self.recogniser.write(self.model_path)
        self._model_loaded = True

        logger.info("LBPH model trained and saved to %s", self.model_path)
        return True

    def predict(self, face_roi: np.ndarray) -> tuple[int, float]:
        """
        Predict the identity of a face ROI.
        Returns (user_id, confidence). Lower confidence = better match.
        """
        if not self._model_loaded:
            raise RuntimeError("No trained model loaded — enrol users first")

        roi = cv2.resize(face_roi, self.image_size)
        label, confidence = self.recogniser.predict(roi)
        return label, confidence

    def verify(self, face_roi: np.ndarray,
               expected_user_id: int | None = None) -> tuple[bool, int, float]:
        """
        Verify a face against the trained model (FR-07).
        If expected_user_id is provided, only accept if the predicted label matches.
        Returns (accepted, predicted_label, confidence).
        """
        label, confidence = self.predict(face_roi)

        if confidence > self.confidence_threshold:
            logger.debug("Verification REJECTED: confidence %.1f > threshold %d",
                         confidence, self.confidence_threshold)
            return False, label, confidence

        if expected_user_id is not None and label != expected_user_id:
            logger.debug("Verification REJECTED: predicted user %d != expected %d",
                         label, expected_user_id)
            return False, label, confidence

        logger.info("Verification ACCEPTED: user %d (confidence %.1f)",
                     label, confidence)
        return True, label, confidence

    @property
    def is_trained(self) -> bool:
        return self._model_loaded
