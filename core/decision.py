"""
PillSafe — Decision Engine
Orchestrates: capture → detect → FaceNet recognition → result.
Extended to support voice verification as a second auth modality.
Implements FR-07, FR-08, FR-10, FR-55, FR-57.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from enum import Enum
from typing import Literal

from core.camera import Camera
from core.detector import FaceDetector
from core.facenet_recogniser import FaceNetRecogniser
from utils.config import get_config
from utils.logger import setup_logger

try:
    from core.voice_recogniser import VoiceRecogniser
except Exception:  # pragma: no cover - voice auth is optional when audio deps are missing
    VoiceRecogniser = None

logger = setup_logger("pillsafe.decision")

AuthMode = Literal["face", "voice"]


class VerificationResult(Enum):
    ACCEPTED = "ACCEPTED"
    REJECTED = "REJECTED"
    NO_FACE = "NO_FACE"
    MODEL_NOT_READY = "MODEL_NOT_READY"
    NO_VOICE_TEMPLATE = "NO_VOICE_TEMPLATE"
    AUDIO_ERROR = "AUDIO_ERROR"


@dataclass
class VerificationOutcome:
    result: VerificationResult
    user_id: int | None = None
    confidence: float | None = None   # cosine similarity for both face and voice
    attempt: int = 0
    auth_mode: AuthMode = "face"      # logged to AdherenceLog (FR-59)


class DecisionEngine:
    """Coordinates camera, detection, face recognition, and voice verification."""

    def __init__(self, camera: Camera, detector: FaceDetector,
                 recogniser: FaceNetRecogniser, voice_recogniser: VoiceRecogniser | None = None):
        cfg = get_config()
        self.camera = camera
        self.detector = detector
        self.recogniser = recogniser
        self.voice_recogniser = voice_recogniser   # None if voice hardware unavailable
        self.max_retries = cfg.face.max_retries
        self.confidence_threshold = cfg.face.confidence_threshold
        self.distance_threshold = getattr(cfg.face, "distance_threshold", 0.6)

    # ── Public entry point ─────────────────────────────────────────────────

    def run_verification(self, expected_user_id: int | None = None,
                         auth_mode: AuthMode = "face") -> VerificationOutcome:
        """
        Execute verification in the requested modality (FR-57).

        Parameters
        ----------
        expected_user_id : int | None
            DB user_id of the patient expected to authenticate.
        auth_mode : "face" | "voice"
            Modality chosen by the user via the mobile app (FR-56).
            Either modality alone is sufficient to unlock dispensing (OR logic).
        """
        if auth_mode == "voice":
            return self._run_voice_verification(expected_user_id)
        return self._run_face_verification(expected_user_id)

    # ── Face verification (unchanged logic) ───────────────────────────────

    def _run_face_verification(self, expected_user_id: int | None) -> VerificationOutcome:
        """
        Execute the full face verification pipeline with retry logic (FR-08).
        Up to max_retries attempts before returning REJECTED.
        """
        if not self.recogniser.is_trained:
            logger.error("Face recognition model not loaded")
            return VerificationOutcome(
                result=VerificationResult.MODEL_NOT_READY,
                auth_mode="face"
            )

        for attempt in range(1, self.max_retries + 1):
            logger.info("Face verification attempt %d/%d", attempt, self.max_retries)

            frame = self.camera.capture_frame()
            if frame is None:
                time.sleep(1)
                continue

            detections = self.detector.detect_and_extract(frame)
            if len(detections) == 0:
                logger.debug("No face detected on attempt %d", attempt)
                time.sleep(1)
                continue

            roi, bbox = max(detections, key=lambda d: d[1][2] * d[1][3])

            user_id, confidence = self.recogniser.predict(roi)
            # confidence = (1 - cosine_distance) * 100  →  recover distance
            distance = 1.0 - (confidence / 100.0)

            # The match must be (a) confident enough, (b) close enough in
            # embedding space, and (c) the SAME person the dose is scheduled
            # for. Without (c) any enrolled user could collect another
            # patient's medication (security fix, FR-07/FR-08).
            confident = confidence >= self.confidence_threshold
            close_enough = distance <= self.distance_threshold
            identity_ok = (expected_user_id is None) or (user_id == expected_user_id)

            if confident and close_enough and identity_ok:
                logger.info("ACCEPTED attempt %d: user=%d confidence=%.4f dist=%.4f",
                            attempt, user_id, confidence, distance)
                return VerificationOutcome(
                    result=VerificationResult.ACCEPTED,
                    user_id=user_id,
                    confidence=confidence,
                    attempt=attempt,
                    auth_mode="face",
                )
            else:
                logger.info(
                    "REJECTED attempt %d: predicted=%s expected=%s confidence=%.4f "
                    "dist=%.4f (confident=%s close=%s identity=%s)",
                    attempt, user_id, expected_user_id, confidence, distance,
                    confident, close_enough, identity_ok,
                )
                time.sleep(1)

        logger.warning("Face verification FAILED after %d attempts — lockout", self.max_retries)
        return VerificationOutcome(
            result=VerificationResult.REJECTED,
            attempt=self.max_retries,
            auth_mode="face",
        )

    # ── Voice verification ─────────────────────────────────────────────────

    def _run_voice_verification(self, expected_user_id: int | None) -> VerificationOutcome:
        """
        Execute voice verification with retry logic (FR-51).
        Up to max_retries attempts before returning REJECTED.
        """
        if self.voice_recogniser is None:
            logger.error("Voice recogniser not initialised")
            return VerificationOutcome(
                result=VerificationResult.AUDIO_ERROR,
                auth_mode="voice"
            )

        if expected_user_id is not None and not self.voice_recogniser.is_enrolled(expected_user_id):
            logger.warning("No voice template for user %d", expected_user_id)
            return VerificationOutcome(
                result=VerificationResult.NO_VOICE_TEMPLATE,
                user_id=expected_user_id,
                auth_mode="voice",
            )

        for attempt in range(1, self.max_retries + 1):
            logger.info("Voice verification attempt %d/%d", attempt, self.max_retries)

            result = self.voice_recogniser.verify_user(expected_user_id)

            if result.get("error"):
                logger.warning("Audio error on attempt %d: %s", attempt, result["error"])
                time.sleep(1)
                continue

            similarity = result.get("similarity", 0.0)

            if result.get("verified"):
                logger.info("ACCEPTED attempt %d: user=%d similarity=%.4f",
                            attempt, expected_user_id, similarity)
                return VerificationOutcome(
                    result=VerificationResult.ACCEPTED,
                    user_id=expected_user_id,
                    confidence=similarity,
                    attempt=attempt,
                    auth_mode="voice",
                )
            else:
                logger.info("REJECTED attempt %d: similarity=%.4f", attempt, similarity)
                time.sleep(1)

        logger.warning("Voice verification FAILED after %d attempts — lockout", self.max_retries)
        return VerificationOutcome(
            result=VerificationResult.REJECTED,
            attempt=self.max_retries,
            auth_mode="voice",
        )