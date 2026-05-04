"""
PillSafe — Liveness Detection
Eye-blink based anti-spoofing. Tracks open→closed→open cycles
using the Haar eye cascade. A photograph never produces this transition.
"""

import time
from core.detector import FaceDetector
from utils.config import get_config
from utils.logger import setup_logger

logger = setup_logger("pillsafe.liveness")


class LivenessDetector:
    EYES_OPEN = "open"
    EYES_CLOSED = "closed"

    def __init__(self, detector: FaceDetector):
        cfg = get_config()
        self.detector = detector
        self.enabled = cfg.liveness.enabled
        self.required_blinks = cfg.liveness.required_blinks
        self.detection_timeout = cfg.liveness.detection_timeout
        logger.info("Liveness detector (enabled=%s, blinks=%d)",
                     self.enabled, self.required_blinks)

    def check_liveness(self, camera) -> bool:
        """
        Monitor for blinks via the camera. Returns True if the required
        number of blinks is detected within the timeout.
        """
        if not self.enabled:
            return True

        logger.info("Liveness check — waiting for %d blink(s)...", self.required_blinks)

        blink_count = 0
        eye_state = self.EYES_OPEN
        start_time = time.time()
        consecutive_closed = 0
        consecutive_open = 0
        min_closed_frames = 2
        min_open_frames = 2

        while time.time() - start_time < self.detection_timeout:
            frame = camera.capture_frame()
            if frame is None:
                continue

            grey = self.detector.preprocess(frame)
            faces = self.detector.detect_faces(grey)

            if len(faces) == 0:
                continue

            face_bbox = max(faces, key=lambda b: b[2] * b[3])
            eyes = self.detector.detect_eyes(grey, face_bbox)

            if len(eyes) >= 1:
                consecutive_open += 1
                consecutive_closed = 0
                if eye_state == self.EYES_CLOSED and consecutive_open >= min_open_frames:
                    blink_count += 1
                    logger.debug("Blink %d/%d detected", blink_count, self.required_blinks)
                    eye_state = self.EYES_OPEN
                    if blink_count >= self.required_blinks:
                        logger.info("Liveness PASSED (%d blinks)", blink_count)
                        return True
            else:
                consecutive_closed += 1
                consecutive_open = 0
                if eye_state == self.EYES_OPEN and consecutive_closed >= min_closed_frames:
                    eye_state = self.EYES_CLOSED

            time.sleep(0.05)

        logger.warning("Liveness FAILED — timeout (%d/%d blinks)",
                         blink_count, self.required_blinks)
        return False
