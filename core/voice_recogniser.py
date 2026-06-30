"""
voice_recogniser.py — PillSafe Voice Verification Module
=========================================================
Hardware : I2S MEMS microphone (GPIO-based, e.g. INMP441)
Method   : Speaker verification using MFCC feature extraction +
           cosine similarity on mean MFCC vectors.
Challenge: System delivers a random text prompt via the mobile app
           (GET /voice/challenge); user speaks it aloud; Pi records
           and verifies the voice matches the enrolled profile.

Enrolment : 3 utterances captured, mean MFCC vector stored as .npy
Verification: Cosine similarity between live MFCC and stored template
              must exceed SIMILARITY_THRESHOLD (default 0.82).
"""

import os
import logging
import numpy as np
import sounddevice as sd
import librosa
import random
from pathlib import Path

from utils.config import get_config

logger = logging.getLogger(__name__)

# ── Constants (all overridable via config.yaml) ────────────────────────────
SAMPLE_RATE      = 16000   # Hz — INMP441 native rate
DURATION_SEC     = 3       # seconds to record per utterance
N_MFCC           = 40      # number of MFCC coefficients
ENROL_SAMPLES    = 3       # utterances captured during enrolment
SIM_THRESHOLD    = 0.82    # cosine similarity threshold (0–1)
MODELS_DIR       = Path("models/voice")
DEVICE_INDEX     = None    # None = default input device (set in config.yaml)

# Random prompt pool — displayed on mobile app, spoken by user
CHALLENGE_PROMPTS = [
    "open my medicine",
    "dispense my pills",
    "pillsafe unlock",
    "ready for medication",
    "confirm my dose",
    "give me my pills",
    "pillsafe access",
    "release my medication",
]


class VoiceRecogniser:
    """Compatibility wrapper around the module-level voice helpers."""

    def get_random_challenge(self) -> str:
        return get_random_challenge()

    def enrol_user(self, user_id: int, prompts: list[str] | None = None) -> dict:
        return enrol_user(user_id, prompts=prompts)

    def verify_user(self, user_id: int) -> dict:
        return verify_user(user_id)

    def delete_template(self, user_id: int) -> bool:
        return delete_template(user_id)

    def is_enrolled(self, user_id: int) -> bool:
        return is_enrolled(user_id)


# ── Helpers ────────────────────────────────────────────────────────────────

def _record(duration: float = DURATION_SEC, sample_rate: int = SAMPLE_RATE) -> np.ndarray:
    """Capture audio from the I2S MEMS microphone."""
    cfg = None
    try:
        cfg = get_config()
    except Exception:
        cfg = None

    configured_device = DEVICE_INDEX
    if cfg is not None:
        voice_cfg = getattr(cfg, "voice", None)
        if voice_cfg is not None and getattr(voice_cfg, "device_index", None) is not None:
            configured_device = voice_cfg.device_index

    logger.info("Recording %.1fs of audio…", duration)

    try:
        audio = sd.rec(
            int(duration * sample_rate),
            samplerate=sample_rate,
            channels=1,
            dtype="float32",
            device=configured_device,
        )
        sd.wait()
        return audio.flatten()
    except Exception as exc:
        if configured_device is not None:
            logger.warning("Primary audio device unavailable, falling back to default input: %s", exc)
            audio = sd.rec(
                int(duration * sample_rate),
                samplerate=sample_rate,
                channels=1,
                dtype="float32",
                device=None,
            )
            sd.wait()
            return audio.flatten()
        raise


def _extract_mfcc(audio: np.ndarray, sample_rate: int = SAMPLE_RATE,
                  n_mfcc: int = N_MFCC) -> np.ndarray:
    """
    Extract mean MFCC feature vector from a raw audio array.
    Returns a 1-D vector of shape (N_MFCC,).
    """
    mfcc = librosa.feature.mfcc(y=audio, sr=sample_rate, n_mfcc=n_mfcc)
    return np.mean(mfcc, axis=1)   # shape: (N_MFCC,)


def _cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
    """Return cosine similarity in [0, 1] between two vectors."""
    norm_a = np.linalg.norm(a)
    norm_b = np.linalg.norm(b)
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return float(np.dot(a, b) / (norm_a * norm_b))


def _template_path(user_id: int) -> Path:
    cfg = None
    try:
        cfg = get_config()
    except Exception:
        cfg = None

    models_dir = MODELS_DIR
    if cfg is not None:
        voice_cfg = getattr(cfg, "voice", None)
        if voice_cfg is not None and getattr(voice_cfg, "models_dir", None):
            models_dir = Path(voice_cfg.models_dir)

    return models_dir / f"user_{user_id}_voice.npy"


# ── Public API ─────────────────────────────────────────────────────────────

def get_random_challenge() -> str:
    """Return a random text prompt to display on the mobile app."""
    return random.choice(CHALLENGE_PROMPTS)


def enrol_user(user_id: int, prompts: list[str] | None = None) -> dict:
    """
    Capture ENROL_SAMPLES utterances, compute mean MFCC template,
    and save to disk.

    Called by: POST /users/{id}/enrol  (voice=true query param)

    Returns:
        {"success": True, "user_id": user_id}  on success
        {"success": False, "error": "<reason>"} on failure
    """
    cfg = None
    try:
        cfg = get_config()
    except Exception:
        cfg = None

    voice_cfg = getattr(cfg, "voice", None) if cfg is not None else None
    sample_rate = getattr(voice_cfg, "sample_rate", SAMPLE_RATE)
    duration_sec = getattr(voice_cfg, "record_duration_sec", DURATION_SEC)
    mfcc_count = getattr(voice_cfg, "n_mfcc", N_MFCC)
    enrol_samples = getattr(voice_cfg, "enrol_samples", ENROL_SAMPLES)
    models_dir = Path(getattr(voice_cfg, "models_dir", MODELS_DIR)) if voice_cfg is not None else MODELS_DIR

    models_dir.mkdir(parents=True, exist_ok=True)
    mfcc_vectors = []
    prompt_list = prompts or []

    for i in range(enrol_samples):
        logger.info("Enrolment sample %d/%d for user %d", i + 1, enrol_samples, user_id)
        if prompt_list:
            prompt_text = prompt_list[i % len(prompt_list)]
            print(f"[VOICE PROMPT] {prompt_text}")
            logger.info("Voice enrolment prompt: %s", prompt_text)
            input("Press ENTER when ready to speak...")
        try:
            audio = _record(duration=duration_sec, sample_rate=sample_rate)
            vec = _extract_mfcc(audio, sample_rate=sample_rate, n_mfcc=mfcc_count)
            mfcc_vectors.append(vec)
        except Exception as exc:
            logger.error("Enrolment recording failed: %s", exc)
            return {"success": False, "error": str(exc)}

    template = np.mean(mfcc_vectors, axis=0)  # shape: (N_MFCC,)
    np.save(models_dir / f"user_{user_id}_voice.npy", template)
    logger.info("Voice template saved for user %d", user_id)
    return {"success": True, "user_id": user_id}


def verify_user(user_id: int) -> dict:
    """
    Record one utterance and compare against the stored template.

    Called by: main control loop (voice auth path)

    Returns:
        {"verified": True,  "similarity": float}  on ACCEPT
        {"verified": False, "similarity": float}  on REJECT
        {"verified": False, "error": "<reason>"}  on hard failure
    """
    cfg = None
    try:
        cfg = get_config()
    except Exception:
        cfg = None

    voice_cfg = getattr(cfg, "voice", None) if cfg is not None else None
    threshold = getattr(voice_cfg, "similarity_threshold", SIM_THRESHOLD)
    sample_rate = getattr(voice_cfg, "sample_rate", SAMPLE_RATE) if voice_cfg is not None else SAMPLE_RATE
    duration_sec = getattr(voice_cfg, "record_duration_sec", DURATION_SEC) if voice_cfg is not None else DURATION_SEC
    mfcc_count = getattr(voice_cfg, "n_mfcc", N_MFCC) if voice_cfg is not None else N_MFCC
    path = _template_path(user_id)
    if not path.exists():
        logger.warning("No voice template found for user %d", user_id)
        return {"verified": False, "error": "no_template"}

    template = np.load(path)

    try:
        audio = _record(duration=duration_sec, sample_rate=sample_rate)
        live_vec = _extract_mfcc(audio, sample_rate=sample_rate, n_mfcc=mfcc_count)
    except Exception as exc:
        logger.error("Verification recording failed: %s", exc)
        return {"verified": False, "error": str(exc)}

    similarity = _cosine_similarity(live_vec, template)
    verified = similarity >= threshold

    logger.info(
        "Voice verification for user %d: similarity=%.4f threshold=%.2f → %s",
        user_id, similarity, threshold, "ACCEPT" if verified else "REJECT"
    )
    return {"verified": verified, "similarity": round(similarity, 4)}


def delete_template(user_id: int) -> bool:
    """Remove stored voice template when a user is deleted."""
    path = _template_path(user_id)
    if path.exists():
        path.unlink()
        logger.info("Voice template deleted for user %d", user_id)
        return True
    return False


def is_enrolled(user_id: int) -> bool:
    """Return True if a voice template exists for this user."""
    return _template_path(user_id).exists()
