"""
PillSafe — Database Manager
SQLite helper functions for Users, Schedules, and AdherenceLog tables.
"""

import os
import sqlite3
import threading
from datetime import datetime
from utils.config import get_config
from utils.logger import setup_logger

logger = setup_logger("pillsafe.database")
_lock = threading.Lock()


class DatabaseManager:
    def __init__(self):
        cfg = get_config()
        self.db_path = cfg.database.path
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        return conn

    def _init_db(self):
        schema_path = os.path.join(os.path.dirname(__file__), "schema.sql")
        with open(schema_path, "r", encoding="utf-8") as f:
            schema_sql = f.read()
        with _lock:
            conn = self._get_connection()
            try:
                conn.executescript(schema_sql)
                conn.commit()
                self._migrate(conn)
                conn.commit()
                logger.info("Database initialised at %s", self.db_path)
            finally:
                conn.close()

    def _migrate(self, conn: sqlite3.Connection) -> None:
        """Additively migrate older databases to the current schema.

        ``CREATE TABLE IF NOT EXISTS`` never alters an existing table, so
        databases created before slots/inventory/notifications were added
        need their new columns backfilled with ``ALTER TABLE ADD COLUMN``.
        """
        def columns(table: str) -> set[str]:
            rows = conn.execute(f"PRAGMA table_info({table})").fetchall()
            return {r["name"] for r in rows}

        schedule_cols = columns("Schedules")
        additions = {
            "slot_index": "INTEGER NOT NULL DEFAULT 0",
            "dosage": "TEXT",
            "pills_per_dose": "INTEGER NOT NULL DEFAULT 1",
            "repeat_days": "TEXT",
        }
        for col, ddl in additions.items():
            if col not in schedule_cols:
                conn.execute(f"ALTER TABLE Schedules ADD COLUMN {col} {ddl}")
                logger.info("Migration: added Schedules.%s", col)

    # ── User Operations ──────────────────────────────────────

    def create_user(self, full_name: str, caregiver_phone: str,
                    compartment_index: int) -> int:
        with _lock:
            conn = self._get_connection()
            try:
                cursor = conn.execute(
                    "INSERT INTO Users (full_name, caregiver_phone, compartment_index) VALUES (?, ?, ?)",
                    (full_name, caregiver_phone, compartment_index),
                )
                conn.commit()
                logger.info("Created user '%s' (id=%d, compartment=%d)",
                            full_name, cursor.lastrowid, compartment_index)
                return cursor.lastrowid
            finally:
                conn.close()

    def get_user(self, user_id: int) -> dict | None:
        conn = self._get_connection()
        try:
            row = conn.execute("SELECT * FROM Users WHERE user_id = ?", (user_id,)).fetchone()
            return dict(row) if row else None
        finally:
            conn.close()

    def get_all_users(self) -> list[dict]:
        conn = self._get_connection()
        try:
            rows = conn.execute("SELECT * FROM Users").fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    def update_user(self, user_id: int, **kwargs) -> bool:
        allowed = {"full_name", "caregiver_phone", "compartment_index", "enrolment_status"}
        fields = {k: v for k, v in kwargs.items() if k in allowed}
        if not fields:
            return False
        set_clause = ", ".join(f"{k} = ?" for k in fields)
        values = list(fields.values()) + [user_id]
        with _lock:
            conn = self._get_connection()
            try:
                conn.execute(f"UPDATE Users SET {set_clause} WHERE user_id = ?", values)
                conn.commit()
                return True
            finally:
                conn.close()

    def delete_user(self, user_id: int) -> bool:
        with _lock:
            conn = self._get_connection()
            try:
                cursor = conn.execute("DELETE FROM Users WHERE user_id = ?", (user_id,))
                conn.commit()
                deleted = cursor.rowcount > 0
                if deleted:
                    logger.info("Deleted user %d", user_id)
                return deleted
            finally:
                conn.close()

    def set_enrolment_status(self, user_id: int, enrolled: bool) -> None:
        self.update_user(user_id, enrolment_status=1 if enrolled else 0)

    # ── Schedule Operations ──────────────────────────────────

    def create_schedule(self, user_id: int, medication_name: str, dose_time: str,
                        slot_index: int = 0, dosage: str | None = None,
                        pills_per_dose: int = 1,
                        repeat_days: str | None = None) -> int:
        user = self.get_user(user_id)
        if not user:
            raise ValueError(f"User {user_id} does not exist")
        if not (0 <= int(slot_index) <= 8):
            raise ValueError("slot_index must be between 0 and 8")
        if int(pills_per_dose) < 1:
            raise ValueError("pills_per_dose must be >= 1")
        with _lock:
            conn = self._get_connection()
            try:
                cursor = conn.execute(
                    "INSERT INTO Schedules "
                    "(user_id, medication_name, dose_time, slot_index, dosage, "
                    "pills_per_dose, repeat_days) VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (user_id, medication_name, dose_time, int(slot_index), dosage,
                     int(pills_per_dose), repeat_days),
                )
                conn.commit()
                logger.info("Created schedule %d for user %d: %s at %s (slot %d)",
                            cursor.lastrowid, user_id, medication_name, dose_time,
                            int(slot_index))
                return cursor.lastrowid
            finally:
                conn.close()

    def get_schedule(self, schedule_id: int) -> dict | None:
        conn = self._get_connection()
        try:
            row = conn.execute("SELECT * FROM Schedules WHERE schedule_id = ?", (schedule_id,)).fetchone()
            return dict(row) if row else None
        finally:
            conn.close()

    def get_active_schedules(self, user_id: int | None = None) -> list[dict]:
        conn = self._get_connection()
        try:
            if user_id:
                rows = conn.execute(
                    "SELECT s.*, u.compartment_index, u.full_name "
                    "FROM Schedules s JOIN Users u ON s.user_id = u.user_id "
                    "WHERE s.is_active = 1 AND s.user_id = ?", (user_id,),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT s.*, u.compartment_index, u.full_name "
                    "FROM Schedules s JOIN Users u ON s.user_id = u.user_id "
                    "WHERE s.is_active = 1"
                ).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    def get_schedule_with_user(self, schedule_id: int) -> dict | None:
        """Return a schedule joined with its owner's compartment and name."""
        conn = self._get_connection()
        try:
            row = conn.execute(
                "SELECT s.*, u.compartment_index, u.full_name "
                "FROM Schedules s JOIN Users u ON s.user_id = u.user_id "
                "WHERE s.schedule_id = ?", (schedule_id,),
            ).fetchone()
            return dict(row) if row else None
        finally:
            conn.close()

    def update_schedule(self, schedule_id: int, **kwargs) -> bool:
        allowed = {"medication_name", "dose_time", "is_active", "slot_index",
                   "dosage", "pills_per_dose", "repeat_days"}
        fields = {k: v for k, v in kwargs.items() if k in allowed}
        if not fields:
            return False
        set_clause = ", ".join(f"{k} = ?" for k in fields)
        values = list(fields.values()) + [schedule_id]
        with _lock:
            conn = self._get_connection()
            try:
                conn.execute(f"UPDATE Schedules SET {set_clause} WHERE schedule_id = ?", values)
                conn.commit()
                return True
            finally:
                conn.close()

    def delete_schedule(self, schedule_id: int) -> bool:
        with _lock:
            conn = self._get_connection()
            try:
                cursor = conn.execute("DELETE FROM Schedules WHERE schedule_id = ?", (schedule_id,))
                conn.commit()
                return cursor.rowcount > 0
            finally:
                conn.close()

    # ── Adherence Log Operations ─────────────────────────────

    def log_event(self, user_id: int, schedule_id: int,
                  scheduled_time: str, outcome: str,
                  actual_time: str | None = None) -> int:
        with _lock:
            conn = self._get_connection()
            try:
                cursor = conn.execute(
                    "INSERT INTO AdherenceLog "
                    "(user_id, schedule_id, scheduled_time, actual_time, outcome) "
                    "VALUES (?, ?, ?, ?, ?)",
                    (user_id, schedule_id, scheduled_time, actual_time, outcome),
                )
                conn.commit()
                logger.info("Logged %s for user %d, schedule %d", outcome, user_id, schedule_id)
                return cursor.lastrowid
            finally:
                conn.close()

    def get_adherence_logs(self, user_id: int | None = None,
                           date: str | None = None) -> list[dict]:
        conn = self._get_connection()
        try:
            query = "SELECT * FROM AdherenceLog WHERE 1=1"
            params = []
            if user_id:
                query += " AND user_id = ?"
                params.append(user_id)
            if date:
                query += " AND DATE(logged_at) = ?"
                params.append(date)
            query += " ORDER BY logged_at DESC"
            rows = conn.execute(query, params).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    def mark_sms_sent(self, log_id: int) -> None:
        with _lock:
            conn = self._get_connection()
            try:
                conn.execute("UPDATE AdherenceLog SET sms_sent = 1 WHERE log_id = ?", (log_id,))
                conn.commit()
            finally:
                conn.close()

    def acknowledge_event(self, log_id: int) -> bool:
        with _lock:
            conn = self._get_connection()
            try:
                cursor = conn.execute(
                    "UPDATE AdherenceLog SET acknowledged = 1 WHERE log_id = ?", (log_id,))
                conn.commit()
                return cursor.rowcount > 0
            finally:
                conn.close()

    def get_unacknowledged_missed(self) -> list[dict]:
        conn = self._get_connection()
        try:
            rows = conn.execute(
                "SELECT al.*, u.full_name, u.caregiver_phone, s.medication_name "
                "FROM AdherenceLog al "
                "JOIN Users u ON al.user_id = u.user_id "
                "JOIN Schedules s ON al.schedule_id = s.schedule_id "
                "WHERE al.outcome IN ('MISSED', 'REJECTED', 'MECHANICAL_ERROR') "
                "AND al.acknowledged = 0 ORDER BY al.logged_at DESC"
            ).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    # ── Inventory Operations ─────────────────────────────────

    def upsert_inventory(self, compartment_index: int, slot_index: int,
                         pill_count: int, medication_name: str | None = None,
                         low_threshold: int | None = None,
                         user_id: int | None = None) -> None:
        """Create or replace the inventory row for one physical slot."""
        with _lock:
            conn = self._get_connection()
            try:
                existing = conn.execute(
                    "SELECT inventory_id FROM Inventory "
                    "WHERE compartment_index = ? AND slot_index = ?",
                    (compartment_index, slot_index),
                ).fetchone()
                if existing:
                    sets = ["pill_count = ?", "updated_at = datetime('now')"]
                    vals: list = [int(pill_count)]
                    if medication_name is not None:
                        sets.append("medication_name = ?")
                        vals.append(medication_name)
                    if low_threshold is not None:
                        sets.append("low_threshold = ?")
                        vals.append(int(low_threshold))
                    if user_id is not None:
                        sets.append("user_id = ?")
                        vals.append(user_id)
                    vals += [compartment_index, slot_index]
                    conn.execute(
                        f"UPDATE Inventory SET {', '.join(sets)} "
                        "WHERE compartment_index = ? AND slot_index = ?", vals,
                    )
                else:
                    conn.execute(
                        "INSERT INTO Inventory (user_id, compartment_index, "
                        "slot_index, medication_name, pill_count, low_threshold) "
                        "VALUES (?, ?, ?, ?, ?, ?)",
                        (user_id, compartment_index, slot_index, medication_name,
                         int(pill_count),
                         5 if low_threshold is None else int(low_threshold)),
                    )
                conn.commit()
            finally:
                conn.close()

    def get_inventory(self, compartment_index: int | None = None) -> list[dict]:
        conn = self._get_connection()
        try:
            if compartment_index is None:
                rows = conn.execute(
                    "SELECT * FROM Inventory ORDER BY compartment_index, slot_index"
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM Inventory WHERE compartment_index = ? "
                    "ORDER BY slot_index", (compartment_index,),
                ).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    def get_slot_inventory(self, compartment_index: int, slot_index: int) -> dict | None:
        conn = self._get_connection()
        try:
            row = conn.execute(
                "SELECT * FROM Inventory WHERE compartment_index = ? AND slot_index = ?",
                (compartment_index, slot_index),
            ).fetchone()
            return dict(row) if row else None
        finally:
            conn.close()

    def decrement_inventory(self, compartment_index: int, slot_index: int,
                            quantity: int = 1) -> int | None:
        """Decrement a slot's pill count (never below 0).

        Returns the new pill_count, or None if no inventory row exists for
        that slot (inventory tracking is optional per slot).
        """
        with _lock:
            conn = self._get_connection()
            try:
                row = conn.execute(
                    "SELECT pill_count FROM Inventory "
                    "WHERE compartment_index = ? AND slot_index = ?",
                    (compartment_index, slot_index),
                ).fetchone()
                if row is None:
                    return None
                new_count = max(0, int(row["pill_count"]) - int(quantity))
                conn.execute(
                    "UPDATE Inventory SET pill_count = ?, updated_at = datetime('now') "
                    "WHERE compartment_index = ? AND slot_index = ?",
                    (new_count, compartment_index, slot_index),
                )
                conn.commit()
                return new_count
            finally:
                conn.close()

    def get_low_inventory(self) -> list[dict]:
        conn = self._get_connection()
        try:
            rows = conn.execute(
                "SELECT * FROM Inventory WHERE pill_count <= low_threshold "
                "ORDER BY compartment_index, slot_index"
            ).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    # ── Notification Operations ──────────────────────────────

    def add_notification(self, type: str, message: str,
                         user_id: int | None = None) -> int:
        with _lock:
            conn = self._get_connection()
            try:
                cursor = conn.execute(
                    "INSERT INTO Notifications (user_id, type, message) "
                    "VALUES (?, ?, ?)", (user_id, type, message),
                )
                conn.commit()
                return cursor.lastrowid
            finally:
                conn.close()

    def get_notifications(self, user_id: int | None = None,
                          unread_only: bool = False, limit: int = 100) -> list[dict]:
        conn = self._get_connection()
        try:
            query = "SELECT * FROM Notifications WHERE 1=1"
            params: list = []
            if user_id is not None:
                query += " AND (user_id = ? OR user_id IS NULL)"
                params.append(user_id)
            if unread_only:
                query += " AND is_read = 0"
            query += " ORDER BY created_at DESC LIMIT ?"
            params.append(int(limit))
            rows = conn.execute(query, params).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    def mark_notification_read(self, notification_id: int) -> bool:
        with _lock:
            conn = self._get_connection()
            try:
                cursor = conn.execute(
                    "UPDATE Notifications SET is_read = 1 WHERE notification_id = ?",
                    (notification_id,),
                )
                conn.commit()
                return cursor.rowcount > 0
            finally:
                conn.close()
