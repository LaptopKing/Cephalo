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
    echo "[1/6] Cloning Cephalo repository..."
    git clone https://github.com/LaptopKing/Cephalo.git "$TARGET_DIR"
else
    echo "[1/6] Using Cephalo at $TARGET_DIR"
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

echo "[2/6] Installing dependencies..."
$PY_CMD -m pip install --quiet --upgrade pip
$PY_CMD -m pip install --quiet -r "$TARGET_DIR/requirements.txt"

# 4. Install Chromium for Playwright
echo "[3/6] Setting up Chromium crawler engine..."
$PY_CMD -m playwright install chromium

# 5. Link executable into user bin
echo "[4/6] Configuring 'cephalo' CLI command..."
chmod +x "$TARGET_DIR/cephalo"
chmod +x "$TARGET_DIR/auto_harvest.py"
BIN_DIR="$HOME/.local/bin"
mkdir -p "$BIN_DIR"
ln -sf "$TARGET_DIR/cephalo" "$BIN_DIR/cephalo"

# 6. Automatic Multi-Harness Agent Integrations
echo "[5/6] Configuring Multi-Harness Agent integrations..."

# A. Google Antigravity Integration (Rules + Hooks)
if [ -d "$HOME/.gemini" ]; then
    AGY_RULES="$HOME/.gemini/config/rules"
    mkdir -p "$AGY_RULES"
    
    if [ -f "$TARGET_DIR/integrations/antigravity/cephalo_second_brain.md" ]; then
        sed "s|{{CEPHALO_DIR}}|$TARGET_DIR|g" "$TARGET_DIR/integrations/antigravity/cephalo_second_brain.md" > "$AGY_RULES/cephalo_second_brain.md"
    fi
    echo "      Configured Antigravity global rule: $AGY_RULES/cephalo_second_brain.md"

    # Lifecycle Hooks configuration
    AGY_CONFIG="$HOME/.gemini/config"
    cat << EOF > "$AGY_CONFIG/hooks.json"
{
  "cephalo-autonomous-brain": {
    "enabled": true,
    "PreInvocation": [
      {
        "type": "command",
        "command": "$TARGET_DIR/auto_harvest.py --pre-invocation",
        "timeout": 15
      }
    ],
    "Stop": [
      {
        "type": "command",
        "command": "$TARGET_DIR/auto_harvest.py --stop-hook",
        "timeout": 15
      }
    ]
  }
}
EOF
    echo "      Configured Antigravity autonomous lifecycle hooks: $AGY_CONFIG/hooks.json"
fi

# B. Claude Code Integration
if [ -d "$HOME/.claude" ]; then
    cp "$TARGET_DIR/CLAUDE.md" "$HOME/.claude/CLAUDE.md"
    echo "      Configured Claude Code global policy: $HOME/.claude/CLAUDE.md"
fi

# C. Universal Agent Specification (AGENTS.md)
if [ ! -f "$HOME/AGENTS.md" ]; then
    cp "$TARGET_DIR/AGENTS.md" "$HOME/AGENTS.md"
    echo "      Configured Universal AGENTS.md at: $HOME/AGENTS.md"
fi

# 7. Verify Installation
echo "[6/6] Initializing Cephalo..."
$PY_CMD "$TARGET_DIR/brain.py" status

echo ""
echo "=========================================================="
echo "  [+] Cephalo Installed & Configured Across Agent Harnesses!"
echo "=========================================================="
echo "Autonomous Features Active:"
echo "  • All user prompts automatically audited and logged."
echo "  • Token-efficient dynamic context injection (silent on new topics)."
echo "  • Antigravity PreInvocation & Stop lifecycle hooks enabled."
echo "  • Multi-harness support (Antigravity, Claude Code, Cursor, Codex)."
echo ""
echo "You can now run 'cephalo' from any terminal:"
echo "  cephalo status           # Check memory & database health"
echo "  cephalo search <query>   # Query Cephalo with hybrid search"
echo "  cephalo harvest          # Audit past conversation transcripts"
echo "  cephalo record <text>    # Store a memory with zero-leak privacy"
echo ""
