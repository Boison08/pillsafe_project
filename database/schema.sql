PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS Users (
    user_id             INTEGER PRIMARY KEY AUTOINCREMENT,
    full_name           TEXT    NOT NULL,
    caregiver_phone     TEXT    NOT NULL,
    compartment_index   INTEGER NOT NULL UNIQUE CHECK (compartment_index BETWEEN 0 AND 5),
    enrolment_status    INTEGER DEFAULT 0 CHECK (enrolment_status IN (0, 1)),
    created_at          TEXT    DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS Schedules (
    schedule_id         INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id             INTEGER NOT NULL,
    medication_name     TEXT    NOT NULL,
    dose_time           TEXT    NOT NULL,
    is_active           INTEGER DEFAULT 1 CHECK (is_active IN (0, 1)),
    FOREIGN KEY (user_id) REFERENCES Users(user_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS AdherenceLog (
    log_id              INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id             INTEGER NOT NULL,
    schedule_id         INTEGER NOT NULL,
    scheduled_time      TEXT    NOT NULL,
    actual_time         TEXT,
    outcome             TEXT    NOT NULL CHECK (outcome IN ('TAKEN', 'MISSED', 'REJECTED', 'MECHANICAL_ERROR')),
    sms_sent            INTEGER DEFAULT 0 CHECK (sms_sent IN (0, 1)),
    acknowledged        INTEGER DEFAULT 0 CHECK (acknowledged IN (0, 1)),
    logged_at           TEXT    DEFAULT (datetime('now')),
    FOREIGN KEY (user_id)     REFERENCES Users(user_id)     ON DELETE CASCADE,
    FOREIGN KEY (schedule_id) REFERENCES Schedules(schedule_id) ON DELETE CASCADE
);
