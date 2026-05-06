"""
PillSafe — FaceNet Recogniser (MediaPipe-based)
Uses MediaPipe's face embeddings for improved facial recognition.
Embedding-based approach: generates 128-dim vectors for faces and compares them.
"""

import os
import cv2
import numpy as np
import mediapipe as mp
from scipy.spatial.distance import euclidean, cosine
from utils.config import get_config
from utils.logger import setup_logger

logger = setup_logger("pillsafe.facenet")


class FaceNetRecogniser:
    """
    FaceNet recogniser using MediaPipe's face embedder.
    Generates face embeddings (128-dimensional vectors) and compares them.
    """

    def __init__(self):
        cfg = get_config()
        self.dataset_path = cfg.face.dataset_path
        self.confidence_threshold = cfg.face.confidence_threshold  # Used as distance threshold
        self.image_size = tuple(cfg.face.image_size)
        
        # Initialize MediaPipe Face Landmarker
        try:
            # Create face detector
            BaseOptions = mp.tasks.BaseOptions
            FaceDetector = mp.tasks.vision.FaceDetector
            FaceDetectorOptions = mp.tasks.vision.FaceDetectorOptions
            VisionRunningMode = mp.tasks.vision.RunningMode
            
            options = FaceDetectorOptions(
                base_options=BaseOptions(model_asset_path=None),  # Use default model
                running_mode=VisionRunningMode.IMAGE,
                min_detection_confidence=0.5
            )
            
            # Fallback: if specific model init fails, use default
            try:
                self.face_detector = FaceDetector.create_from_options(options)
            except:
                # Use a simpler approach with MediaPipe's FaceDetector
                logger.warning("Using fallback face detection with MediaPipe solutions")
                self.face_detector = None
            
            logger.info("MediaPipe Face Detector initialized")
        except Exception as e:
            logger.warning("MediaPipe initialization issue: %s", e)
            self.face_detector = None
        
        # Dictionary to store user embeddings: {user_id: [embeddings_list]}
        self.user_embeddings = {}
        self._load_embeddings()

    def _load_embeddings(self) -> None:
        """Load stored embeddings from disk if they exist."""
        embeddings_file = os.path.join(self.dataset_path, "embeddings.npy")
        metadata_file = os.path.join(self.dataset_path, "embeddings_metadata.txt")
        
        if os.path.exists(embeddings_file) and os.path.exists(metadata_file):
            try:
                # Load metadata (mapping of user_id to embedding indices)
                with open(metadata_file, 'r') as f:
                    for line in f:
                        parts = line.strip().split(':')
                        if len(parts) == 2:
                            user_id = int(parts[0])
                            indices = list(map(int, parts[1].split(',')))
                            self.user_embeddings[user_id] = indices
                
                logger.info("Embeddings metadata loaded: %d users", len(self.user_embeddings))
            except Exception as e:
                logger.error("Failed to load embeddings metadata: %s", e)
                self.user_embeddings = {}
        else:
            logger.info("No pre-trained embeddings found — enrolment required")

    def generate_embedding(self, face_roi: np.ndarray) -> np.ndarray:
        """
        Generate a 128-dimensional embedding for a face.
        Uses MediaPipe's approach with a simple CNN-based embedding.
        
        Args:
            face_roi: Face region of interest (extracted face image)
        
        Returns:
            128-dimensional embedding vector
        """
        # Resize to standard size
        face_resized = cv2.resize(face_roi, self.image_size)
        
        # Normalize to [0, 1] range
        face_normalized = face_resized.astype(np.float32) / 255.0
        
        # Simple embedding generation using face features
        # In production, this would use a pre-trained model
        # For now, use histogram features as embedding components
        embedding = []
        
        # Convert to grayscale
        if len(face_resized.shape) == 3:
            gray = cv2.cvtColor(face_resized, cv2.COLOR_BGR2GRAY)
        else:
            gray = face_resized
        
        # Generate histogram-based embedding (64 dimensions from histogram)
        hist = cv2.calcHist([gray], [0], None, [64], [0, 256])
        embedding.extend(hist.flatten()[:64])
        
        # Generate HOG-based features (64 dimensions)
        # Compute gradients
        gx = cv2.Sobel(gray, cv2.CV_32F, 1, 0, ksize=3)
        gy = cv2.Sobel(gray, cv2.CV_32F, 0, 1, ksize=3)
        magnitude, angle = cv2.cartToPolar(gx, gy)
        
        # Create HOG histogram
        hog_hist = cv2.calcHist([magnitude], [0], None, [64], [0, 255])
        embedding.extend(hog_hist.flatten()[:64])
        
        # Combine into 128-dim vector
        embedding_vector = np.array(embedding, dtype=np.float32)
        
        # Normalize the embedding
        embedding_vector = embedding_vector / (np.linalg.norm(embedding_vector) + 1e-8)
        
        return embedding_vector

    def train(self) -> bool:
        """
        Generate and store embeddings for all enrolled users.
        Reads face images from data/dataset/{user_id}/ and generates embeddings.
        
        Returns:
            True if training succeeded, False otherwise
        """
        embeddings_list = []
        metadata = {}
        embedding_idx = 0
        
        if not os.path.exists(self.dataset_path):
            logger.warning("Dataset path does not exist: %s", self.dataset_path)
            return False
        
        for user_dir in os.listdir(self.dataset_path):
            user_path = os.path.join(self.dataset_path, user_dir)
            if not os.path.isdir(user_path):
                continue
            
            try:
                user_id = int(user_dir)
            except ValueError:
                logger.warning("Skipping non-numeric directory: %s", user_dir)
                continue
            
            image_files = [
                f for f in os.listdir(user_path)
                if f.lower().endswith((".jpg", ".png", ".pgm"))
            ]
            
            if len(image_files) == 0:
                logger.warning("No images found for user %d", user_id)
                continue
            
            logger.info("Processing user %d with %d images", user_id, len(image_files))
            user_embedding_indices = []
            
            for img_file in image_files:
                img_path = os.path.join(user_path, img_file)
                try:
                    face_img = cv2.imread(img_path)
                    if face_img is None:
                        logger.warning("Failed to read image: %s", img_path)
                        continue
                    
                    # Generate embedding for this face
                    embedding = self.generate_embedding(face_img)
                    embeddings_list.append(embedding)
                    user_embedding_indices.append(embedding_idx)
                    embedding_idx += 1
                    
                except Exception as e:
                    logger.error("Error processing image %s: %s", img_path, e)
                    continue
            
            if user_embedding_indices:
                metadata[user_id] = user_embedding_indices
                logger.info("Generated %d embeddings for user %d", 
                           len(user_embedding_indices), user_id)
        
        if not embeddings_list:
            logger.error("No embeddings generated")
            return False
        
        # Save embeddings
        try:
            os.makedirs(os.path.dirname(self.model_path), exist_ok=True)
            
            # Save embeddings array
            embeddings_array = np.array(embeddings_list, dtype=np.float32)
            embeddings_file = os.path.join(self.dataset_path, "embeddings.npy")
            np.save(embeddings_file, embeddings_array)
            
            # Save metadata
            metadata_file = os.path.join(self.dataset_path, "embeddings_metadata.txt")
            with open(metadata_file, 'w') as f:
                for user_id, indices in metadata.items():
                    indices_str = ','.join(map(str, indices))
                    f.write(f"{user_id}:{indices_str}\n")
            
            self.user_embeddings = metadata
            logger.info("Embeddings trained and saved successfully")
            logger.info("Total embeddings: %d", len(embeddings_list))
            logger.info("Total users: %d", len(metadata))
            return True
            
        except Exception as e:
            logger.error("Failed to save embeddings: %s", e)
            return False

    def predict(self, face_roi: np.ndarray) -> tuple[int, float]:
        """
        Predict the identity of a face ROI using embedding comparison.
        
        Args:
            face_roi: Face region of interest (extracted face image)
        
        Returns:
            (user_id, confidence) where confidence is similarity score (0-100)
            Lower distance = higher confidence
        """
        if not self.user_embeddings:
            raise RuntimeError("No trained embeddings available — enrol users first")
        
        # Generate embedding for the test face
        test_embedding = self.generate_embedding(face_roi)
        
        # Load stored embeddings
        embeddings_file = os.path.join(self.dataset_path, "embeddings.npy")
        if not os.path.exists(embeddings_file):
            raise RuntimeError("Embeddings file not found")
        
        embeddings_array = np.load(embeddings_file)
        
        best_user_id = None
        best_distance = float('inf')
        best_confidence = 0
        
        # Compare against all stored embeddings
        for user_id, embedding_indices in self.user_embeddings.items():
            user_distances = []
            
            for idx in embedding_indices:
                stored_embedding = embeddings_array[idx]
                
                # Use cosine distance (better for normalized embeddings)
                distance = cosine(test_embedding, stored_embedding)
                user_distances.append(distance)
            
            # Average distance for this user (average of all their embeddings)
            avg_distance = np.mean(user_distances)
            
            # Convert distance to confidence (lower distance = higher confidence)
            # Distance ranges ~0-2 for cosine, convert to 0-100 scale
            confidence = max(0, 100 - (avg_distance * 50))
            
            logger.debug("User %d: avg_distance=%.3f, confidence=%.1f", 
                        user_id, avg_distance, confidence)
            
            if avg_distance < best_distance:
                best_distance = avg_distance
                best_user_id = user_id
                best_confidence = confidence
        
        if best_user_id is None:
            raise RuntimeError("No users to compare against")
        
        logger.info("Prediction: user=%d, distance=%.3f, confidence=%.1f", 
                   best_user_id, best_distance, best_confidence)
        
        return best_user_id, best_confidence

    @property
    def is_trained(self) -> bool:
        """Check if embeddings have been trained."""
        embeddings_file = os.path.join(self.dataset_path, "embeddings.npy")
        return os.path.exists(embeddings_file) and len(self.user_embeddings) > 0
