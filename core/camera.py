"""
PillSafe — Camera Module
Manages the Raspberry Pi Camera Module v2 via Picamera2.
Falls back to OpenCV VideoCapture for development on non-Pi systems.
"""

import time
import cv2
from utils.logger import setup_logger

logger = setup_logger("pillsafe.camera")

try:
    from picamera2 import Picamera2
    PICAMERA_AVAILABLE = True
    logger.info("Picamera2 available — using Pi Camera")
except ImportError:
    PICAMERA_AVAILABLE = False
    logger.info("Picamera2 not found — falling back to OpenCV VideoCapture")


class Camera:
    """Wrapper around Pi Camera for consistent frame capture."""

    def __init__(self, resolution: tuple[int, int] = (640, 480)):
        self.resolution = resolution
        self._camera = None
        self._started = False

    def start(self) -> None:
        """Initialise and start the camera stream."""
        if self._started:
            return

        if PICAMERA_AVAILABLE:
            self._camera = Picamera2()
            config = self._camera.create_preview_configuration(
                main={"size": self.resolution, "format": "RGB888"}
            )
            self._camera.configure(config)
            self._camera.start()
            time.sleep(1)  # Allow auto-exposure to settle
        else:
            self._camera = cv2.VideoCapture(0)
            self._camera.set(cv2.CAP_PROP_FRAME_WIDTH, self.resolution[0])
            self._camera.set(cv2.CAP_PROP_FRAME_HEIGHT, self.resolution[1])
            if not self._camera.isOpened():
                logger.error("Failed to open USB camera")
                return

        self._started = True
        logger.info("Camera started at %dx%d", *self.resolution)

    def capture_frame(self):
        """Capture a single frame and return it as a BGR numpy array."""
        if not self._started:
            self.start()

        if PICAMERA_AVAILABLE:
            frame_rgb = self._camera.capture_array()
            return cv2.cvtColor(frame_rgb, cv2.COLOR_RGB2BGR)
        else:
            ret, frame = self._camera.read()
            if not ret:
                logger.error("Failed to capture frame")
                return None
            return frame

    def stop(self) -> None:
        """Release camera resources."""
        if not self._started:
            return
        try:
            if PICAMERA_AVAILABLE:
                self._camera.stop()
                self._camera.close()
            else:
                self._camera.release()
        except Exception as e:
            logger.warning("Camera release error: %s", e)
        finally:
            self._started = False
            logger.info("Camera stopped")

    @property
    def is_active(self) -> bool:
        return self._started
