#!/usr/bin/env bash
# ==============================================================================
# Cephalo - 1-Command Automated Installer (Linux / macOS)
# ==============================================================================

set -e

echo ""
echo "   ____ _____ ____  _   _    _    _     ___  "
echo "  / ___| ____|  _ \| | | |  / \  | |   / _ \ "
echo " | |   |  _| | |_) | |_| | / _ \ | |  | | | |"
echo " | |___| |___|  __/|  _  |/ ___ \| |__| |_| |"
echo "  \____|_____|_|   |_| |_/_/   \_\_____\___/ "
echo ""
echo "  >> Sovereign Local Memory & Cognitive Coprocessor <<"
echo ""

# 1. Determine Target Directory
if [ -f "brain.py" ]; then
    TARGET_DIR="$(pwd)"
else
    TARGET_DIR="$HOME/.cephalo"
fi

# 2. Clone if not present
if [ ! -f "$TARGET_DIR/brain.py" ]; then
    echo "[1/5] Cloning Cephalo repository..."
    git clone https://github.com/LaptopKing/Cephalo.git "$TARGET_DIR"
else
    echo "[1/5] Using Cephalo at $TARGET_DIR"
fi

# 3. Locate Python
if command -v python3 &> /dev/null; then
    PY_CMD="python3"
elif command -v python &> /dev/null; then
    PY_CMD="python"
else
    echo "Error: Python 3.10+ is required."
    exit 1
fi

echo "[2/5] Installing dependencies..."
$PY_CMD -m pip install --quiet --upgrade pip
$PY_CMD -m pip install --quiet -r "$TARGET_DIR/requirements.txt"

# 4. Install Chromium for Playwright
echo "[3/5] Setting up Chromium crawler engine..."
$PY_CMD -m playwright install chromium

# 5. Link executable into user bin
echo "[4/5] Configuring 'cephalo' CLI command..."
chmod +x "$TARGET_DIR/cephalo"
BIN_DIR="$HOME/.local/bin"
mkdir -p "$BIN_DIR"
ln -sf "$TARGET_DIR/cephalo" "$BIN_DIR/cephalo"

# 6. Verify Installation
echo "[5/5] Initializing Cephalo..."
$PY_CMD "$TARGET_DIR/brain.py" status

echo ""
echo "=========================================================="
echo "  [+] Cephalo Installed Successfully!"
echo "=========================================================="
echo "You can now run 'cephalo' from any terminal:"
echo "  cephalo status           # Check memory & database health"
echo "  cephalo search <query>   # Query Cephalo with hybrid search"
echo "  cephalo web <query>      # Live web research"
echo "  cephalo record <text>    # Store a memory with zero-leak privacy"
echo ""
