"""
PillSafe — SMS Alert Service
Monitors the database for missed/rejected events and dispatches
SMS alerts via the GSM module (FR-38 to FR-43).
Runs as a background thread checking for unacknowledged events.
"""

import time
import threading
from datetime import datetime, timedelta

from database.db_manager import DatabaseManager
from hardware.gsm import GSMModule
from utils.config import get_config
from utils.logger import setup_logger

logger = setup_logger("pillsafe.alerts")


class AlertService:
    """Background service for dispatching SMS alerts on missed doses."""

    def __init__(self, db: DatabaseManager, gsm: GSMModule):
        self.db = db
        self.gsm = gsm
        cfg = get_config()
        self.max_sms = cfg.alerts.max_sms_per_event
        self.retry_interval = cfg.alerts.retry_interval_minutes
        self._running = False
        self._thread = None
        # Track SMS counts per log_id to enforce max_sms_per_event (FR-40)
        self._sms_counts: dict[int, int] = {}
        # Track first SMS send times for retry logic (FR-41)
        self._first_sms_times: dict[int, datetime] = {}

    def start(self) -> None:
        """Start the alert monitoring loop in a background thread."""
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self._thread.start()
        logger.info("Alert service started")

    def stop(self) -> None:
        """Stop the alert monitoring loop."""
        self._running = False
        if self._thread:
            self._thread.join(timeout=5)
        logger.info("Alert service stopped")

    def _monitor_loop(self) -> None:
        """
        Periodically check for unacknowledged missed-dose events
        and send SMS alerts as needed.
        """
        while self._running:
            try:
                self._check_and_alert()
            except Exception as e:
                logger.error("Alert service error: %s", e)
            time.sleep(30)  # Check every 30 seconds

    def _check_and_alert(self) -> None:
        """Process unacknowledged events and dispatch SMS alerts."""
        events = self.db.get_unacknowledged_missed()

        for event in events:
            log_id = event["log_id"]
            sms_count = self._sms_counts.get(log_id, 0)

            # FR-40: Maximum SMS limit per event
            if sms_count >= self.max_sms:
                continue

            if sms_count == 0:
                # First SMS — send immediately
                self._send_alert(event)
                self._sms_counts[log_id] = 1
                self._first_sms_times[log_id] = datetime.now()

            elif sms_count == 1:
                # FR-41: Second SMS after retry interval if still unacknowledged
                first_sent = self._first_sms_times.get(log_id)
                if first_sent:
                    elapsed = datetime.now() - first_sent
                    if elapsed >= timedelta(minutes=self.retry_interval):
                        self._send_alert(event)
                        self._sms_counts[log_id] = 2

    def _send_alert(self, event: dict) -> None:
        """Dispatch an SMS alert for a specific event."""
        outcome = event["outcome"]

        if outcome in ("MISSED", "MECHANICAL_ERROR"):
            success = self.gsm.send_missed_dose_alert(
                patient_name=event["full_name"],
                medication_name=event["medication_name"],
                scheduled_time=event["scheduled_time"],
                caregiver_phone=event["caregiver_phone"],
            )
        elif outcome == "REJECTED":
            success = self.gsm.send_unauthorized_alert(
                caregiver_phone=event["caregiver_phone"],
                scheduled_time=event["scheduled_time"],
            )
        else:
            return

        if success:
            self.db.mark_sms_sent(event["log_id"])
            logger.info("SMS alert sent for log_id=%d (outcome=%s)",
                         event["log_id"], outcome)

    def send_immediate_alert(self, user_id: int, schedule_id: int,
                              outcome: str, scheduled_time: str) -> None:
        """
        Called directly by the main control loop for immediate alerts
        (e.g., after a lockout or mechanical error).
        """
        user = self.db.get_user(user_id)
        schedule = self.db.get_schedule(schedule_id)
        if not user or not schedule:
            logger.error("Cannot send alert — user or schedule not found")
            return

        if outcome == "REJECTED":
            self.gsm.send_unauthorized_alert(
                caregiver_phone=user["caregiver_phone"],
                scheduled_time=scheduled_time,
            )
        else:
            self.gsm.send_missed_dose_alert(
                patient_name=user["full_name"],
                medication_name=schedule["medication_name"],
                scheduled_time=scheduled_time,
                caregiver_phone=user["caregiver_phone"],
            )
