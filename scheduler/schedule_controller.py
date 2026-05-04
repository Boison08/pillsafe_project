"""
PillSafe — Scheduling & Dispensing Controller
Polls the DS3231 RTC and triggers dispensing events when scheduled
times are matched (FR-12, FR-13, FR-16).
Uses APScheduler for the background daemon.
"""

import time
import threading
from datetime import datetime, timedelta
from dataclasses import dataclass

from database.db_manager import DatabaseManager
from hardware.rtc import RealTimeClock
from utils.config import get_config
from utils.logger import setup_logger

logger = setup_logger("pillsafe.scheduler")


@dataclass
class DispenseEvent:
    """Data object representing a triggered dispensing event (SDR §4.3)."""
    user_id: int
    full_name: str
    medication_name: str
    compartment_index: int
    schedule_id: int
    scheduled_time: str           # HH:MM
    grace_deadline: datetime      # scheduled_time + grace_period


class ScheduleController:
    """
    Background daemon that monitors the RTC and triggers dispensing events.
    Uses a simple polling loop instead of APScheduler to reduce dependencies,
    while maintaining the same behaviour described in the SDR.
    """

    def __init__(self, db: DatabaseManager, rtc: RealTimeClock):
        cfg = get_config()
        self.db = db
        self.rtc = rtc
        self.poll_interval = cfg.schedule.poll_interval_seconds
        self.grace_period = cfg.schedule.grace_period_minutes

        self._running = False
        self._thread = None
        self._event_callback = None
        # Track which schedules have already been triggered today
        # to prevent duplicate triggers within the same day
        self._triggered_today: set[int] = set()
        self._last_date: str = ""

    def set_event_callback(self, callback) -> None:
        """
        Register a callback function that will be called when
        a dispensing event is triggered.
        Signature: callback(event: DispenseEvent) -> None
        """
        self._event_callback = callback

    def start(self) -> None:
        """Start the scheduling daemon in a background thread."""
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._poll_loop, daemon=True)
        self._thread.start()
        logger.info("Scheduler started (polling every %ds, grace=%d min)",
                     self.poll_interval, self.grace_period)

    def stop(self) -> None:
        """Stop the scheduling daemon."""
        self._running = False
        if self._thread:
            self._thread.join(timeout=10)
        logger.info("Scheduler stopped")

    def _poll_loop(self) -> None:
        """
        Main polling loop — runs every poll_interval seconds (FR-12).
        Compares RTC time against active schedules.
        """
        while self._running:
            try:
                self._check_schedules()
            except Exception as e:
                logger.error("Scheduler error: %s", e)
            time.sleep(self.poll_interval)

    def _check_schedules(self) -> None:
        """
        Compare current RTC time against all active schedules.
        A match is defined as ±1 minute tolerance (FR-13).
        """
        now = self.rtc.get_time()
        current_time_str = now.strftime("%H:%M")
        current_date = now.strftime("%Y-%m-%d")

        # Reset triggered set at midnight
        if current_date != self._last_date:
            self._triggered_today.clear()
            self._last_date = current_date

        schedules = self.db.get_active_schedules()

        for sched in schedules:
            schedule_id = sched["schedule_id"]

            # Skip if already triggered today
            if schedule_id in self._triggered_today:
                continue

            dose_time = sched["dose_time"]  # "HH:MM"

            # Check ±1 minute tolerance
            if self._is_time_match(current_time_str, dose_time):
                logger.info("Schedule match: user %d, medication '%s' at %s",
                             sched["user_id"], sched["medication_name"], dose_time)

                # Mark as triggered to prevent duplicates
                self._triggered_today.add(schedule_id)

                # Create DispenseEvent
                grace_deadline = now + timedelta(minutes=self.grace_period)
                event = DispenseEvent(
                    user_id=sched["user_id"],
                    full_name=sched["full_name"],
                    medication_name=sched["medication_name"],
                    compartment_index=sched["compartment_index"],
                    schedule_id=schedule_id,
                    scheduled_time=dose_time,
                    grace_deadline=grace_deadline,
                )

                # Dispatch to callback
                if self._event_callback:
                    # Run in a separate thread so the scheduler isn't blocked
                    threading.Thread(
                        target=self._event_callback,
                        args=(event,),
                        daemon=True,
                    ).start()

    @staticmethod
    def _is_time_match(current: str, scheduled: str) -> bool:
        """
        Check if the current time matches the scheduled time
        within a ±1 minute tolerance (FR-13).
        Both times in HH:MM format.
        """
        try:
            c_h, c_m = map(int, current.split(":"))
            s_h, s_m = map(int, scheduled.split(":"))
            current_mins = c_h * 60 + c_m
            scheduled_mins = s_h * 60 + s_m
            return abs(current_mins - scheduled_mins) <= 1
        except (ValueError, AttributeError):
            return False
