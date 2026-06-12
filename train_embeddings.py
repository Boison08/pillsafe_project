#!/usr/bin/env python
"""
Run this once after placing mobilefacenet.tflite in data/models/
to generate embeddings.npy for every user in data/dataset/.
"""

import sys
import os

sys.path.insert(0, os.path.dirname(__file__))

from utils.config import load_config
from utils.logger import setup_logger
from core.facenet_recogniser import FaceNetRecogniser

logger = setup_logger("pillsafe.train")

load_config()
recogniser = FaceNetRecogniser()

if not recogniser.model_loaded:
    print("ERROR: TFLite model not loaded.")
    print(f"  Place mobilefacenet.tflite at: {recogniser.model_path}")
    sys.exit(1)

print(f"Model loaded. Training embeddings from {recogniser.dataset_path} ...")
success = recogniser.train()

if success:
    print(f"Done. {len(recogniser.user_embeddings)} user(s) enrolled.")
else:
    print("Training failed — check that sample images exist in data/dataset/<user_id>/")
    sys.exit(1)
