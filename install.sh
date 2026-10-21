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
BIN_DIR="$HOME/.local/bin"
mkdir -p "$BIN_DIR"
ln -sf "$TARGET_DIR/cephalo" "$BIN_DIR/cephalo"

# 6. Automatic Agent Harness Integration (Google Antigravity)
echo "[5/6] Configuring Agent Harness integrations..."
if [ -d "$HOME/.gemini" ]; then
    AGY_RULES="$HOME/.gemini/config/rules"
    mkdir -p "$AGY_RULES"
    
    if [ -f "$TARGET_DIR/integrations/antigravity/cephalo_second_brain.md" ]; then
        sed "s|{{CEPHALO_DIR}}|$TARGET_DIR|g" "$TARGET_DIR/integrations/antigravity/cephalo_second_brain.md" > "$AGY_RULES/cephalo_second_brain.md"
    else
        cat << EOF > "$AGY_RULES/cephalo_second_brain.md"
# Cephalo Second Brain & Autonomous Memory Policy

## Core Invariant: Omnipresent Second Brain
The user has an omnipresent, local-first Second Brain called **Cephalo** located at:
\`$TARGET_DIR\`

Cephalo is the user's permanent long-term memory core across **ALL sessions (new and existing)**. The AI agent must never restart from scratch or repeatedly ask the user for information, preferences, hardware setups, or background that are already recorded in Cephalo.

---

## 1. Grounding in User Profile & Verified Hardware
Before answering questions concerning past decisions, preferences, device configurations, or domain-specific workflows:
1. Always ground your reasoning in Cephalo:
   - Consult the profile blueprint: \`$TARGET_DIR/USER_PROFILE.md\`
   - Or run the hybrid vector search CLI: \`cephalo search "<query>" --json\`
2. Follow the user's communication style and language preferences specified in \`USER_PROFILE.md\`.

---

## 2. Automated Continuous Learning (Record)
Whenever the user:
- Expresses a new preference, desire, or interest
- Introduces or configures a new device, tool, or hardware
- Makes an architectural, coding, or technical decision
- Shares a project idea or workflow rule

The agent **must automatically persist it**:
1. Record into Cephalo vector database:
   \`cephalo record "<decision_or_preference>" --category "<category>" --source "agent"\`
2. If it affects core user identity, hardware, or global principles, update:
   \`$TARGET_DIR/USER_PROFILE.md\`

---

## 3. Continuous GitHub Synchronization
If Cephalo is version-controlled via Git, all modifications, feature additions, and documentation improvements made to the repository must be committed and pushed:
\`\`\`bash
cd "$TARGET_DIR"
git add .
git commit -m "<Clear, descriptive commit message>"
git push
\`\`\`
EOF
    fi
    echo "      Configured Antigravity global rule at: $AGY_RULES/cephalo_second_brain.md"
fi

# 7. Verify Installation
echo "[6/6] Initializing Cephalo..."
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
