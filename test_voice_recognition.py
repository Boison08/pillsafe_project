#!/usr/bin/env python
# coding: utf-8

"""
PillSafe Voice Recognition Test

Standalone script for testing the voice recogniser module on a development PC.

Usage:
  python test_voice_recognition.py --list-challenge
  python test_voice_recognition.py --verify --user-id 1
  python test_voice_recognition.py --enrol --user-id 1
    python test_voice_recognition.py --setup --user-id 1

Notes:
  - Verification requires an existing voice template for the chosen user.
  - Enrolment records multiple utterances and saves a template to disk.
  - The script prints friendly errors if audio dependencies are missing.
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent
os.chdir(PROJECT_ROOT)
sys.path.insert(0, str(PROJECT_ROOT))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Test PillSafe voice recognition")
    parser.add_argument("--user-id", type=int, default=1, help="User ID to verify or enrol")
    parser.add_argument("--list-challenge", action="store_true", help="Print a random challenge prompt and exit")
    parser.add_argument("--verify", action="store_true", help="Run one voice verification attempt")
    parser.add_argument("--enrol", action="store_true", help="Record samples and save a voice template")
    parser.add_argument("--setup", action="store_true", help="Enrol first if needed, then run verification")
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    try:
        from utils.config import load_config, get_config
        from utils.logger import setup_logger
        from core.voice_recogniser import VoiceRecogniser
    except Exception as exc:
        print(f"[ERROR] Failed to import project modules: {exc}")
        return 1

    logger = setup_logger("pillsafe.test_voice")

    try:
        load_config()
        cfg = get_config()
    except Exception as exc:
        print(f"[ERROR] Configuration load failed: {exc}")
        return 1

    voice = VoiceRecogniser()

    if args.list_challenge:
        try:
            print(voice.get_random_challenge())
            return 0
        except Exception as exc:
            print(f"[ERROR] Failed to generate challenge prompt: {exc}")
            return 1

    selected_modes = sum(bool(flag) for flag in (args.enrol, args.verify, args.setup))
    if selected_modes > 1:
        print("[ERROR] Choose only one mode: --enrol, --verify, or --setup")
        return 1

    template_exists = voice.is_enrolled(args.user_id)

    if not args.enrol and not args.verify and not args.setup:
        if template_exists:
            print("[INFO] No mode selected, defaulting to --verify")
            args.verify = True
        else:
            print("[INFO] No voice template found, defaulting to --setup")
            args.setup = True

    voice_cfg = getattr(cfg, "voice", None)
    if voice_cfg is not None:
        print(f"[OK] Voice config loaded: sample_rate={voice_cfg.sample_rate}, duration={voice_cfg.record_duration_sec}s, threshold={voice_cfg.similarity_threshold}")

    print(f"[OK] Project root: {PROJECT_ROOT}")
    print(f"[OK] User ID: {args.user_id}")

    if args.enrol:
        print("[INFO] Starting voice enrolment...")
        print("[INFO] Speak clearly when recording begins.")
        try:
            result = voice.enrol_user(args.user_id)
        except Exception as exc:
            print(f"[ERROR] Enrolment failed: {exc}")
            return 1

        if result.get("success"):
            print(f"[OK] Voice template saved for user {result.get('user_id')}")
            return 0

        print(f"[FAIL] Enrolment failed: {result.get('error', 'unknown error')}")
        return 1

    if args.setup:
        print("[INFO] Starting setup flow: enrolment followed by verification.")
        print("[INFO] Speak clearly during enrolment prompts and again for verification.")
        try:
            enrol_result = voice.enrol_user(args.user_id)
        except Exception as exc:
            print(f"[ERROR] Enrolment failed during setup: {exc}")
            return 1

        if not enrol_result.get("success"):
            print(f"[FAIL] Setup enrolment failed: {enrol_result.get('error', 'unknown error')}")
            return 1

        print(f"[OK] Voice template saved for user {enrol_result.get('user_id')}")

    print("[INFO] Starting voice verification...")
    challenge = voice.get_random_challenge()
    print(f"[PROMPT] {challenge}")
    print("[INFO] Press ENTER when you are ready to start voice verification.")
    input()
    print("[INFO] Speak the prompt aloud when recording begins.")

    if not voice.is_enrolled(args.user_id):
        print(f"[FAIL] No voice template found for user {args.user_id}. Run with --enrol or --setup first.")
        return 1

    try:
        result = voice.verify_user(args.user_id)
    except Exception as exc:
        print(f"[ERROR] Verification failed: {exc}")
        return 1

    if result.get("error"):
        print(f"[FAIL] Verification error: {result['error']}")
        return 1

    verified = bool(result.get("verified"))
    similarity = result.get("similarity", 0.0)
    print(f"[RESULT] verified={verified} similarity={similarity}")
    return 0 if verified else 2


if __name__ == "__main__":
    raise SystemExit(main())