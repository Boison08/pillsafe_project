#!/usr/bin/env python
"""
PillSafe — Standalone User Enrolment Tool
==========================================
Enrol one or more users with a live camera preview.

For each user this script:
  1. Creates the database record (name, caregiver phone, compartment).
  2. Captures face samples with a live preview window (bounding box +
     progress bar) into  data/dataset/<user_id>/ .
  3. Trains the MobileFaceNet embeddings  ->  data/dataset/<user_id>/embeddings.npy .
  4. Marks the user as enrolled in the database.

Usage:
    python enroll_new_user.py

Controls during capture:
    q  — abort the current capture
"""

import os
import sys
import time

import cv2

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from utils.config import load_config, get_config
from utils.logger import setup_logger
from core.camera import Camera
from core.detector import FaceDetector
from core.facenet_recogniser import FaceNetRecogniser
from database.db_manager import DatabaseManager

logger = setup_logger("pillsafe.enroll")

WINDOW_NAME = "PillSafe Enrolment — press 'q' to abort"


# ──────────────────────────────────────────────────────────────────
# Live preview overlay
# ──────────────────────────────────────────────────────────────────
def draw_overlay(frame, name, captured, total, bbox=None, face_ok=False):
    """Return a copy of `frame` with enrolment overlays drawn on it."""
    disp = frame.copy()
    h, w = disp.shape[:2]

    # Top banner
    top = disp.copy()
    cv2.rectangle(top, (0, 0), (w, 70), (0, 0, 0), -1)
    cv2.addWeighted(top, 0.6, disp, 0.4, 0, disp)
    cv2.putText(disp, "ENROLLMENT", (15, 28),
                cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 165, 255), 2)
    cv2.putText(disp, f"User: {name}", (15, 55),
                cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 1)

    # Face bounding box
    if bbox is not None:
        x, y, bw, bh = bbox
        colour = (0, 255, 0) if face_ok else (0, 200, 255)
        cv2.rectangle(disp, (x, y), (x + bw, y + bh), colour, 2)

    # Progress bar
    bar_x, bar_y, bar_w = 15, h - 40, w - 30
    pct = captured / total if total else 0
    cv2.rectangle(disp, (bar_x, bar_y), (bar_x + bar_w, bar_y + 22),
                  (80, 80, 80), -1)
    cv2.rectangle(disp, (bar_x, bar_y), (bar_x + int(bar_w * pct), bar_y + 22),
                  (0, 255, 0), -1)
    cv2.putText(disp, f"Samples: {captured}/{total}", (bar_x + 8, bar_y + 17),
                cv2.FONT_HERSHEY_SIMPLEX, 0.55, (255, 255, 255), 1)

    # Hint
    hint = "Face detected - hold steady, vary angle slightly" if face_ok \
        else "Position your face in the frame..."
    cv2.putText(disp, hint, (15, h - 55),
                cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 255), 1)

    return disp


# ──────────────────────────────────────────────────────────────────
# Sample capture with live preview
# ──────────────────────────────────────────────────────────────────
def capture_samples(camera, detector, user_id, name, sample_count, dataset_path):
    """
    Capture `sample_count` face samples with a live preview.
    Returns the number of samples actually captured (0 if aborted).
    """
    user_dir = os.path.join(dataset_path, str(user_id))
    os.makedirs(user_dir, exist_ok=True)

    # Clear any existing samples (supports clean re-enrolment)
    for f in os.listdir(user_dir):
        try:
            os.remove(os.path.join(user_dir, f))
        except OSError:
            pass

    print(f"\nCapturing {sample_count} samples for '{name}'.")
    print("A preview window will open. Look at the camera and vary your")
    print("head angle slightly. Press 'q' in the window to abort.\n")

    captured = 0
    last_save = 0.0
    max_attempts = sample_count * 30
    attempts = 0

    while captured < sample_count and attempts < max_attempts:
        attempts += 1
        frame = camera.capture_frame()
        if frame is None:
            time.sleep(0.05)
            continue

        detections = detector.detect_and_extract(frame)
        bbox = None
        face_ok = len(detections) > 0

        if face_ok:
            # Use the largest detected face
            roi, bbox = max(detections, key=lambda d: d[1][2] * d[1][3])

            # Throttle saves so samples capture some variation (~0.25s apart)
            now = time.time()
            if now - last_save >= 0.25:
                img_path = os.path.join(user_dir, f"face_{captured:03d}.jpg")
                cv2.imwrite(img_path, roi)
                captured += 1
                last_save = now
                logger.info("Captured sample %d/%d for user %d",
                            captured, sample_count, user_id)

        disp = draw_overlay(frame, name, captured, sample_count, bbox, face_ok)
        cv2.imshow(WINDOW_NAME, disp)

        if (cv2.waitKey(1) & 0xFF) == ord('q'):
            print("Capture aborted by user.")
            break

    cv2.destroyWindow(WINDOW_NAME)
    cv2.waitKey(1)  # flush the window-close event on some platforms
    return captured


# ──────────────────────────────────────────────────────────────────
# Console prompts for a new user
# ──────────────────────────────────────────────────────────────────
def prompt_new_user(db, max_compartment=5):
    """Prompt for new-user details and create the DB record. Returns user_id or None."""
    taken = {u["compartment_index"] for u in db.get_all_users()}
    free = [c for c in range(max_compartment + 1) if c not in taken]

    if not free:
        print("\nAll compartments are occupied — no room for a new user.")
        print("Free up a compartment (delete a user) before enrolling another.")
        return None

    name = input("Full name: ").strip()
    while not name:
        name = input("Full name (cannot be empty): ").strip()

    phone = input("Caregiver phone (e.g. +233...): ").strip()
    while not phone:
        phone = input("Caregiver phone (cannot be empty): ").strip()

    print(f"Available compartments: {free}")
    while True:
        raw = input(f"Compartment index {free}: ").strip()
        try:
            compartment = int(raw)
        except ValueError:
            print("  Please enter a number.")
            continue
        if compartment not in free:
            print(f"  Compartment must be one of the free slots: {free}")
            continue
        break

    user_id = db.create_user(name, phone, compartment)
    print(f"\nCreated user '{name}' (ID {user_id}, compartment {compartment}).")
    return user_id


# ──────────────────────────────────────────────────────────────────
# Main
# ──────────────────────────────────────────────────────────────────
def main():
    load_config()
    cfg = get_config()

    db = DatabaseManager()
    camera = Camera(resolution=(640, 480))
    detector = FaceDetector()
    recogniser = FaceNetRecogniser()

    if not recogniser.model_loaded:
        print("ERROR: MobileFaceNet model not loaded.")
        print(f"  Expected model at: {recogniser.model_path}")
        return 1

    sample_count = cfg.face.sample_count
    dataset_path = cfg.face.dataset_path
    max_compartment = cfg.servo.num_compartments - 1

    print("\n" + "=" * 60)
    print("PillSafe — User Enrolment")
    print("=" * 60)

    camera.start()
    if not camera.is_active:
        print("ERROR: Could not start the camera. Check the connection.")
        return 1

    try:
        while True:
            # Show current users
            users = db.get_all_users()
            print("\nCurrently registered users:")
            if users:
                for u in users:
                    status = "ENROLLED" if u["enrolment_status"] else "NOT ENROLLED"
                    print(f"  ID {u['user_id']}: {u['full_name']} "
                          f"(compartment {u['compartment_index']}) [{status}]")
            else:
                print("  (none)")

            # Create the new user
            user_id = prompt_new_user(db, max_compartment)
            if user_id is None:
                break

            user = db.get_user(user_id)
            name = user["full_name"]

            input("\nPress ENTER when you are ready to start capture...")

            captured = capture_samples(
                camera, detector, user_id, name, sample_count, dataset_path
            )

            if captured < 10:
                print(f"\nOnly {captured} samples captured — not enough to enrol "
                      f"reliably (need >= 10).")
                print("The user record was created but NOT marked enrolled.")
                print("Re-run capture for this user later, or delete the record.")
            else:
                print(f"\nCaptured {captured} samples. Training embeddings...")
                if recogniser.train():
                    db.set_enrolment_status(user_id, enrolled=True)
                    print(f"SUCCESS: '{name}' (ID {user_id}) is enrolled "
                          f"and ready for verification.")
                else:
                    print("ERROR: Embedding training failed — see logs.")

            again = input("\nEnrol another user? (y/N): ").strip().lower()
            if again != "y":
                break

    except KeyboardInterrupt:
        print("\nInterrupted.")
    finally:
        camera.stop()
        cv2.destroyAllWindows()
        cv2.waitKey(1)

    print("\nEnrolment session finished.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
