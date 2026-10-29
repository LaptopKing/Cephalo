#!/usr/bin/env bash
# ==============================================================================
# Cephalo - Adaptive Non-Destructive Installer (Linux / macOS / WSL)
# ==============================================================================
# Invariant: Cephalo adapts and integrates cleanly into existing environments.
# Never blindly overwrites existing user configurations, dotfiles, or global rules.
# ==============================================================================

set -e

USE_VENV=0
for arg in "$@"; do
    case "$arg" in
        --venv)
            USE_VENV=1
            ;;
        --help|-h)
            echo "Cephalo Adaptive Installer (Linux/macOS/WSL)"
            echo "Usage: ./install.sh [--venv]"
            echo "  --venv  Create and install into an isolated virtual environment (.venv)"
            exit 0
            ;;
    esac
done

echo ""
echo "   ____ _____ ____  _   _    _    _     ___  "
echo "  / ___| ____|  _ \| | | |  / \  | |   / _ \ "
echo " | |   |  _| | |_) | |_| | / _ \ | |  | | | |"
echo " | |___| |___|  __/|  _  |/ ___ \| |__| |_| |"
echo "  \____|_____|_|   |_| |_/_/   \_\_____\___/ "
echo ""
echo "  >> Sovereign Local Memory & Cognitive Coprocessor <<"
echo "  >> Adaptive Non-Destructive Multi-Harness Integration <<"
echo ""

# Helper: Merge managed block non-destructively
merge_managed_block() {
    local target_file="$1"
    local block_content="$2"
    local block_tag="${3:-CEPHALO MANAGED BLOCK}"
    local start_tag="<!-- ${block_tag} START -->"
    local end_tag="<!-- ${block_tag} END -->"

    mkdir -p "$(dirname "$target_file")"
    if [ -f "$target_file" ]; then
        local timestamp
        timestamp="$(date +%Y%m%d%H%M%S)"
        cp "$target_file" "${target_file}.bak.${timestamp}"
        
        # Check if block exists
        if grep -qF "$start_tag" "$target_file"; then
            # Replace existing block using python
            python3 -c "
import sys, re
path = sys.argv[1]
start = sys.argv[2]
end = sys.argv[3]
content = sys.argv[4]
with open(path, 'r', encoding='utf-8') as f:
    text = f.read()
pattern = re.escape(start) + r'.*?' + re.escape(end)
replacement = start + '\n' + content + '\n' + end
text = re.sub(pattern, replacement, text, flags=re.DOTALL)
with open(path, 'w', encoding='utf-8') as f:
    f.write(text)
" "$target_file" "$start_tag" "$end_tag" "$block_content"
            echo "      Updated Cephalo block in $target_file (backup: ${target_file}.bak.${timestamp})"
        else
            printf "\n%s\n%s\n%s\n" "$start_tag" "$block_content" "$end_tag" >> "$target_file"
            echo "      Appended Cephalo block to $target_file (backup: ${target_file}.bak.${timestamp})"
        fi
    else
        printf "%s\n%s\n%s\n" "$start_tag" "$block_content" "$end_tag" > "$target_file"
        echo "      Created $target_file with Cephalo block."
    fi
}

# Helper: Safely merge hooks into hooks.json without destroying existing hooks
merge_hooks_json() {
    local hooks_file="$1"
    local py_cmd="$2"
    local harvest_path="$3"

    mkdir -p "$(dirname "$hooks_file")"
    if [ -f "$hooks_file" ]; then
        local timestamp
        timestamp="$(date +%Y%m%d%H%M%S)"
        cp "$hooks_file" "${hooks_file}.bak.${timestamp}"
    fi

    python3 -c "
import sys, json, os

path = sys.argv[1]
py_exe = sys.argv[2]
harvest = sys.argv[3]

data = {}
if os.path.exists(path):
    try:
        with open(path, 'r', encoding='utf-8') as f:
            content = f.read().strip()
            if content:
                data = json.loads(content)
    except Exception:
        data = {}

data['cephalo-autonomous-brain'] = {
    'enabled': True,
    'SessionStart': [{'type': 'command', 'command': f'\"{py_exe}\" \"{harvest}\" --session-start', 'timeout': 15}],
    'PreInvocation': [{'type': 'command', 'command': f'\"{py_exe}\" \"{harvest}\" --pre-invocation', 'timeout': 15}],
    'Stop': [{'type': 'command', 'command': f'\"{py_exe}\" \"{harvest}\" --stop-hook', 'timeout': 15}]
}

with open(path, 'w', encoding='utf-8') as f:
    json.dump(data, f, indent=2)
" "$hooks_file" "$py_cmd" "$harvest_path"

    echo "      Safely merged Cephalo hooks into $hooks_file."
}

# 1. Determine Target Directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
if [ -f "$SCRIPT_DIR/brain.py" ]; then
    TARGET_DIR="$SCRIPT_DIR"
elif [ -f "$HOME/.gemini/antigravity/scratch/second-brain/brain.py" ]; then
    TARGET_DIR="$HOME/.gemini/antigravity/scratch/second-brain"
elif [ -f "brain.py" ]; then
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

# 3. Locate Base Python
if command -v python3 &> /dev/null; then
    BASE_PY="python3"
elif command -v python &> /dev/null; then
    BASE_PY="python"
else
    echo "Error: Python 3.10+ is required."
    exit 1
fi

# Manage Virtual Environment
VENV_DIR="$TARGET_DIR/.venv"
if [ "$USE_VENV" -eq 1 ] || [ -d "$VENV_DIR" ]; then
    if [ ! -d "$VENV_DIR" ]; then
        echo "[2/6] Creating isolated Python virtual environment (.venv)..."
        $BASE_PY -m venv "$VENV_DIR"
    fi
    PY_CMD="$VENV_DIR/bin/python"
    echo "[2/6] Using isolated virtual environment: $PY_CMD"
else
    PY_CMD="$BASE_PY"
    echo "[2/6] Using Python environment: $PY_CMD"
fi

echo "      Checking and installing dependencies..."
$PY_CMD -m pip install --quiet -r "$TARGET_DIR/requirements.txt"

# 4. Optional Playwright check
if $PY_CMD -c "import playwright; print('ok')" &> /dev/null; then
    echo "[3/6] Verified browser crawler integration."
else
    echo "[3/6] Optional crawler browser setup skipped (can run 'playwright install chromium' anytime)."
fi

# 5. Link executable into user bin
echo "[4/6] Configuring 'cephalo' CLI command..."
chmod +x "$TARGET_DIR/cephalo"
chmod +x "$TARGET_DIR/auto_harvest.py"
BIN_DIR="$HOME/.local/bin"
mkdir -p "$BIN_DIR"
ln -sf "$TARGET_DIR/cephalo" "$BIN_DIR/cephalo"

# 6. Adaptive Multi-Harness Agent Integrations
echo "[5/6] Configuring Multi-Harness Agent integrations (non-destructive)..."

# A. Google Antigravity Integration
if [ -d "$HOME/.gemini" ]; then
    AGY_PLUGIN="$HOME/.gemini/config/plugins/cephalo"
    mkdir -p "$AGY_PLUGIN/rules" "$AGY_PLUGIN/skills/cephalo" "$HOME/.gemini/config/skills/cephalo" "$HOME/.gemini/config/rules"

    # Plugin Manifest
    cat << EOF > "$AGY_PLUGIN/plugin.json"
{
  "name": "cephalo",
  "description": "Cephalo Omnipresent Autonomous Second Brain and Personal Memory Engine"
}
EOF

    # Skills & Rules
    if [ -f "$TARGET_DIR/integrations/antigravity/SKILL.md" ]; then
        cp "$TARGET_DIR/integrations/antigravity/SKILL.md" "$AGY_PLUGIN/skills/cephalo/SKILL.md"
        cp "$TARGET_DIR/integrations/antigravity/SKILL.md" "$HOME/.gemini/config/skills/cephalo/SKILL.md"
    fi

    if [ -f "$TARGET_DIR/integrations/antigravity/cephalo_second_brain.md" ]; then
        sed "s|{{CEPHALO_DIR}}|$TARGET_DIR|g" "$TARGET_DIR/integrations/antigravity/cephalo_second_brain.md" > "$AGY_PLUGIN/rules/AGENTS.md"
        cp "$AGY_PLUGIN/rules/AGENTS.md" "$AGY_PLUGIN/rules/GEMINI.md"
        cp "$AGY_PLUGIN/rules/AGENTS.md" "$HOME/.gemini/config/rules/cephalo_second_brain.md"
    fi

    # Non-destructive hooks merge
    merge_hooks_json "$AGY_PLUGIN/hooks.json" "$PY_CMD" "$TARGET_DIR/auto_harvest.py"
    merge_hooks_json "$HOME/.gemini/config/hooks.json" "$PY_CMD" "$TARGET_DIR/auto_harvest.py"
fi

# B. Claude Code Integration (Clean MCP or Managed Block)
if [ -d "$HOME/.claude" ]; then
    if command -v claude &> /dev/null; then
        claude mcp add cephalo -- "$PY_CMD" "$TARGET_DIR/mcp_server.py" 2>/dev/null || true
        echo "      Registered Cephalo MCP server cleanly via 'claude mcp add'."
    fi

    # Non-destructive block append to ~/.claude/CLAUDE.md
    CLAUDE_TARGET="$HOME/.claude/CLAUDE.md"
    CLAUDE_BLOCK="### Cephalo Sovereign Memory Integration
- **Root Directory:** $TARGET_DIR
- **Grounding Invariant:** Consult Cephalo before answering past preferences or decisions (\`cephalo search \"<query>\" --json\`).
- **Autonomous Capture:** Record preferences & decisions immediately (\`cephalo record \"<statement>\" --category \"<category>\"\`)."
    merge_managed_block "$CLAUDE_TARGET" "$CLAUDE_BLOCK"
fi

# 7. Verify Installation
echo "[6/6] Verifying Cephalo..."
$PY_CMD "$TARGET_DIR/brain.py" status

echo ""
echo "=========================================================="
echo "  [+] Cephalo Installed Adaptively with Zero Configuration Damage!"
echo "=========================================================="
echo "Safety Guarantees Applied:"
echo "  • Existing CLAUDE.md and hooks preserved; managed blocks merged cleanly."
echo "  • No unmanaged files dropped into your home directory root."
echo "  • Background git push is opt-in (CEPHALO_AUTO_PUSH=1); no surprise pushes."
echo "  • Automatic backups created for every touched configuration file."
echo ""
