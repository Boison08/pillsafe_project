"""
PillSafe — Dispensing Mechanism Controller
Controls SG90 servo motor for a 6-compartment rotating carousel.
Each compartment maps 1:1 to a user (SDR §4.4, FR-14).

GPIO Wiring:
  - Servo signal → GPIO 18 (BCM) / Pin 12
  - Servo VCC    → 5V  (Pin 2 or 4)
  - Servo GND    → GND (Pin 6)

Note on SG90 (0–180° range):
  With 6 compartments across 180°, each slot = 30° apart.
  For a full 360° carousel, use a continuous-rotation or 270° servo.
"""

import time
from utils.config import get_config
from utils.logger import setup_logger

logger = setup_logger("pillsafe.dispenser")

try:
    import RPi.GPIO as GPIO
    GPIO_AVAILABLE = True
except (ImportError, RuntimeError):
    GPIO_AVAILABLE = False
    logger.warning("RPi.GPIO not available — dispenser in simulation mode")


class Dispenser:
    """Controls a 6-slot rotating carousel via servo PWM."""

    def __init__(self):
        cfg = get_config()
        self.pwm_pin = cfg.servo.pwm_pin
        self.frequency = cfg.servo.frequency_hz
        self.num_compartments = cfg.servo.num_compartments
        self.min_duty = cfg.servo.min_duty
        self.max_duty = cfg.servo.max_duty
        self.hold_time = cfg.servo.hold_time

        # SG90 range is 0–180°, divide evenly among compartments
        self.max_angle = 180.0
        self.angle_per_slot = self.max_angle / self.num_compartments
        self.angles = {
            i: round(i * self.angle_per_slot, 1)
            for i in range(self.num_compartments)
        }

        self._pwm = None
        self._current_index = None
        self._setup_gpio()

    def _setup_gpio(self) -> None:
        if not GPIO_AVAILABLE:
            logger.info("Dispenser GPIO simulated — pin %d", self.pwm_pin)
            return
        GPIO.setmode(GPIO.BCM)
        GPIO.setup(self.pwm_pin, GPIO.OUT)
        self._pwm = GPIO.PWM(self.pwm_pin, self.frequency)
        self._pwm.start(0)
        logger.info("Servo on GPIO %d at %d Hz", self.pwm_pin, self.frequency)

    def _angle_to_duty(self, angle: float) -> float:
        """Convert angle (0–180°) to PWM duty cycle."""
        return round(
            self.min_duty + (angle / self.max_angle) * (self.max_duty - self.min_duty),
            2,
        )

    def rotate_to(self, compartment_index: int) -> bool:
        """
        Rotate carousel to align compartment with the discharge chute.
        Returns True on success.
        """
        if compartment_index < 0 or compartment_index >= self.num_compartments:
            logger.error("Invalid compartment: %d (range 0–%d)",
                         compartment_index, self.num_compartments - 1)
            return False

        target_angle = self.angles[compartment_index]
        duty = self._angle_to_duty(target_angle)

        logger.info("Rotating to compartment %d (%.1f°, duty %.2f%%)",
                     compartment_index, target_angle, duty)

        if GPIO_AVAILABLE and self._pwm:
            self._pwm.ChangeDutyCycle(duty)
            time.sleep(self.hold_time)
            self._pwm.ChangeDutyCycle(0)  # Stop signal to prevent jitter
        else:
            logger.debug("[SIM] Servo → compartment %d at %.1f°",
                         compartment_index, target_angle)
            time.sleep(self.hold_time)

        self._current_index = compartment_index
        logger.info("Now at compartment %d", compartment_index)
        return True

    def home(self) -> None:
        """Return carousel to home position (compartment 0)."""
        self.rotate_to(0)

    @property
    def current_compartment(self) -> int | None:
        return self._current_index

    def cleanup(self) -> None:
        if GPIO_AVAILABLE and self._pwm:
            self._pwm.stop()
            logger.info("Servo PWM stopped")
