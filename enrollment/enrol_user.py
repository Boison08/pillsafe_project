"""
PillSafe — User Enrolment Module
Captures facial samples for a user, saves them to disk,
and retrains the FaceNet embedding model (SDR §3.2, FR-01 to FR-05).

This can be triggered via:
  - The Flask API (POST /users/{id}/enrol)
  - Directly from the command line for setup
"""

import os
import time
import cv2
from core.camera import Camera
from core.detector import FaceDetector
from core.facenet_recogniser import FaceNetRecogniser
from database.db_manager import DatabaseManager
from utils.config import get_config
from utils.logger import setup_logger

try:
    from core.voice_recogniser import VoiceRecogniser
except Exception:  # pragma: no cover - voice auth is optional when audio deps are missing
    VoiceRecogniser = None

try:
    from core.voice_recogniser import delete_template as delete_voice_template
except Exception:  # pragma: no cover - voice auth is optional when audio deps are missing
    delete_voice_template = None

logger = setup_logger("pillsafe.enrolment")


class EnrolmentManager:
    """Handles facial enrolment: sample capture, storage, and training."""

    def __init__(self, camera: Camera, detector: FaceDetector,
                 recogniser: FaceNetRecogniser, db: DatabaseManager,
                 voice_recogniser: VoiceRecogniser | None = None):
        cfg = get_config()
        self.camera = camera
        self.detector = detector
        self.recogniser = recogniser
        self.db = db
        self.sample_count = cfg.face.sample_count
        self.dataset_path = cfg.face.dataset_path
        self.voice_enabled = bool(getattr(cfg, "voice", None) and getattr(cfg.voice, "enabled", False))
        self.voice_recogniser = voice_recogniser

    def _get_voice_recogniser(self) -> VoiceRecogniser | None:
        if not self.voice_enabled:
            return None
        if self.voice_recogniser is not None:
            return self.voice_recogniser
        if VoiceRecogniser is None:
            logger.warning("Voice enrolment disabled: voice module unavailable")
            return None
        self.voice_recogniser = VoiceRecogniser()
        return self.voice_recogniser

    def enrol_voice_user(self, user_id: int) -> tuple[bool, str]:
        voice = self._get_voice_recogniser()
        if voice is None:
            return True, "Voice enrolment skipped"

        logger.info("Starting voice enrolment for user %d", user_id)
        try:
            result = voice.enrol_user(user_id)
        except Exception as exc:
            return False, f"Voice enrolment failed: {exc}"

        if result.get("success"):
            return True, f"Voice template saved for user {user_id}"
        return False, f"Voice enrolment failed: {result.get('error', 'unknown error')}"

    def enrol_user(self, user_id: int) -> tuple[bool, str]:
        """
        Run the full enrolment sequence for a user.
        1. Verify user exists in DB
        2. Capture facial samples
        3. Save images to dataset/{user_id}/
        4. Retrain the FaceNet embedding model
        5. Update enrolment_status in DB

        Returns (success, message).
        """
        # Step 1: Verify user exists
        user = self.db.get_user(user_id)
        if not user:
            return False, f"User {user_id} does not exist"

        logger.info("Starting enrolment for user %d (%s)", user_id, user["full_name"])

        # Step 2: Prepare dataset directory
        user_dir = os.path.join(self.dataset_path, str(user_id))
        os.makedirs(user_dir, exist_ok=True)

        # Clear any existing samples for re-enrolment
        for f in os.listdir(user_dir):
            os.remove(os.path.join(user_dir, f))

        # Step 3: Capture facial samples
        self.camera.start()
        captured = 0
        attempts = 0
        max_attempts = self.sample_count * 5  # Allow 5x attempts for missed detections

        logger.info("Capturing %d facial samples. Please look at the camera...",
                     self.sample_count)

        while captured < self.sample_count and attempts < max_attempts:
            attempts += 1
            frame = self.camera.capture_frame()
            if frame is None:
                time.sleep(0.1)
                continue

            # Detect and extract face
            detections = self.detector.detect_and_extract(frame)
            if len(detections) == 0:
                time.sleep(0.1)
                continue

            # Use the largest detected face
            roi, bbox = max(detections, key=lambda d: d[1][2] * d[1][3])

            # Save the face ROI
            img_path = os.path.join(user_dir, f"face_{captured:03d}.jpg")
            cv2.imwrite(img_path, roi)
            captured += 1

            if captured % 10 == 0:
                logger.info("Captured %d/%d samples", captured, self.sample_count)

            # Small delay between captures to get variation
            time.sleep(0.2)

        if captured < self.sample_count:
            logger.warning("Only captured %d/%d samples", captured, self.sample_count)
            if captured < 10:
                return False, f"Insufficient samples captured: {captured}/{self.sample_count}"

        # Step 4: Retrain the FaceNet embedding model (FR-09)
        logger.info("Retraining FaceNet embedding model with updated dataset...")
        success = self.recogniser.train()
        if not success:
            return False, "Model training failed"

        # Step 5: Update enrolment status in database
        self.db.set_enrolment_status(user_id, enrolled=True)

        voice_ok, voice_message = self.enrol_voice_user(user_id)

        msg = f"Enrolment complete: {captured} samples captured and model retrained"
        if voice_ok:
            msg = f"{msg}; {voice_message}"
        else:
            logger.warning(voice_message)
            msg = f"{msg}; {voice_message}"
        logger.info(msg)
        return True, msg

    def remove_user_data(self, user_id: int) -> None:
        """Remove a user's facial data and retrain the model."""
        user_dir = os.path.join(self.dataset_path, str(user_id))
        if os.path.exists(user_dir):
            import shutil
            shutil.rmtree(user_dir)
            logger.info("Removed facial data for user %d", user_id)

        if delete_voice_template is not None:
            try:
                delete_voice_template(user_id)
            except Exception as exc:
                logger.warning("Failed to remove voice template for user %d: %s", user_id, exc)

        # Retrain model without this user's data
        self.recogniser.train()


def run_cli_enrolment():
    """
    Command-line enrolment tool for initial setup.
    Usage: python -m enrollment.enrol_user
    """
    from utils.config import load_config
    load_config()

    db = DatabaseManager()
    camera = Camera()
    detector = FaceDetector()
    recogniser = FaceNetRecogniser()
    manager = EnrolmentManager(camera, detector, recogniser, db)

    print("\n=== PillSafe User Enrolment ===\n")

    # Show existing users
    users = db.get_all_users()
    if users:
        print("Existing users:")
        for u in users:
            status = "ENROLLED" if u["enrolment_status"] else "NOT ENROLLED"
            print(f"  ID {u['user_id']}: {u['full_name']} (compartment {u['compartment_index']}) [{status}]")
        print()

    user_id = int(input("Enter user ID to enrol: "))
    user = db.get_user(user_id)

    if not user:
        print(f"\nUser {user_id} not found. Create a new user first via the API or add one below:")
        name = input("Full name: ").strip()
        phone = input("Caregiver phone (e.g. +233...): ").strip()
        compartment = int(input("Compartment index (0-5): "))
        user_id = db.create_user(name, phone, compartment)
        print(f"User created with ID {user_id}")

    print(f"\nStarting enrolment for user {user_id}...")
    print("Please position yourself in front of the camera.")
    print("Move your head slightly between captures for variety.\n")

    input("Press ENTER to begin...")

    success, message = manager.enrol_user(user_id)
    print(f"\n{'SUCCESS' if success else 'FAILED'}: {message}")

    camera.stop()


if __name__ == "__main__":
    run_cli_enrolment()
