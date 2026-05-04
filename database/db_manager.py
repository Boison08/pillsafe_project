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
        with open(schema_path, "r") as f:
            schema_sql = f.read()
        with _lock:
            conn = self._get_connection()
            try:
                conn.executescript(schema_sql)
                conn.commit()
                logger.info("Database initialised at %s", self.db_path)
            finally:
                conn.close()

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

    def create_schedule(self, user_id: int, medication_name: str, dose_time: str) -> int:
        user = self.get_user(user_id)
        if not user:
            raise ValueError(f"User {user_id} does not exist")
        with _lock:
            conn = self._get_connection()
            try:
                cursor = conn.execute(
                    "INSERT INTO Schedules (user_id, medication_name, dose_time) VALUES (?, ?, ?)",
                    (user_id, medication_name, dose_time),
                )
                conn.commit()
                logger.info("Created schedule %d for user %d: %s at %s",
                            cursor.lastrowid, user_id, medication_name, dose_time)
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

    def update_schedule(self, schedule_id: int, **kwargs) -> bool:
        allowed = {"medication_name", "dose_time", "is_active"}
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
