"""
PillSafe — Decision Engine
Orchestrates: capture → detect → FaceNet recognition → result.
Implements FR-07, FR-08, FR-10.
"""

import time
from dataclasses import dataclass
from enum import Enum

from core.camera import Camera
from core.detector import FaceDetector
from core.facenet_recogniser import FaceNetRecogniser
from utils.config import get_config
from utils.logger import setup_logger

logger = setup_logger("pillsafe.decision")


class VerificationResult(Enum):
    ACCEPTED = "ACCEPTED"
    REJECTED = "REJECTED"
    NO_FACE = "NO_FACE"
    MODEL_NOT_READY = "MODEL_NOT_READY"


@dataclass
class VerificationOutcome:
    result: VerificationResult
    user_id: int | None = None
    confidence: float | None = None
    attempt: int = 0


class DecisionEngine:
    """Coordinates camera, detection, and recognition."""

    def __init__(self, camera: Camera, detector: FaceDetector, recogniser: FaceNetRecogniser):
        cfg = get_config()
        self.camera = camera
        self.detector = detector
        self.recogniser = recogniser
        self.max_retries = cfg.face.max_retries

    def run_verification(self, expected_user_id: int | None = None) -> VerificationOutcome:
        """
        Execute the full verification pipeline with retry logic (FR-08).
        Up to max_retries attempts before returning REJECTED.
        """
        if not self.recogniser.is_trained:
            logger.error("Face recognition model not loaded")
            return VerificationOutcome(result=VerificationResult.MODEL_NOT_READY)

        for attempt in range(1, self.max_retries + 1):
            logger.info("Verification attempt %d/%d", attempt, self.max_retries)

            # Capture frame
            frame = self.camera.capture_frame()
            if frame is None:
                time.sleep(1)
                continue

            # Detect face
            detections = self.detector.detect_and_extract(frame)
            if len(detections) == 0:
                logger.debug("No face detected on attempt %d", attempt)
                time.sleep(1)
                continue

            roi, bbox = max(detections, key=lambda d: d[1][2] * d[1][3])
            

            # FaceNet recognition
            user_id, confidence = self.recogniser.predict(roi)

            # FaceNet: Confidence > 60 means good match
            if confidence > 60:
                logger.info("ACCEPTED attempt %d: user=%d confidence=%.1f",
                            attempt, user_id, confidence)
                return VerificationOutcome(
                    result=VerificationResult.ACCEPTED,
                    user_id=user_id,
                    confidence=confidence,
                    attempt=attempt,
                )
            else:
                logger.info("REJECTED attempt %d: predicted=%d confidence=%.1f",
                            attempt, user_id, confidence)
                time.sleep(1)

        # All retries exhausted — lockout (FR-08)
        logger.warning("FAILED after %d attempts — lockout", self.max_retries)
        return VerificationOutcome(
            result=VerificationResult.REJECTED,
            attempt=self.max_retries,
        )
