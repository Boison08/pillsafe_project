"""
PillSafe — Decision Engine
Orchestrates: capture → detect → liveness → LBPH recognition → result.
Implements FR-07, FR-08, FR-10.
"""

import time
from dataclasses import dataclass
from enum import Enum

from core.camera import Camera
from core.detector import FaceDetector
from core.recogniser import FaceRecogniser
from core.liveness import LivenessDetector
from utils.config import get_config
from utils.logger import setup_logger

logger = setup_logger("pillsafe.decision")


class VerificationResult(Enum):
    ACCEPTED = "ACCEPTED"
    REJECTED = "REJECTED"
    NO_FACE = "NO_FACE"
    LIVENESS_FAILED = "LIVENESS_FAILED"
    MODEL_NOT_READY = "MODEL_NOT_READY"


@dataclass
class VerificationOutcome:
    result: VerificationResult
    user_id: int | None = None
    confidence: float | None = None
    attempt: int = 0


class DecisionEngine:
    """Coordinates camera, detection, liveness, and recognition."""

    def __init__(self, camera: Camera, detector: FaceDetector,
                 recogniser: FaceRecogniser, liveness: LivenessDetector):
        cfg = get_config()
        self.camera = camera
        self.detector = detector
        self.recogniser = recogniser
        self.liveness = liveness
        self.max_retries = cfg.face.max_retries

    def run_verification(self, expected_user_id: int | None = None) -> VerificationOutcome:
        """
        Execute the full verification pipeline with retry logic (FR-08).
        Up to max_retries attempts before returning REJECTED.
        """
        if not self.recogniser.is_trained:
            logger.error("LBPH model not loaded")
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

            # Liveness check (first attempt only to avoid user frustration)
            if attempt == 1:
                if not self.liveness.check_liveness(self.camera):
                    logger.warning("Liveness check failed")
                    return VerificationOutcome(
                        result=VerificationResult.LIVENESS_FAILED,
                        attempt=attempt,
                    )

            # LBPH recognition
            accepted, label, confidence = self.recogniser.verify(roi, expected_user_id)

            if accepted:
                logger.info("ACCEPTED attempt %d: user=%d confidence=%.1f",
                            attempt, label, confidence)
                return VerificationOutcome(
                    result=VerificationResult.ACCEPTED,
                    user_id=label,
                    confidence=confidence,
                    attempt=attempt,
                )
            else:
                logger.info("REJECTED attempt %d: predicted=%d confidence=%.1f",
                            attempt, label, confidence)
                time.sleep(1)

        # All retries exhausted — lockout (FR-08)
        logger.warning("FAILED after %d attempts — lockout", self.max_retries)
        return VerificationOutcome(
            result=VerificationResult.REJECTED,
            attempt=self.max_retries,
        )
