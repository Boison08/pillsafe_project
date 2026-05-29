"""
PillSafe — FaceNet Recogniser (MobileFaceNet TFLite)
Uses a pretrained MobileFaceNet model converted to TensorFlow Lite
to generate face embeddings for identity verification.

Pipeline:
  1. Receive a face ROI (cropped by detector.py)
  2. Preprocess: resize to model input size, convert to RGB, normalize to [-1, 1]
  3. Run inference through the TFLite interpreter → embedding vector
  4. Compare embeddings using cosine similarity

Model:
  - Architecture: MobileFaceNet (lightweight variant of ArcFace/FaceNet)
  - Format: TensorFlow Lite (.tflite)
  - Input: 112×112×3 RGB float32 image, normalized to [-1, 1]
  - Output: L2-normalized embedding vector (128 or 512 dimensions)
  - Source: Pretrained on MS-Celeb-1M / CASIA-WebFace (open-source weights)

References:
  - S. Chen et al., "MobileFaceNets: Efficient CNNs for Accurate Real-Time
    Face Verification on Mobile Devices," arXiv:1804.07573, 2018.
"""

import os
import cv2
import numpy as np
from scipy.spatial.distance import cosine
from utils.config import get_config
from utils.logger import setup_logger

logger = setup_logger("pillsafe.facenet")

# ── TFLite import (works on both Pi and dev machines) ───────────
try:
    import tflite_runtime.interpreter as tflite
    TFLITE_SOURCE = "tflite_runtime"
except ImportError:
    try:
        from ai_edge_litert import interpreter as _ai_edge
        tflite = _ai_edge
        TFLITE_SOURCE = "ai_edge_litert"
    except ImportError:
        try:
            import tensorflow as tf
            tflite = tf.lite
            TFLITE_SOURCE = "tensorflow"
        except ImportError:
            tflite = None
            TFLITE_SOURCE = None
            logger.error(
                "No TFLite runtime found. Install one of: "
                "pip install ai-edge-litert  OR  pip install tflite-runtime"
            )


class FaceNetRecogniser:
    """
    MobileFaceNet TFLite recogniser.
    Generates face embeddings and compares them via cosine similarity.
    """

    DEFAULT_MODEL_PATH = "data/models/mobilefacenet.tflite"

    def __init__(self):
        cfg = get_config()
        self.dataset_path = cfg.face.dataset_path
        self.distance_threshold = getattr(cfg.face, "distance_threshold", 0.6)
        self.model_path = getattr(
            cfg.face, "model_path", self.DEFAULT_MODEL_PATH
        )

        # ── TFLite interpreter state ────────────────────────────
        self._interpreter = None
        self._input_details = None
        self._output_details = None
        self._input_shape = None          # e.g. (1, 112, 112, 3)
        self._embedding_dim = None        # e.g. 128 or 512

        if tflite is not None:
            self._load_model()

        # user_id → np.ndarray of shape (N, embedding_dim)
        self.user_embeddings: dict[int, np.ndarray] = {}
        self._load_embeddings()

    # ────────────────────────────────────────────────────────────
    # Model loading
    # ────────────────────────────────────────────────────────────
    def _load_model(self) -> None:
        """Load the MobileFaceNet .tflite model into the interpreter."""
        if not os.path.isfile(self.model_path):
            logger.warning(
                "TFLite model not found at '%s'. "
                "Download a MobileFaceNet .tflite model and place it there. "
                "See README — Setup section for instructions.",
                self.model_path,
            )
            return

        try:
            if TFLITE_SOURCE == "tflite_runtime":
                self._interpreter = tflite.Interpreter(
                    model_path=self.model_path,
                    num_threads=4,
                )
            else:
                self._interpreter = tflite.Interpreter(
                    model_path=self.model_path,
                    num_threads=4,
                )

            self._interpreter.allocate_tensors()
            self._input_details = self._interpreter.get_input_details()
            self._output_details = self._interpreter.get_output_details()

            # Discover model dimensions dynamically
            self._input_shape = self._input_details[0]["shape"]
            self._embedding_dim = self._output_details[0]["shape"][-1]

            h, w = int(self._input_shape[1]), int(self._input_shape[2])
            logger.info(
                "TFLite model loaded — input %dx%dx3, "
                "embedding dim %d  [backend: %s]",
                h, w, self._embedding_dim, TFLITE_SOURCE,
            )
        except Exception as exc:
            logger.error("Failed to load TFLite model: %s", exc)
            self._interpreter = None

    # ────────────────────────────────────────────────────────────
    # Embedding storage  (per-user .npy files)
    # ────────────────────────────────────────────────────────────
    def _embeddings_file(self, user_id: int) -> str:
        """Return the path to a user's stored embeddings file."""
        return os.path.join(self.dataset_path, str(user_id), "embeddings.npy")

    def _load_embeddings(self) -> None:
        """Load all per-user embedding files from disk."""
        self.user_embeddings = {}

        if not os.path.isdir(self.dataset_path):
            logger.info("Dataset path does not exist yet: %s", self.dataset_path)
            return

        for entry in os.listdir(self.dataset_path):
            user_dir = os.path.join(self.dataset_path, entry)
            if not os.path.isdir(user_dir):
                continue
            try:
                user_id = int(entry)
            except ValueError:
                continue

            emb_file = self._embeddings_file(user_id)
            if os.path.isfile(emb_file):
                try:
                    emb = np.load(emb_file)
                    self.user_embeddings[user_id] = emb
                    logger.info(
                        "Loaded %d embeddings for user %d", emb.shape[0], user_id
                    )
                except Exception as exc:
                    logger.error(
                        "Failed to load embeddings for user %d: %s", user_id, exc
                    )

        logger.info(
            "Embedding store ready — %d enrolled user(s)", len(self.user_embeddings)
        )

    # ────────────────────────────────────────────────────────────
    # Preprocessing
    # ────────────────────────────────────────────────────────────
    def _preprocess(self, face_roi: np.ndarray) -> np.ndarray:
        """
        Prepare a face ROI for the TFLite model.

        Steps:
          1. Convert greyscale → BGR → RGB if needed
          2. Resize to model input size (e.g. 112×112)
          3. Normalize pixel values to [-1, 1]
          4. Add batch dimension → (1, H, W, 3)
        """
        img = face_roi.copy()

        # Ensure 3-channel colour
        if len(img.shape) == 2:
            # Greyscale input (from detector.py which outputs greyscale ROIs)
            img = cv2.cvtColor(img, cv2.COLOR_GRAY2BGR)
        elif img.shape[2] == 4:
            img = cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)

        # BGR → RGB  (MobileFaceNet expects RGB input)
        img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)

        # Resize to what the model expects
        h, w = int(self._input_shape[1]), int(self._input_shape[2])
        img = cv2.resize(img, (w, h))

        # Normalize to [-1, 1]  (standard for MobileFaceNet / ArcFace)
        img = img.astype(np.float32)
        img = (img - 127.5) / 127.5

        # Batch dimension
        return np.expand_dims(img, axis=0)

    # ────────────────────────────────────────────────────────────
    # Embedding generation
    # ────────────────────────────────────────────────────────────
    def generate_embedding(self, face_roi: np.ndarray) -> np.ndarray:
        """
        Run a face ROI through MobileFaceNet and return the
        L2-normalised embedding vector.

        Args:
            face_roi: Face region of interest (any size, grey or BGR).

        Returns:
            1-D numpy float32 array of shape (embedding_dim,), L2-normalised.

        Raises:
            RuntimeError: If the TFLite model is not loaded.
        """
        if self._interpreter is None:
            raise RuntimeError(
                "TFLite model is not loaded. "
                "Place a MobileFaceNet .tflite file at: " + self.model_path
            )

        tensor = self._preprocess(face_roi)

        # Run inference
        self._interpreter.set_tensor(
            self._input_details[0]["index"], tensor
        )
        self._interpreter.invoke()

        embedding = self._interpreter.get_tensor(
            self._output_details[0]["index"]
        )[0]  # Remove batch dim → (embedding_dim,)

        # L2 normalise (essential for cosine similarity to work correctly)
        norm = np.linalg.norm(embedding)
        if norm > 0:
            embedding = embedding / norm

        return embedding.astype(np.float32)

    # ────────────────────────────────────────────────────────────
    # Training (embedding generation for enrolled users)
    # ────────────────────────────────────────────────────────────
    def train(self) -> bool:
        """
        Generate and store embeddings for every enrolled user.

        Reads face images from  data/dataset/{user_id}/  , runs each
        through MobileFaceNet, and saves the resulting embedding matrix
        as a per-user .npy file alongside the images.

        Returns:
            True if at least one user was successfully processed.
        """
        if self._interpreter is None:
            logger.error("Cannot train — TFLite model is not loaded")
            return False

        if not os.path.isdir(self.dataset_path):
            logger.warning("Dataset path does not exist: %s", self.dataset_path)
            return False

        total_users = 0
        total_embeddings = 0

        for user_dir_name in sorted(os.listdir(self.dataset_path)):
            user_path = os.path.join(self.dataset_path, user_dir_name)
            if not os.path.isdir(user_path):
                continue

            try:
                user_id = int(user_dir_name)
            except ValueError:
                continue

            image_files = [
                f for f in os.listdir(user_path)
                if f.lower().endswith((".jpg", ".jpeg", ".png", ".pgm"))
            ]

            if not image_files:
                logger.warning("No images found for user %d", user_id)
                continue

            logger.info(
                "Generating embeddings for user %d (%d images)",
                user_id, len(image_files),
            )

            embeddings = []
            for img_name in image_files:
                img_path = os.path.join(user_path, img_name)
                try:
                    img = cv2.imread(img_path)
                    if img is None:
                        logger.warning("Cannot read image: %s", img_path)
                        continue
                    emb = self.generate_embedding(img)
                    embeddings.append(emb)
                except Exception as exc:
                    logger.error("Error processing %s: %s", img_path, exc)

            if not embeddings:
                logger.warning("No valid embeddings generated for user %d", user_id)
                continue

            emb_array = np.array(embeddings, dtype=np.float32)
            emb_file = self._embeddings_file(user_id)
            np.save(emb_file, emb_array)

            self.user_embeddings[user_id] = emb_array
            total_users += 1
            total_embeddings += len(embeddings)

            logger.info(
                "User %d: saved %d embeddings -> %s",
                user_id, len(embeddings), emb_file,
            )

        logger.info(
            "Training complete — %d user(s), %d total embeddings",
            total_users, total_embeddings,
        )
        return total_users > 0

    # ────────────────────────────────────────────────────────────
    # Prediction
    # ────────────────────────────────────────────────────────────
    def predict(self, face_roi: np.ndarray) -> tuple[int, float]:
        """
        Identify a face by comparing its embedding against all enrolled users.

        Method:
          - Cosine distance between the probe and every stored embedding.
          - Mean distance per user.
          - Best (lowest distance) user wins.
          - Confidence = max(0, (1 - distance) × 100).

        Args:
            face_roi: Face region of interest (any size, grey or BGR).

        Returns:
            (user_id, confidence) — best-matching user and 0–100 score.

        Raises:
            RuntimeError: If no embeddings are loaded.
        """
        if not self.user_embeddings:
            raise RuntimeError("No enrolled users — run enrolment first")

        probe = self.generate_embedding(face_roi)

        best_user_id = None
        best_distance = float("inf")

        for user_id, stored_embeddings in self.user_embeddings.items():
            distances = [
                cosine(probe, stored) for stored in stored_embeddings
            ]
            avg_dist = float(np.mean(distances))

            logger.debug(
                "User %d: avg cosine distance = %.4f", user_id, avg_dist
            )

            if avg_dist < best_distance:
                best_distance = avg_dist
                best_user_id = user_id

        # Distance → confidence  (0 – 100 scale)
        confidence = max(0.0, (1.0 - best_distance) * 100.0)

        logger.info(
            "Prediction: user=%d, cosine_dist=%.4f, confidence=%.1f",
            best_user_id, best_distance, confidence,
        )
        return best_user_id, confidence

    # ────────────────────────────────────────────────────────────
    # Utilities
    # ────────────────────────────────────────────────────────────
    @property
    def is_trained(self) -> bool:
        """True if at least one user has stored embeddings."""
        return len(self.user_embeddings) > 0

    @property
    def model_loaded(self) -> bool:
        """True if the TFLite interpreter is ready."""
        return self._interpreter is not None
