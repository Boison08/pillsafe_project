#!/usr/bin/env bash
# ============================================================
# PillSafe — Download MobileFaceNet TFLite Model
# ============================================================
#
# Downloads a pretrained MobileFaceNet model converted to
# TensorFlow Lite format for use with PillSafe's facial
# recognition pipeline.
#
# Usage:
#   bash scripts/download_model.sh
#
# The model will be saved to: data/models/mobilefacenet.tflite
#
# Model details:
#   - Architecture: MobileFaceNet (ArcFace-trained)
#   - Input: 112×112×3 RGB, float32, normalized to [-1, 1]
#   - Output: 192-dim embedding (L2-normalized)
#   - Size: ~5 MB
#   - Source: Google's MediaPipe face embedding model
#
# Alternative models (if you prefer a different source):
#   - InsightFace MobileFaceNet: https://github.com/deepinsight/insightface
#   - ONNX → TFLite conversion of any ArcFace model
#
# ============================================================

set -euo pipefail

MODEL_DIR="data/models"
MODEL_PATH="$MODEL_DIR/mobilefacenet.tflite"

# MediaPipe face embedder (FaceNet-style, optimised for mobile/edge)
# This is Google's official lightweight face embedding model.
MODEL_URL="https://storage.googleapis.com/mediapipe-models/face_embedder/face_embedder/float32/latest/face_embedder.tflite"

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo ""
echo "============================================================"
echo "  PillSafe — MobileFaceNet Model Download"
echo "============================================================"
echo ""

# Create directory
mkdir -p "$MODEL_DIR"

# Check if model already exists
if [ -f "$MODEL_PATH" ]; then
    echo -e "${YELLOW}[!]${NC} Model already exists at: $MODEL_PATH"
    echo "    To re-download, delete it first: rm $MODEL_PATH"
    echo ""
    exit 0
fi

# Download
echo "Downloading MobileFaceNet TFLite model..."
echo "  Source: $MODEL_URL"
echo "  Target: $MODEL_PATH"
echo ""

if command -v wget &> /dev/null; then
    wget -q --show-progress -O "$MODEL_PATH" "$MODEL_URL"
elif command -v curl &> /dev/null; then
    curl -L --progress-bar -o "$MODEL_PATH" "$MODEL_URL"
else
    echo "Error: neither wget nor curl is available."
    echo "Install with: sudo apt install wget"
    exit 1
fi

# Verify
if [ -f "$MODEL_PATH" ]; then
    SIZE=$(du -h "$MODEL_PATH" | cut -f1)
    echo ""
    echo -e "${GREEN}[✓]${NC} Model downloaded successfully"
    echo "    Path: $MODEL_PATH"
    echo "    Size: $SIZE"
    echo ""
    echo "  You can now run PillSafe with FaceNet recognition:"
    echo "    python3 main.py"
    echo ""
else
    echo "Error: Download failed."
    exit 1
fi
