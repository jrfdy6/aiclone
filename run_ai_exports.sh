#!/bin/bash
# Wrapper script to run process_ai_exports.py with environment variables

EXPORT_DIR="${EXPORT_DIR:-$HOME/Downloads/AI_exports}"
OUT_DIR="${OUT_DIR:-$HOME/Downloads/notebooklm_ready}"
MAX_WORDS="${MAX_WORDS:-450000}"
MAX_MB="${MAX_MB:-5}"

# Install ijson if not already installed
python3 -m pip install --user -q ijson

# Run the script with environment variables
EXPORT_DIR="$EXPORT_DIR" \
OUT_DIR="$OUT_DIR" \
MAX_WORDS="$MAX_WORDS" \
MAX_MB="$MAX_MB" \
python3 "$(dirname "$0")/process_ai_exports.py"
