#!/usr/bin/env bash
set -e

echo "================================================================="
echo "  Web2Apk v1.0 — By Mohsin Khawaja"
echo "  \"Get rid of paid web to apk tools\""
echo "================================================================="
echo ""

# 1. Check for Python
if ! command -v python3 &> /dev/null; then
    echo "[ERROR] Python 3 was not found in your system PATH!"
    echo "Please install Python 3.10 or higher."
    exit 1
fi

# 2. Check and install Python dependencies
if ! python3 -c "import flask, PIL" &> /dev/null; then
    echo "[*] Installing required Python packages..."
    python3 -m pip install -r requirements.txt
    echo "[*] Dependencies installed successfully."
    echo ""
fi

# 3. Launch Web2Apk Web Console
echo "[*] Launching Web2Apk Web Console..."
python3 main.py
