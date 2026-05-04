"""
PillSafe — Buzzer Controller
Active buzzer for audio alerts (NFR-18).

GPIO Wiring:
  - Signal → GPIO 25 (BCM) / Pin 22
  - VCC → 3.3V (Pin 17) | GND → GND (Pin 20)
"""

import time
import threading
from utils.config import get_config
from utils.logger import setup_logger

logger = setup_logger("pillsafe.buzzer")

try:
    import RPi.GPIO as GPIO
    GPIO_AVAILABLE = True
except (ImportError, RuntimeError):
    GPIO_AVAILABLE = False


class Buzzer:
    def __init__(self):
        cfg = get_config()
        self.pin = cfg.buzzer.pin
        self.patterns = {
            "dose_ready": cfg.buzzer.dose_ready_pattern,
            "success": cfg.buzzer.success_pattern,
            "failure": cfg.buzzer.failure_pattern,
            "missed": cfg.buzzer.missed_pattern,
        }
        self._setup_gpio()

    def _setup_gpio(self):
        if not GPIO_AVAILABLE:
            logger.info("Buzzer simulated on GPIO %d", self.pin)
            return
        GPIO.setmode(GPIO.BCM)
        GPIO.setup(self.pin, GPIO.OUT)
        GPIO.output(self.pin, GPIO.LOW)

    def _play_pattern(self, pattern: list[float]):
        for i, duration in enumerate(pattern):
            state = (i % 2 == 0)
            if GPIO_AVAILABLE:
                GPIO.output(self.pin, GPIO.HIGH if state else GPIO.LOW)
            time.sleep(duration)
        if GPIO_AVAILABLE:
            GPIO.output(self.pin, GPIO.LOW)

    def play(self, pattern_name: str, blocking: bool = False):
        pattern = self.patterns.get(pattern_name)
        if not pattern:
            return
        if blocking:
            self._play_pattern(pattern)
        else:
            threading.Thread(target=self._play_pattern, args=(pattern,), daemon=True).start()

    def cleanup(self):
        if GPIO_AVAILABLE:
            GPIO.output(self.pin, GPIO.LOW)
            GPIO.cleanup(self.pin)
