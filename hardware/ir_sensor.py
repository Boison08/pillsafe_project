"""
PillSafe — IR Sensor Module
FC-51 infrared sensors for pill detection and pickup confirmation.

GPIO Wiring:
  - IR Sensor 1 (pill detect)  → GPIO 23 (BCM) / Pin 16
  - IR Sensor 2 (pill pickup)  → GPIO 24 (BCM) / Pin 18
  - Both VCC → 3.3V (Pin 1)   | Both GND → GND (Pin 9)

FC-51 behaviour: LOW = obstacle detected, HIGH = clear.
"""

import time
from utils.config import get_config
from utils.logger import setup_logger

logger = setup_logger("pillsafe.ir_sensor")

try:
    import RPi.GPIO as GPIO
    GPIO_AVAILABLE = True
except (ImportError, RuntimeError):
    GPIO_AVAILABLE = False
    logger.warning("RPi.GPIO not available — IR sensors in simulation mode")


class IRSensorManager:
    def __init__(self):
        cfg = get_config()
        self.pill_detect_pin = cfg.ir_sensors.pill_detect_pin
        self.pill_pickup_pin = cfg.ir_sensors.pill_pickup_pin
        self._setup_gpio()

    def _setup_gpio(self):
        if not GPIO_AVAILABLE:
            logger.info("IR sensors simulated on GPIO %d, %d",
                         self.pill_detect_pin, self.pill_pickup_pin)
            return
        GPIO.setmode(GPIO.BCM)
        GPIO.setup(self.pill_detect_pin, GPIO.IN, pull_up_down=GPIO.PUD_UP)
        GPIO.setup(self.pill_pickup_pin, GPIO.IN, pull_up_down=GPIO.PUD_UP)
        logger.info("IR sensors on GPIO %d (detect), %d (pickup)",
                     self.pill_detect_pin, self.pill_pickup_pin)

    def pill_detected(self) -> bool:
        if not GPIO_AVAILABLE:
            return True
        return GPIO.input(self.pill_detect_pin) == GPIO.LOW

    def pill_picked_up(self) -> bool:
        if not GPIO_AVAILABLE:
            return True
        return GPIO.input(self.pill_pickup_pin) == GPIO.HIGH

    def wait_for_pill_drop(self, timeout: float = 5.0) -> bool:
        start = time.time()
        while time.time() - start < timeout:
            if self.pill_detected():
                logger.info("Pill detected at discharge chute")
                return True
            time.sleep(0.05)
        logger.warning("Pill NOT detected — possible mechanical error")
        return False

    def wait_for_pickup(self, timeout: float = 120.0) -> bool:
        start = time.time()
        if not self.pill_detected():
            logger.warning("No pill in tray — cannot wait for pickup")
            return False
        while time.time() - start < timeout:
            if self.pill_picked_up():
                logger.info("Pill picked up by user")
                return True
            time.sleep(0.1)
        logger.warning("Pill pickup timeout")
        return False

    def cleanup(self):
        if GPIO_AVAILABLE:
            GPIO.cleanup([self.pill_detect_pin, self.pill_pickup_pin])
