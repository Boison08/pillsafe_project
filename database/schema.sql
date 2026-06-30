PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS Users (
    user_id             INTEGER PRIMARY KEY AUTOINCREMENT,
    full_name           TEXT    NOT NULL,
    caregiver_phone     TEXT    NOT NULL,
    compartment_index   INTEGER NOT NULL UNIQUE CHECK (compartment_index BETWEEN 0 AND 5),
    enrolment_status    INTEGER DEFAULT 0 CHECK (enrolment_status IN (0, 1)),
    recognition_model   TEXT    DEFAULT 'facenet' CHECK (recognition_model IN ('lbph', 'facenet')),
    created_at          TEXT    DEFAULT (datetime('now'))
);

-- Store face embeddings for FaceNet-based recognition
CREATE TABLE IF NOT EXISTS FaceEmbeddings (
    embedding_id        INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id             INTEGER NOT NULL,
    embedding_data      BLOB    NOT NULL,  -- numpy array stored as binary
    source_image_path   TEXT,               -- path to source face image
    created_at          TEXT    DEFAULT (datetime('now')),
    FOREIGN KEY (user_id) REFERENCES Users(user_id) ON DELETE CASCADE
);

-- Create index for faster embedding lookups
CREATE INDEX IF NOT EXISTS idx_face_embeddings_user_id ON FaceEmbeddings(user_id);

-- A schedule is a recurring dose. Each schedule targets a specific
-- (compartment, slot): the compartment belongs to the user, and the
-- slot_index (0-8) selects one of the nine angular slots in that
-- compartment's cylinder.
CREATE TABLE IF NOT EXISTS Schedules (
    schedule_id         INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id             INTEGER NOT NULL,
    medication_name     TEXT    NOT NULL,
    dose_time           TEXT    NOT NULL,                        -- "HH:MM"
    slot_index          INTEGER NOT NULL DEFAULT 0 CHECK (slot_index BETWEEN 0 AND 8),
    dosage              TEXT,                                    -- human readable, e.g. "1 tablet", "500mg"
    pills_per_dose      INTEGER NOT NULL DEFAULT 1 CHECK (pills_per_dose >= 1),
    repeat_days         TEXT,                                    -- CSV of weekday ints 0=Mon..6=Sun; NULL/'' = every day
    is_active           INTEGER DEFAULT 1 CHECK (is_active IN (0, 1)),
    FOREIGN KEY (user_id) REFERENCES Users(user_id) ON DELETE CASCADE
);

-- Per-slot medication inventory. One row per physical slot
-- (compartment_index, slot_index). pill_count is decremented on each
-- successful dispense; a LOW_INVENTORY notification fires at/below
-- low_threshold.
CREATE TABLE IF NOT EXISTS Inventory (
    inventory_id        INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id             INTEGER,
    compartment_index   INTEGER NOT NULL CHECK (compartment_index BETWEEN 0 AND 5),
    slot_index          INTEGER NOT NULL CHECK (slot_index BETWEEN 0 AND 8),
    medication_name     TEXT,
    pill_count          INTEGER NOT NULL DEFAULT 0 CHECK (pill_count >= 0),
    low_threshold       INTEGER NOT NULL DEFAULT 5 CHECK (low_threshold >= 0),
    updated_at          TEXT    DEFAULT (datetime('now')),
    UNIQUE (compartment_index, slot_index),
    FOREIGN KEY (user_id) REFERENCES Users(user_id) ON DELETE SET NULL
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

-- Event feed consumed by the mobile app (reminder, dispensed, missed,
-- failed verification, low inventory, device status).
CREATE TABLE IF NOT EXISTS Notifications (
    notification_id     INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id             INTEGER,
    type                TEXT    NOT NULL CHECK (type IN (
                            'REMINDER', 'DISPENSED', 'MISSED', 'REJECTED',
                            'MECHANICAL_ERROR', 'LOW_INVENTORY', 'DEVICE_STATUS')),
    message             TEXT    NOT NULL,
    is_read             INTEGER DEFAULT 0 CHECK (is_read IN (0, 1)),
    created_at          TEXT    DEFAULT (datetime('now')),
    FOREIGN KEY (user_id) REFERENCES Users(user_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_notifications_user_id ON Notifications(user_id);
CREATE INDEX IF NOT EXISTS idx_inventory_slot ON Inventory(compartment_index, slot_index);
