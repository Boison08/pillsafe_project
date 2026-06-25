"""
PillSafe — Main Control Loop
Entry point that initialises all modules and coordinates the
dispensing workflow as described in the SDR §9.

Startup Sequence:
  1. Load configuration
  2. Initialise database
  3. Initialise hardware (camera, servo, IR sensors, buzzer, RTC, GSM)
  4. Load FaceNet (TFLite) recognition model
  5. Start Flask API server as a background thread
  6. Start the scheduling daemon
  7. Start the SMS alert service
  8. Enter idle state — wait for dispensing events

Operational Workflow (per event):
  1. Scheduler detects a time match → creates DispenseEvent
  2. Buzzer plays "dose_ready" pattern
  3. Camera activates → face detection + FaceNet (TFLite) verification
  4. On ACCEPT: servo rotates to compartment → IR confirms pill drop → IR confirms pickup → log TAKEN
  5. On REJECT (3 failures): log REJECTED → send alert
  6. On TIMEOUT (grace period): log MISSED → send alert
  7. Return to idle
"""

import os
import sys
import signal
import threading
from datetime import datetime

# Ensure project root is on the Python path
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, PROJECT_ROOT)
os.chdir(PROJECT_ROOT)

from utils.config import load_config, get_config
from utils.logger import setup_logger

# Load config first
load_config()
logger = setup_logger("pillsafe.main")

from database.db_manager import DatabaseManager
from core.camera import Camera
from core.detector import FaceDetector
from core.facenet_recogniser import FaceNetRecogniser
from core.decision import DecisionEngine, VerificationResult
from hardware.dispenser import Dispenser
from hardware.ir_sensor import IRSensorManager
from hardware.buzzer import Buzzer
from hardware.rtc import RealTimeClock
from hardware.gsm import GSMModule
from scheduler.schedule_controller import ScheduleController, DispenseEvent
from alerts.alert_service import AlertService
from enrollment.enrol_user import EnrolmentManager
from api.routes import create_app
from core.voice_recogniser import VoiceRecogniser

class PillSafeSystem:
    """Main system controller — orchestrates all PillSafe components."""

    def __init__(self):
        logger.info("=" * 60)
        logger.info("PillSafe Smart Pill Dispenser — Starting Up")
        logger.info("=" * 60) 

        cfg = get_config()

        # ── Step 1: Database ─────────────────────────────────
        logger.info("Initialising database...")
        self.db = DatabaseManager()

        # ── Step 2: Hardware ─────────────────────────────────
        logger.info("Initialising hardware modules...")
        self.camera = Camera()
        self.rtc = RealTimeClock()
        self.dispenser = Dispenser()
        self.ir_sensors = IRSensorManager()
        self.buzzer = Buzzer()
        self.gsm = GSMModule()

        # ── Step 3: Core AI ──────────────────────────────────
        logger.info("Initialising facial recognition pipeline...")
        self.detector = FaceDetector()
        self.recogniser = FaceNetRecogniser()
        try:
            self.voice_recogniser = VoiceRecogniser()
            logger.info("Voice recogniser initialised")
        except Exception as e:
            logger.warning("Voice recogniser unavailable: %s — voice auth disabled", e)
            self.voice_recogniser = None
        self.decision_engine = DecisionEngine(
            self.camera, self.detector, self.recogniser, self.voice_recogniser
)

        # ── Step 4: Enrolment Manager ────────────────────────
        self.enrolment = EnrolmentManager(
            self.camera, self.detector, self.recogniser, self.db, self.voice_recogniser
        )

        # ── Step 5: Alert Service ────────────────────────────
        self.alert_service = AlertService(self.db, self.gsm)

        # ── Step 6: Scheduler ────────────────────────────────
        self.scheduler = ScheduleController(self.db, self.rtc)
        self.scheduler.set_event_callback(self._handle_dispense_event)

        # ── Step 7: Flask API ────────────────────────────────
        self.app = create_app(
            db=self.db,
            enrolment_manager=self.enrolment,
            rtc=self.rtc,
            gsm=self.gsm,
        )

        self._running = False

    def start(self) -> None:
        """Start all background services and enter the main loop."""
        self._running = True

        # Register signal handlers for graceful shutdown
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)

        # Start the alert service
        self.alert_service.start()

        # Start the scheduler
        self.scheduler.start()

        # Start the Flask API in a background thread (FR-24)
        cfg = get_config()
        api_thread = threading.Thread(
            target=self.app.run,
            kwargs={
                "host": cfg.api.host,
                "port": cfg.api.port,
                "debug": False,
                "use_reloader": False,
            },
            daemon=True,
        )
        api_thread.start()
        logger.info("Flask API started on %s:%d", cfg.api.host, cfg.api.port)

        rtc_time = self.rtc.get_time_string("%Y-%m-%d %H:%M:%S")
        logger.info("System ready — RTC time: %s", rtc_time)
        logger.info("Entering idle state — waiting for dispensing events...")

        # Keep the main thread alive
        try:
            while self._running:
                signal.pause()
        except AttributeError:
            # signal.pause() not available on Windows
            import time
            while self._running:
                time.sleep(1)

    def _handle_dispense_event(self, event: DispenseEvent) -> None:
        """
        Handle a dispensing event triggered by the scheduler.
        This runs in its own thread for each event.
        Implements the full operational workflow from SDR §9.
        """
        logger.info("=" * 40)
        logger.info("DISPENSING EVENT: %s for %s at %s",
                     event.medication_name, event.full_name, event.scheduled_time)
        logger.info("Compartment: %d | Grace deadline: %s",
                     event.compartment_index,
                     event.grace_deadline.strftime("%H:%M:%S"))
        logger.info("=" * 40)

        # Step 1: Sound the buzzer to alert the user (NFR-18)
        self.buzzer.play("dose_ready")

        # Step 2: Activate camera and run verification
        self.camera.start()

        # Get auth mode chosen by user from the API (POST /dispense/request)
        pending = self.app.config.get("PENDING_AUTH", {})
        auth_mode = pending.get("mode", "face")

        outcome = self.decision_engine.run_verification(
            expected_user_id=event.user_id,
            auth_mode=auth_mode,
        )

        if outcome.result == VerificationResult.ACCEPTED:
            # ── Successful Verification ──────────────────────
            logger.info("User %d verified — dispensing medication", event.user_id)

            # Step 3: Rotate carousel to correct compartment
            rotated = self.dispenser.rotate_to(event.compartment_index)
            if not rotated:
                self._handle_mechanical_error(event)
                return

            # Step 4: Wait for IR sensor to confirm pill dropped
            pill_dropped = self.ir_sensors.wait_for_pill_drop(timeout=5.0)
            if not pill_dropped:
                self._handle_mechanical_error(event)
                return

            # Step 5: Wait for user to pick up the pill
            pill_picked = self.ir_sensors.wait_for_pickup(timeout=120.0)

            # Step 6: Log the event as TAKEN
            actual_time = datetime.now().strftime("%H:%M")
            self.db.log_event(
                user_id=event.user_id,
                schedule_id=event.schedule_id,
                scheduled_time=event.scheduled_time,
                outcome="TAKEN",
                actual_time=actual_time,
            )

            # Success buzzer
            self.buzzer.play("success")
            logger.info("Dose TAKEN by user %d at %s", event.user_id, actual_time)

        elif outcome.result == VerificationResult.REJECTED:
            # ── Authentication Failed (FR-08) ────────────────
            logger.warning("Verification REJECTED for user %d — lockout",
                            event.user_id)
            self.db.log_event(
                user_id=event.user_id,
                schedule_id=event.schedule_id,
                scheduled_time=event.scheduled_time,
                outcome="REJECTED",
            )
            self.buzzer.play("failure")
            self.alert_service.send_immediate_alert(
                event.user_id, event.schedule_id,
                "REJECTED", event.scheduled_time,
            )

        elif outcome.result == VerificationResult.NO_FACE:
            # ── No one present — will eventually become MISSED via grace period
            logger.info("No face detected — waiting for grace period to expire")
            # The scheduler's grace period logic will handle the MISSED event
            self._wait_for_grace_period(event)

        else:
            # ── Model not ready or other error ───────────────
            logger.error("Verification returned: %s", outcome.result)
            self._wait_for_grace_period(event)

        # Return to idle
        self.camera.stop()
        self.dispenser.home()
        logger.info("Returning to idle state")

    def _wait_for_grace_period(self, event: DispenseEvent) -> None:
        """
        Wait until the grace period expires, periodically retrying verification.
        If no successful verification occurs, log as MISSED (FR-16).
        """
        import time

        logger.info("Entering grace period — retrying verification until %s",
                     event.grace_deadline.strftime("%H:%M:%S"))

        while datetime.now() < event.grace_deadline:
            # Retry verification every 30 seconds during grace period
            time.sleep(30)

            if not self._running:
                break

            frame = self.camera.capture_frame()
            if frame is None:
                continue

            detections = self.detector.detect_and_extract(frame)
            if len(detections) == 0:
                continue

            # Someone appeared — run full verification
            outcome = self.decision_engine.run_verification(
                expected_user_id=event.user_id
            )

            if outcome.result == VerificationResult.ACCEPTED:
                # Late but still within grace period
                rotated = self.dispenser.rotate_to(event.compartment_index)
                if rotated:
                    pill_dropped = self.ir_sensors.wait_for_pill_drop(timeout=5.0)
                    if pill_dropped:
                        self.ir_sensors.wait_for_pickup(timeout=120.0)
                        actual_time = datetime.now().strftime("%H:%M")
                        self.db.log_event(
                            user_id=event.user_id,
                            schedule_id=event.schedule_id,
                            scheduled_time=event.scheduled_time,
                            outcome="TAKEN",
                            actual_time=actual_time,
                        )
                        self.buzzer.play("success")
                        logger.info("Late dose TAKEN at %s", actual_time)
                        return

        # Grace period expired — mark as MISSED
        logger.warning("Grace period expired — dose MISSED for user %d", event.user_id)
        self.db.log_event(
            user_id=event.user_id,
            schedule_id=event.schedule_id,
            scheduled_time=event.scheduled_time,
            outcome="MISSED",
        )
        self.buzzer.play("missed")
        self.alert_service.send_immediate_alert(
            event.user_id, event.schedule_id,
            "MISSED", event.scheduled_time,
        )

    def _handle_mechanical_error(self, event: DispenseEvent) -> None:
        """Handle a mechanical dispensing failure."""
        logger.error("MECHANICAL ERROR during dispensing for user %d", event.user_id)
        self.db.log_event(
            user_id=event.user_id,
            schedule_id=event.schedule_id,
            scheduled_time=event.scheduled_time,
            outcome="MECHANICAL_ERROR",
        )
        self.buzzer.play("failure")
        self.alert_service.send_immediate_alert(
            event.user_id, event.schedule_id,
            "MECHANICAL_ERROR", event.scheduled_time,
        )

    def _signal_handler(self, signum, frame) -> None:
        """Handle SIGINT/SIGTERM for graceful shutdown."""
        logger.info("Shutdown signal received (signal %d)", signum)
        self.shutdown()

    def shutdown(self) -> None:
        """Gracefully shut down all components and release hardware."""
        logger.info("Shutting down PillSafe...")
        self._running = False

        self.scheduler.stop()
        self.alert_service.stop()
        self.camera.stop()
        self.dispenser.cleanup()
        self.ir_sensors.cleanup()
        self.buzzer.cleanup()
        self.rtc.cleanup()
        self.gsm.cleanup()

        # Final GPIO cleanup
        try:
            import RPi.GPIO as GPIO
            GPIO.cleanup()
        except (ImportError, RuntimeError):
            pass

        logger.info("PillSafe shut down complete")
        logger.info("=" * 60)


def main():
    system = PillSafeSystem()
    system.start()


if __name__ == "__main__":
    main()
