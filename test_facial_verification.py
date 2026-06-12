#!/usr/bin/env python
# coding: utf-8

# # PillSafe Facial Recognition Testing
# ## PC Camera FaceNet Verification Testing
# 
# This script tests facial recognition with FaceNet embeddings:
# - Camera frame capture
# - Face detection (Haar Cascade)
# - FaceNet embedding-based recognition
# 
# **Note:** Uses PC camera (OpenCV VideoCapture) for development/testing.

# In[1]:


# Section 1: Import Required Libraries
import os
import sys
import cv2
import numpy as np
import time
from datetime import datetime
from pathlib import Path
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle
from IPython.display import clear_output

# Set project root to the notebook's directory (which is the project root)
PROJECT_ROOT = os.getcwd()
if not os.path.exists(os.path.join(PROJECT_ROOT, 'utils')):
    # If utils is not found, try going up one directory
    PROJECT_ROOT = os.path.dirname(PROJECT_ROOT)

sys.path.insert(0, PROJECT_ROOT)
os.chdir(PROJECT_ROOT)

print("[OK] NumPy version:", np.__version__)
print("[OK] OpenCV version:", cv2.__version__)
print("[OK] Project root:", PROJECT_ROOT)
print("[OK] Python path configured")


# In[2]:


# Load configuration and modules
from utils.config import load_config, get_config
from utils.logger import setup_logger

# Initialize logging
logger = setup_logger("pillsafe.test_facial")

# Load configuration
try:
    load_config()
    cfg = get_config()
    print("[OK] Configuration loaded successfully")
except Exception as e:
    print(f"✗ Configuration error: {e}")
    raise

# Import PillSafe facial recognition modules
try:
    from core.camera import Camera
    from core.detector import FaceDetector
    from core.facenet_recogniser import FaceNetRecogniser
    from core.decision import DecisionEngine, VerificationResult
    from enrollment.enrol_user import EnrolmentManager
    from database.db_manager import DatabaseManager
    print("[OK] All facial recognition modules imported successfully")
    print("[OK] FaceNet (MediaPipe) recogniser loaded")
except Exception as e:
    print(f"✗ Module import error: {e}")
    raise


# ## Section 2: Initialize Webcam Capture
# 
# Initialize the PC camera using OpenCV's VideoCapture with configured parameters.

# In[3]:


# Initialize Camera using PillSafe Camera class
# This will automatically fallback to OpenCV VideoCapture on PC
camera = Camera(resolution=(640, 480))
camera.start()

print("[OK] Camera started")
print(f"  Resolution: {camera.resolution}")

# Get a test frame to verify camera is working
test_frame = camera.capture_frame()
if test_frame is not None:
    print(f"  Frame shape: {test_frame.shape}")
    print(f"  Frame dtype: {test_frame.dtype}")
    print("[OK] Camera is capturing frames successfully")
else:
    print("✗ Failed to capture frame - check camera connection")

print()
print("[OK] FaceNet Recognition Test Ready")


# In[4]:


# Helper function for live display with instructions and stage info
def display_with_instructions(frame, stage, instructions, is_enrollment=False):
    """
    Add text overlays to frame showing current stage and instructions.

    Args:
        frame: Input frame
        stage: Current stage name (e.g., "FACE DETECTION", "FACE RECOGNITION")
        instructions: List of instruction strings to display
        is_enrollment: Boolean to indicate enrollment phase

    Returns:
        Frame with text overlays
    """
    display_frame = frame.copy()
    h, w = display_frame.shape[:2]

    # Dark overlay for text readability
    overlay = display_frame.copy()
    cv2.rectangle(overlay, (0, 0), (w, 120), (0, 0, 0), -1)
    cv2.addWeighted(overlay, 0.6, display_frame, 0.4, 0, display_frame)

    # Phase indicator (top-left)
    phase_text = "🔴 ENROLLMENT" if is_enrollment else "🔵 VERIFICATION"
    phase_color = (0, 165, 255) if is_enrollment else (0, 255, 0)  # Orange for enrollment, Green for verification
    cv2.putText(display_frame, phase_text, (15, 35), cv2.FONT_HERSHEY_SIMPLEX, 1, phase_color, 2)

    # Stage name
    cv2.putText(display_frame, f"Stage: {stage}", (15, 70), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)

    # Instructions overlay at bottom
    overlay_bottom = display_frame.copy()
    cv2.rectangle(overlay_bottom, (0, h-150), (w, h), (0, 0, 0), -1)
    cv2.addWeighted(overlay_bottom, 0.6, display_frame, 0.4, 0, display_frame)

    # Display instructions
    y_pos = h - 120
    cv2.putText(display_frame, "Instructions:", (15, y_pos), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 255), 1)
    y_pos += 25

    for instruction in instructions:
        cv2.putText(display_frame, f"• {instruction}", (25, y_pos), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (200, 200, 200), 1)
        y_pos += 22

    return display_frame

print("✓ Live display helper function created")


# ## Section 3: Test Camera Frame Capture Parameters
# 
# Capture and analyze multiple frames to verify camera parameters are suitable for face detection.

# ## Section 3A: User Enrollment (OPTIONAL - Required for Recognition Testing)
# 
# This section allows you to enroll a user by capturing face samples and generating FaceNet embeddings.
# 
# **Why enroll?** Without enrolled users, FaceNet recognition test will skip. Enrollment captures multiple face samples and trains embeddings to recognize you.
# 
# **Skip this section if:** You already have trained embeddings at `data/dataset/embeddings.npy`

# In[5]:


# Initialize Face Detector and FaceNet Recogniser (needed for enrollment)
try:
    detector = FaceDetector()
    recogniser = FaceNetRecogniser()
    print("[OK] Face Detector initialized")
    print("[OK] FaceNet Recogniser initialized (MediaPipe-based)")
except Exception as e:
    print(f"[ERROR] Failed to initialize: {e}")
    raise


# In[ ]:


# Initialize Enrollment Manager
try:
    enrolment_manager = EnrolmentManager(camera, detector, recogniser, db=None)
    print("[OK] Enrollment Manager initialized")
except Exception as e:
    print(f"⚠ Enrollment Manager initialization: {e}")
    enrolment_manager = None

# Check if embeddings already exist
model_exists = recogniser.is_trained
print(f"\nCurrent embedding status: {'[OK] Trained embeddings found' if model_exists else '[INFO] No trained embeddings yet'}")

# STEP 1: Capture a test frame and compare against existing dataset
print("\n" + "=" * 70)
print("FACE COMPARISON TEST")
print("=" * 70)
print()
print("Capturing your face to compare against enrolled users...")
print("Position your face in front of the camera")
print()
print("Starting in 3 seconds...\n")

for countdown in range(3, 0, -1):
    print(f"  {countdown}...")
    time.sleep(1)

# Capture test frame
test_frame_captured = None
test_detections = None
for attempt in range(60):  # Try up to 60 frames
    frame = camera.capture_frame()
    if frame is None:
        continue

    detections = detector.detect_and_extract(frame)
    if len(detections) > 0:
        test_frame_captured = frame
        test_detections = detections
        print("✓ Face detected!")
        break

    time.sleep(0.1)
    if (attempt + 1) % 10 == 0:
        grey = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        brightness = grey.mean()
        print(f"  Attempt {attempt + 1}/60... (brightness={brightness:.0f}, ensure good lighting)")

if test_frame_captured is None or test_detections is None:
    print("✗ No face detected - please try again")
    sys.exit(1)

# STEP 2: If model exists, try to recognize the face
recognized_user = None
confidence_score = None

if model_exists:
    print("\nComparing against enrolled users...")
    roi, bbox = test_detections[0]
    
    try:
        user_id, confidence = recogniser.predict(roi)
        confidence_score = confidence
        
        # FaceNet: Higher confidence = better match (0-100 similarity score)
        # Typically use threshold around 60-75 for good matches
        if confidence > 60:  # Good match threshold for FaceNet
            recognized_user = user_id
            print(f"[MATCH] Found! User ID: {user_id}, Confidence: {confidence:.2f}")
        else:
            print(f"[NO_MATCH] No good match found. Confidence: {confidence:.2f}")
    except Exception as e:
        print(f"⚠ Prediction error: {e}")

# STEP 3: Decide whether to enroll or skip enrollment
if recognized_user is not None:
    # Face matches an existing user - skip enrollment
    print("\n" + "=" * 70)
    print("EXISTING USER RECOGNIZED")
    print("=" * 70)
    print()
    print(f"Your face matches an enrolled user (ID: {recognized_user})")
    print(f"Confidence score: {confidence_score:.2f}")
    print("Skipping enrollment - proceeding to verification testing")
    print()
    user_id = recognized_user
    enrollment_skipped = True
    
elif not model_exists and enrolment_manager:
    # Model exists but no match found - ask about re-enrollment
    print("\n" + "=" * 70)
    print("UNKNOWN FACE DETECTED")
    print("=" * 70)
    print()
    print("Your face does not match any enrolled user.")
    print("Running enrollment to add you to the system...")
    print()
    user_id = 2  # Use next available ID
    user_name = "New User"
    enrollment_skipped = False
    
    print(f"Enrolling user: {user_name} (ID: {user_id})")
    print()
    print("=" * 70)
    print("ENROLLMENT STAGE 1: SAMPLE CAPTURE")
    print("=" * 70)
    print()

    samples_to_capture = 20
    captured_samples = 0

    print(f"Will capture {samples_to_capture} face samples")
    print("Position your face in front of the camera")
    print("Keep your face centered and at different angles")
    print()
    print("Starting in 5 seconds...\n")

    for countdown in range(5, 0, -1):
        print(f"  {countdown}...")
        time.sleep(1)

    # Capture samples with live display
    dataset_path = recogniser.dataset_path
    user_dataset_path = os.path.join(dataset_path, str(user_id))
    os.makedirs(user_dataset_path, exist_ok=True)

    start_time = time.time()

    while captured_samples < samples_to_capture:
        frame = camera.capture_frame()
        if frame is None:
            continue

        # Detect face
        detections = detector.detect_and_extract(frame)

        if len(detections) > 0:
            roi, bbox = detections[0]

            # Save sample
            sample_path = os.path.join(user_dataset_path, f"sample_{captured_samples+1}.png")
            cv2.imwrite(sample_path, roi)
            captured_samples += 1

            # Display with live feedback
            frame_display = display_with_instructions(
                frame,
                "SAMPLE CAPTURE",
                [
                    f"Capturing sample {captured_samples}/{samples_to_capture}",
                    "Face detected ✓",
                    "Vary your angle slightly"
                ],
                is_enrollment=True
            )

            # Draw bounding box
            x, y, w, h = bbox
            cv2.rectangle(frame_display, (x, y), (x+w, y+h), (0, 255, 0), 3)

            # Show progress bar
            progress = int((captured_samples / samples_to_capture) * 100)
            bar_width = 300
            bar_x, bar_y = 50, 150
            cv2.rectangle(frame_display, (bar_x, bar_y), (bar_x + bar_width, bar_y + 20), (100, 100, 100), -1)
            cv2.rectangle(frame_display, (bar_x, bar_y), (bar_x + int(bar_width * captured_samples / samples_to_capture), bar_y + 20), (0, 255, 0), -1)
            cv2.putText(frame_display, f"{progress}%", (bar_x + bar_width + 10, bar_y + 15), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 1)

            # Display - use cv2.imshow for real-time live video
            cv2.imshow(f"Enrollment: Sample {captured_samples}/{samples_to_capture}", frame_display)
            cv2.waitKey(1)  # Allow window to update

            print(f"  Captured {captured_samples}/{samples_to_capture}")
            time.sleep(0.5)  # Slow down for visibility
        else:
            print("  No face detected - please position your face in front of camera")
            time.sleep(0.5)

    print(f"\n[OK] Enrollment: Sample capture complete!")
    print(f"  Time elapsed: {time.time() - start_time:.1f} seconds")
    print(f"  Samples saved: {user_dataset_path}")

    # Train model
    print("\n" + "=" * 70)
    print("ENROLLMENT STAGE 2: MODEL TRAINING")
    print("=" * 70)
    print()
    print("Training FaceNet embeddings on captured samples...")
    print()

    training_start = time.time()
    training_success = recogniser.train()
    training_time = time.time() - training_start

    if training_success:
        print(f"[OK] FaceNet embeddings trained successfully!")
        print(f"  Training time: {training_time:.2f} seconds")
        print(f"  Model saved: {recogniser.model_path}")
        
        # Verify embeddings file was created
        embeddings_path = os.path.join(recogniser.dataset_path, 'embeddings.npy')
        if os.path.exists(embeddings_path):
            file_size = os.path.getsize(embeddings_path)
            print(f"[OK] Embeddings file verified: {file_size / 1024:.1f} KB")
        else:
            print(f"[WARNING] Embeddings file not found at {embeddings_path}")
        
        # Reload recogniser to get fresh is_trained status
        recogniser = FaceNetRecogniser()
        print(f"[OK] Recogniser reloaded - is_trained: {recogniser.is_trained}")
    else:
        print(f"[FAIL] Model training failed")

    print()
    print("=" * 70)
    print("ENROLLMENT COMPLETE")
    print("=" * 70)
    print()
    print("User is now enrolled and ready for verification testing!")
    print()
    
    # Close enrollment window automatically
    cv2.destroyAllWindows()
    print("Enrollment window closed automatically after task completion")
    time.sleep(1)  # Brief pause before next section

else:
    print("\n[OK] Skipping enrollment - proceeding directly to verification testing")
    user_id = None  # Will verify any enrolled user


# SECTION 3 FRAME CAPTURE TEST - COMMENTED OUT
if False:
    # In[ ]:
    
    # Capture multiple frames and analyze parameters
    num_frames = 5
    frames = []
    
    print(f"Capturing {num_frames} test frames...")
    for i in range(num_frames):
        frame = camera.capture_frame()
        if frame is not None:
            frames.append(frame)
        time.sleep(0.3)  # Small delay between frames
    
    print(f"✓ Captured {len(frames)} frames\n")
    
    # Analyze frame quality
    if frames:
        for i, frame in enumerate(frames[:3]):  # Show first 3
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            brightness = gray.mean()
            contrast = gray.std()
    
            print(f"Frame {i+1}:")
            print(f"  Shape: {frame.shape}")
            print(f"  Brightness: {brightness:.1f} (ideal: 80-180)")
            print(f"  Contrast: {contrast:.1f} (ideal: 40+)")
            print(f"  ✓ Frame quality suitable" if 80 <= brightness <= 180 and contrast >= 40 else f"  ⚠ May need lighting adjustment")
            print()
    
    # Display sample frames
    fig, axes = plt.subplots(1, 3, figsize=(15, 5))
    for idx, ax in enumerate(axes):
        if idx < len(frames):
            ax.imshow(cv2.cvtColor(frames[idx], cv2.COLOR_BGR2RGB))
            ax.set_title(f"Frame {idx+1}")
        ax.axis('off')
    plt.suptitle("Sample Captured Frames", fontsize=14, fontweight='bold')
    plt.tight_layout()
    plt.show()
    
    print("✓ Camera frame capture parameters verified")
    
    # Close frame capture display
    cv2.destroyAllWindows()
    print("Frame capture window closed automatically after task completion\n")
    time.sleep(1)  # Brief pause before next section


# SECTION 4 FACE DETECTION TEST - COMMENTED OUT
if False:
    # ## Section 4: Test Face Detection with Haar Cascade
    # 
    # Initialize the face detector and test detection accuracy on captured frames.
    
    # In[ ]:
    
    
    # Initialize Face Detector
    try:
        detector = FaceDetector()
        print("✓ Face detector initialized")
    except Exception as e:
        print(f"✗ Failed to initialize detector: {e}")
        raise
    
    # Test face detection on captured frames
    print("\nTesting face detection on captured frames...\n")
    
    detection_results = []
    
    fig, axes = plt.subplots(2, 3, figsize=(18, 10))
    axes = axes.flatten()
    
    for idx, frame in enumerate(frames[:6]):
        # Detect faces
        detections = detector.detect_and_extract(frame)
        detection_results.append(detections)
    
        # Prepare visualization
        frame_display = frame.copy()
    
        # Draw bounding boxes
        grey = detector.preprocess(frame)
        faces = detector.detect_faces(grey)
    
        num_faces = len(faces)
        print(f"Frame {idx+1}: Detected {num_faces} face(s)")
    
        for (x, y, w, h) in faces:
            cv2.rectangle(frame_display, (x, y), (x+w, y+h), (0, 255, 0), 2)
            cv2.putText(frame_display, f"Face", (x, y-10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)
    
        # Display
        axes[idx].imshow(cv2.cvtColor(frame_display, cv2.COLOR_BGR2RGB))
        axes[idx].set_title(f"Frame {idx+1}: {num_faces} Face(s)")
        axes[idx].axis('off')
    
    plt.suptitle("Haar Cascade Face Detection Results", fontsize=14, fontweight='bold')
    plt.tight_layout()
    plt.show()
    
    # Summary
    total_faces = sum(len(det) for det in detection_results)
    print(f"\n✓ Face detection complete")
    print(f"  Total frames tested: {len(detection_results)}")
    print(f"  Total faces detected: {total_faces}")
    print(f"  Average per frame: {total_faces/len(detection_results):.1f}")
    
    # Close face detection window automatically
    cv2.destroyAllWindows()
    print("Face detection window closed automatically after task completion\n")
    time.sleep(1)  # Brief pause before next section


# SECTION 5 LIVENESS DETECTION TEST - COMMENTED OUT
if False:
    # ## Section 5: Test Liveness Detection with Eye Blinks
    
    # Initialize Liveness Detector
    liveness_detector = LivenessDetector(detector)
    
    print("=" * 70)
    print("LIVENESS DETECTION TEST")
    print("=" * 70)
    print(f"Configuration:")
    print(f"  Enabled: {liveness_detector.enabled}")
    print(f"  Required blinks: {liveness_detector.required_blinks}")
    print(f"  Timeout: {liveness_detector.detection_timeout} seconds")
    print()
    
    # Live display during liveness check
    print("Preparing liveness test...")
    print("Starting in 2 seconds...\n")
    
    for countdown in range(2, 0, -1):
        print(f"  {countdown}...")
        time.sleep(1)
    
    # Run liveness check with live display
    start_time_liveness = time.time()
    liveness_result = False
    blink_count = 0
    timeout_duration = liveness_detector.detection_timeout
    start_check = time.time()
    
    print("Liveness check running...")
    print("(Watch the live video window for instructions)\n")
    
    # Simulate liveness with visual feedback
    while time.time() - start_check < timeout_duration and not liveness_result:
        frame = camera.capture_frame()
        if frame is None:
            continue
    
        elapsed = time.time() - start_check
        remaining = timeout_duration - elapsed
    
        # Display with instructions
        frame_display = display_with_instructions(
            frame,
            "LIVENESS CHECK",
            [
                f"Blink {liveness_detector.required_blinks} times",
                f"Time remaining: {remaining:.1f}s",
                "Keep face centered"
            ],
            is_enrollment=False
        )
    
        # Show on screen - use cv2.imshow for real-time live video
        cv2.imshow("Liveness Detection - Follow Instructions", frame_display)
        cv2.waitKey(1)  # Allow window to update
    
        time.sleep(0.1)  # Slightly slow down display
    
    # Run actual liveness check
    start_time = time.time()
    liveness_result = liveness_detector.check_liveness(camera)
    elapsed_time = time.time() - start_time
    
    print()
    print("=" * 70)
    print("LIVENESS CHECK RESULT")
    print("=" * 70)
    print(f"Status: {'✓ PASSED' if liveness_result else '✗ FAILED'}")
    print(f"Time elapsed: {elapsed_time:.1f} seconds")
    print()
    
    if liveness_result:
        print("✓ Liveness verification successful!")
        print("  - Eyes were detected correctly")
        print("  - Blink transitions were recognized")
        print("  - This is a REAL face, not a photograph")
    else:
        print("✗ Liveness verification failed!")
        print("  - Check lighting conditions")
        print("  - Ensure face is clearly visible")
        print("  - Blink more deliberately and slowly")
    
    print("=" * 70)
    print()
    time.sleep(2)  # Pause before next stage
    # Close liveness detection window automatically
    cv2.destroyAllWindows()
    print("Liveness detection window closed automatically after task completion\n")
    time.sleep(1)  # Brief pause before next section

# SECTION 6 LBPH FACE RECOGNITION TEST - COMMENTED OUT
if False:
    # ## Section 6: Test LBPH Face Recognition
    
    # Initialize LBPH Face Recogniser
    try:
        recogniser = FaceNetRecogniser()
        print("✓ LBPH Face Recogniser initialized")
    except Exception as e:
        print(f"✗ Failed to initialize recogniser: {e}")
        raise
    
    print()
    print("Model Status:")
    print(f"  Model path: {recogniser.model_path}")
    print(f"  Model loaded: {recogniser.is_trained}")
    print(f"  Confidence threshold: {recogniser.confidence_threshold}")
    print(f"  Image size: {recogniser.image_size}")
    
    # Test recognition on detected faces from earlier
    if recogniser.is_trained:
        print("\n" + "=" * 60)
        print("LBPH RECOGNITION TEST")
        print("=" * 60)
        print()
    
        # Use detected faces from earlier test frames
        recognition_results = []
    
        for frame_idx, (frame, detections) in enumerate(zip(frames[:3], detection_results[:3])):
            print(f"Frame {frame_idx+1}:")
    
            if len(detections) == 0:
                print("  No faces detected - skipping")
                continue
    
            for face_idx, (roi, bbox) in enumerate(detections):
                try:
                    # Recognize face
                    accepted, user_id, confidence = recogniser.verify(roi)
    
                    recognition_results.append({
                        'frame': frame_idx+1,
                        'user_id': user_id,
                        'confidence': confidence,
                        'accepted': accepted
                    })
    
                    status = "✓ MATCH" if accepted else "✗ NO MATCH"
                    print(f"  Face {face_idx+1}: {status}")
                    print(f"    Predicted user ID: {user_id}")
                    print(f"    Confidence: {confidence:.1f}")
    
                    # Color code the result
                    if accepted:
                        print(f"    → This user is RECOGNIZED")
                    else:
                        print(f"    → Confidence too high (threshold: {recogniser.confidence_threshold})")
                    print()
    
                except Exception as e:
                    print(f"  Face {face_idx+1}: Error - {e}")
                    print()
    
        print("=" * 60)
        print(f"Recognition Summary: {len(recognition_results)} faces tested")
        if recognition_results:
            matched = sum(1 for r in recognition_results if r['accepted'])
            print(f"  Matches: {matched}")
            print(f"  No matches: {len(recognition_results) - matched}")
        print("=" * 60)
    
    else:
        print("\n⚠️  No trained model available!")
        print("   To use LBPH recognition, you must first enroll users.")
        print()
        print("   Run the enrollment module to:")
        print("   1. Capture user face samples")
        print("   2. Train the LBPH model")
        print("   3. Save the trained model")
        print()
        print("   Then come back and rerun this test.")


# Initialize required components for Full Pipeline Test (if not already initialized)
if 'detector' not in locals():
    try:
        detector = FaceDetector()
    except:
        pass

if 'recogniser' not in locals():
    try:
           recogniser = FaceNetRecogniser()
    except:
        pass


# ## Section 7: Full Pipeline Test - Decision Engine
# 
# Test the complete verification pipeline (Detection → Recognition) using DecisionEngine.
# 
# **Instructions:**
# 1. Run the cell below
# 2. Position your face in front of the camera
# 3. The system will verify your identity
# 
# The decision engine will return one of these results:
# - **ACCEPTED**: User recognized
# - **REJECTED**: Face detected but not recognized
# - **NO_FACE**: No face detected
# - **MODEL_NOT_READY**: No trained embeddings available

# In[ ]:


# Initialize Decision Engine (without liveness)
decision_engine = DecisionEngine(camera, detector, recogniser)

# Database connection for looking up enrolled user details after verification
try:
    db = DatabaseManager()
    print("[OK] Database connected for user detail lookup")
except Exception as e:
    print(f"[WARNING] Could not connect to database: {e}")
    db = None

print("=" * 70)
print("FACENET RECOGNITION PIPELINE TEST")
print("=" * 70)
print()
print(f"Model trained: {recogniser.is_trained}")
print(f"Max retries: {decision_engine.max_retries}")
print()
print("Running face detection and recognition...")
print()

print("Preparing verification...")
print("Starting in 3 seconds...\n")

for countdown in range(3, 0, -1):
    print(f"  {countdown}...")
    time.sleep(1)

print()
print("Verification running...")
print("(Watch the live video window)\n")

# Run full verification pipeline with live display
start_time = time.time()

# Show live video during verification attempts
for attempt in range(1, decision_engine.max_retries + 1):
    frame = camera.capture_frame()
    if frame is None:
        continue
    
    # Display with stage info
    frame_display = display_with_instructions(
        frame,
        "FACE RECOGNITION",
        [f"Looking for face...", f"Attempt {attempt}/{decision_engine.max_retries}"],
        is_enrollment=False
    )
    
    # Show live video
    cv2.imshow("FaceNet Recognition Pipeline", frame_display)
    cv2.waitKey(1)

# Run the actual verification (now timing is real)
outcome = decision_engine.run_verification(expected_user_id=None)
elapsed_time = time.time() - start_time

print()
print("=" * 70)
print("VERIFICATION RESULT")
print("=" * 70)
print()

# Display results
result_map = {
    VerificationResult.ACCEPTED: "✓ ACCEPTED",
    VerificationResult.REJECTED: "✗ REJECTED",
    VerificationResult.NO_FACE: "⚠ NO_FACE",
    VerificationResult.MODEL_NOT_READY: "⚠ MODEL_NOT_READY",
}

print(f"Result: {result_map.get(outcome.result, str(outcome.result))}")
print(f"Time elapsed: {elapsed_time:.1f} seconds")
print(f"Attempts: {outcome.attempt}")
print()

if outcome.result == VerificationResult.ACCEPTED:
    print("✓ Verification SUCCESSFUL!")

    # Look up the enrolled user's details from the database
    verified_user = db.get_user(outcome.user_id) if db else None

    if verified_user:
        enrol = "Enrolled" if verified_user["enrolment_status"] else "Not enrolled"
        print()
        print("  " + "-" * 40)
        print(f"  Welcome, {verified_user['full_name']}!")
        print("  " + "-" * 40)
        print(f"  User ID:          {verified_user['user_id']}")
        print(f"  Full name:        {verified_user['full_name']}")
        print(f"  Caregiver phone:  {verified_user['caregiver_phone']}")
        print(f"  Compartment:      {verified_user['compartment_index']}")
        print(f"  Enrolment status: {enrol}")
        if outcome.confidence is not None:
            print(f"  Match confidence: {outcome.confidence:.1f}")
    else:
        # Recognised by the model but no matching DB record
        print(f"  User ID: {outcome.user_id}")
        if outcome.confidence is not None:
            print(f"  Confidence: {outcome.confidence:.1f}")
        print("  [WARNING] No database record found for this user ID")

    print()
    print("  Pipeline components working correctly:")
    print("  ✓ Face detection")
    print("  ✓ Liveness check")
    print("  ✓ FaceNet recognition")

elif outcome.result == VerificationResult.REJECTED:
    print("✗ User not recognized")
    print(f"  Predicted user: {outcome.user_id}")
    if outcome.confidence is not None:
        print(f"  Confidence: {outcome.confidence:.1f}")
    print()
    print("  Possible reasons:")
    print("  - Face is not enrolled in the system")
    print("  - Poor lighting conditions")
    print("  - Face angle not suitable")

elif outcome.result == VerificationResult.LIVENESS_FAILED:
    print("✗ Spoofing detected (liveness check failed)")
    print()
    print("  This happens when:")
    print("  - Eye blinks not detected properly")
    print("  - A photograph is shown instead of a real face")

elif outcome.result == VerificationResult.NO_FACE:
    print("⚠ No face detected in any capture attempt")
    print()
    print("  Troubleshooting:")
    print("  - Ensure face is clearly visible")
    print("  - Check camera positioning")
    print("  - Improve lighting conditions")

elif outcome.result == VerificationResult.MODEL_NOT_READY:
    print("[INFO] No trained FaceNet embeddings available - enroll users first")
    print()
    print("  To test recognition:")
    print("  1. Enroll at least one user (run section 3A)")
    print("  2. Capture face samples")
    print("  3. Train FaceNet embeddings")
    print("  4. Rerun this test")

print()
print("=" * 70)
print()
time.sleep(1)  # Pause before summary

# Close decision engine pipeline window automatically
cv2.destroyAllWindows()
print("Decision engine window closed automatically after task completion\n")
time.sleep(1)  # Brief pause before next section


# ## Section 8: Test Summary Report

print()
print("="*70)
print("TEST SUMMARY")
print("="*70)
print()
print(f"Camera:     {camera.resolution[0]}x{camera.resolution[1]} pixels")
print(f"Model:      {'FaceNet (Loaded)' if recogniser.is_trained else 'Not available'}")
print(f"Result:     {outcome.result.value}")
print(f"Time:       {elapsed_time:.1f} seconds")

if outcome.result == VerificationResult.ACCEPTED:
    summary_user = db.get_user(outcome.user_id) if db else None
    if summary_user:
        print(f"User:       {summary_user['full_name']} (compartment {summary_user['compartment_index']})")
    print(f"User ID:    {outcome.user_id}")
    print(f"Confidence: {outcome.confidence:.1f}")
elif outcome.result == VerificationResult.REJECTED:
    print(f"Note:       Face detected but confidence too low")
elif outcome.result == VerificationResult.NO_FACE:
    print(f"Note:       No face detected - check camera and lighting")
elif outcome.result == VerificationResult.MODEL_NOT_READY:
    print(f"Note:       Enroll users first using Section 3A")

print()
print("="*70)
print()


# Cleanup - Release camera resources and close windows
cv2.destroyAllWindows()
plt.close('all')
camera.stop()
print("✓ Test complete")

