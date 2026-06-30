"""
PillSafe — unit tests for hardware-independent logic.

Run from the project root:
    pip install pytest
    pytest -q

These tests deliberately avoid the camera, GPIO, audio and serial hardware
so they pass on any development machine.
"""

import os
import sys

import pytest

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

from utils.config import load_config, get_config  # noqa: E402


@pytest.fixture(scope="session", autouse=True)
def _config():
    load_config()
    return get_config()


@pytest.fixture
def db(tmp_path):
    """A DatabaseManager backed by a throwaway SQLite file."""
    from database.db_manager import DatabaseManager
    # ConfigDict wraps nested dicts on access, so mutate the underlying dict.
    get_config()["database"]["path"] = str(tmp_path / "test.db")
    return DatabaseManager()


# ── Scheduler time / repeat-day matching ────────────────────────────────────

def test_is_time_match_within_tolerance():
    from scheduler.schedule_controller import ScheduleController
    assert ScheduleController._is_time_match("08:00", "08:00")
    assert ScheduleController._is_time_match("08:01", "08:00")
    assert ScheduleController._is_time_match("07:59", "08:00")


def test_is_time_match_outside_tolerance():
    from scheduler.schedule_controller import ScheduleController
    assert not ScheduleController._is_time_match("08:02", "08:00")
    assert not ScheduleController._is_time_match("09:00", "08:00")
    assert not ScheduleController._is_time_match("garbage", "08:00")


def test_runs_today_rules():
    from scheduler.schedule_controller import ScheduleController
    # Empty / None → every day
    assert ScheduleController._runs_today(None, 0)
    assert ScheduleController._runs_today("", 6)
    # Explicit weekday membership (0=Mon .. 6=Sun)
    assert ScheduleController._runs_today("0,2,4", 2)
    assert not ScheduleController._runs_today("0,2,4", 3)
    # Malformed → fail open (never silently skip a dose)
    assert ScheduleController._runs_today("mon,tue", 1)


# ── RTC BCD helpers ─────────────────────────────────────────────────────────

@pytest.mark.parametrize("value", [0, 1, 9, 10, 23, 31, 59, 99])
def test_bcd_roundtrip(value):
    from hardware.rtc import _bcd_to_dec, _dec_to_bcd
    assert _bcd_to_dec(_dec_to_bcd(value)) == value


# ── Dispenser angle math (simulation mode, no GPIO) ─────────────────────────

def test_dispenser_slot_angles():
    from hardware.dispenser import Dispenser
    d = Dispenser()
    # 9 slots across 360° → 40° per slot
    assert d.angle_per_slot == pytest.approx(40.0)
    assert d._slot_angle(0) == pytest.approx(0.0)
    assert d._slot_angle(8) == pytest.approx(320.0)
    # Duty cycle stays within the configured PWM band
    duty0 = d._angle_to_duty(d._slot_angle(0))
    duty_max = d._angle_to_duty(d.max_angle)
    assert duty0 == pytest.approx(d.min_duty)
    assert duty_max == pytest.approx(d.max_duty)


def test_dispenser_rejects_bad_indices():
    from hardware.dispenser import Dispenser
    d = Dispenser()
    assert d.rotate_to(-1, 0) is False
    assert d.rotate_to(0, 99) is False
    # Valid call succeeds in simulation mode
    assert d.rotate_to(0, 1) is True


# ── Database: schedules, inventory, notifications ────────────────────────────

def test_create_schedule_with_slot(db):
    uid = db.create_user("Ama Mensah", "+233200000000", 0)
    sid = db.create_schedule(uid, "Metformin", "08:00", slot_index=3,
                             dosage="1 tablet", pills_per_dose=2,
                             repeat_days="0,1,2,3,4")
    sched = db.get_schedule(sid)
    assert sched["slot_index"] == 3
    assert sched["pills_per_dose"] == 2
    assert sched["repeat_days"] == "0,1,2,3,4"
    # Joined view exposes the owner's compartment
    joined = db.get_schedule_with_user(sid)
    assert joined["compartment_index"] == 0


def test_create_schedule_rejects_bad_slot(db):
    uid = db.create_user("Kofi", "+233200000001", 1)
    with pytest.raises(ValueError):
        db.create_schedule(uid, "Drug", "09:00", slot_index=20)


def test_inventory_decrement_and_low_stock(db):
    uid = db.create_user("Yaa", "+233200000002", 2)
    db.upsert_inventory(2, 0, pill_count=3, medication_name="Aspirin",
                        low_threshold=2, user_id=uid)
    assert db.decrement_inventory(2, 0, 1) == 2
    assert db.decrement_inventory(2, 0, 5) == 0  # never below zero
    low = db.get_low_inventory()
    assert any(r["compartment_index"] == 2 and r["slot_index"] == 0 for r in low)
    # Untracked slot returns None rather than raising
    assert db.decrement_inventory(5, 8, 1) is None


def test_notifications_feed(db):
    uid = db.create_user("Esi", "+233200000003", 3)
    nid = db.add_notification("REMINDER", "Time for your dose", user_id=uid)
    feed = db.get_notifications(uid)
    assert any(n["notification_id"] == nid for n in feed)
    assert db.mark_notification_read(nid) is True
    assert db.get_notifications(uid, unread_only=True) == [] or all(
        n["notification_id"] != nid for n in db.get_notifications(uid, unread_only=True)
    )
