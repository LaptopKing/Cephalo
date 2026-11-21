#!/usr/bin/env bash
# ==============================================================================
# Cephalo - Adaptive Non-Destructive Installer (Linux / macOS / WSL)
# ==============================================================================
# Invariant: Cephalo adapts and integrates cleanly into existing environments.
# Never blindly overwrites existing user configurations, dotfiles, or global rules.
# ==============================================================================

set -e

USE_VENV=1
ENABLE_MCP=1
for arg in "$@"; do
    case "$arg" in
        --venv)
            USE_VENV=1
            ;;
        --system-python|--no-venv)
            USE_VENV=0
            ;;
        --no-mcp)
            ENABLE_MCP=0
            ;;
        --help|-h)
            echo "Cephalo Adaptive Installer (Linux/macOS/WSL)"
            echo "Usage: ./install.sh [--venv | --system-python] [--no-mcp]"
            echo "  --venv           Create and install into an isolated virtual environment (.venv) [DEFAULT]"
            echo "  --system-python  Install directly into system Python"
            echo "  --no-mcp         Skip MCP server registration across agent harnesses"
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
    local comment_style="${4:-}"

    if [ -z "$comment_style" ]; then
        case "$target_file" in
            *.md|*.markdown|*.html|*.xml)
                comment_style="<!--"
                ;;
            *)
                comment_style="#"
                ;;
        esac
    fi

    local start_tag end_tag
    if [ "$comment_style" = "<!--" ]; then
        start_tag="<!-- ${block_tag} START -->"
        end_tag="<!-- ${block_tag} END -->"
    else
        start_tag="# >>> ${block_tag} >>>"
        end_tag="# <<< ${block_tag} <<<"
    fi

    mkdir -p "$(dirname "$target_file")"
    if [ -f "$target_file" ]; then
        local timestamp
        timestamp="$(date +%Y%m%d%H%M%S)"
        cp "$target_file" "${target_file}.bak.${timestamp}"
        
        # Check if block exists (supporting both current and legacy XML comment tags)
        python3 -c "
import sys, re
path = sys.argv[1]
start = sys.argv[2]
end = sys.argv[3]
content = sys.argv[4]
tag = sys.argv[5]

with open(path, 'r', encoding='utf-8') as f:
    text = f.read()

legacy_start = f'<!-- {tag} START -->'
legacy_end = f'<!-- {tag} END -->'

# Remove legacy tags if present
if legacy_start in text:
    pattern_leg = re.escape(legacy_start) + r'.*?' + re.escape(legacy_end) + r'\n?'
    text = re.sub(pattern_leg, '', text, flags=re.DOTALL)

pattern = re.escape(start) + r'.*?' + re.escape(end)
replacement = start + '\n' + content + '\n' + end

if re.search(pattern, text, flags=re.DOTALL):
    text = re.sub(pattern, replacement, text, flags=re.DOTALL)
else:
    sep = '\n\n' if text and not text.endswith('\n\n') else '\n'
    text = text.rstrip() + sep + replacement + '\n'

with open(path, 'w', encoding='utf-8') as f:
    f.write(text)
" "$target_file" "$start_tag" "$end_tag" "$block_content" "$block_tag"
        echo "      Updated Cephalo block in $target_file (backup: ${target_file}.bak.${timestamp})"
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
    except Exception as e:
        print(f"Warning: Failed to parse existing JSON in {path}: {e}. Preserved backup and skipped merge.", file=sys.stderr)
        sys.exit(0)

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

# Helper: Safely merge MCP server configuration non-destructively
merge_mcp_config() {
    local mcp_file="$1"
    local py_cmd="$2"
    local mcp_server="$3"
    local src_dir="$4"

    mkdir -p "$(dirname "$mcp_file")"
    if [ -f "$mcp_file" ]; then
        local timestamp
        timestamp="$(date +%Y%m%d%H%M%S)"
        cp "$mcp_file" "${mcp_file}.bak.${timestamp}"
    fi

    python3 -c "
import sys, json, os

path = sys.argv[1]
py_exe = sys.argv[2]
server = sys.argv[3]
src = sys.argv[4]

data = {'mcpServers': {}}
if os.path.exists(path):
    try:
        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except Exception as e:
        print(f"Warning: Failed to parse existing JSON in {path}: {e}. Preserved backup and skipped merge.", file=sys.stderr)
        sys.exit(0)

if 'mcpServers' not in data:
    data['mcpServers'] = {}

data['mcpServers']['cephalo'] = {
    'command': py_exe,
    'args': [server],
    'env': {
        'PYTHONPATH': src,
        'PYTHONIOENCODING': 'utf-8'
    }
}

with open(path, 'w', encoding='utf-8') as f:
    json.dump(data, f, indent=2)
" "$mcp_file" "$py_cmd" "$mcp_server" "$src_dir"
}

# 1. Determine Target Directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
if [ -f "$SCRIPT_DIR/brain.py" ]; then
    TARGET_DIR="$SCRIPT_DIR"
elif [ -f "$SCRIPT_DIR/../brain.py" ]; then
    TARGET_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
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

# 5. Link executable into user bin & configure shell environments
echo "[4/7] Configuring 'cephalo' CLI command & Shell Environments (non-destructive)..."
chmod +x "$TARGET_DIR/bin/cephalo"
chmod +x "$TARGET_DIR/src/cephalo/learning/auto_harvest.py"
chmod +x "$TARGET_DIR/scripts/release.sh"
chmod +x "$TARGET_DIR/scripts/uninstall.sh"
BIN_DIR="$HOME/.local/bin"
mkdir -p "$BIN_DIR"
ln -sf "$TARGET_DIR/bin/cephalo" "$BIN_DIR/cephalo"
if [ -d "$HOME/.gemini/antigravity-cli/bin" ]; then
    ln -sf "$TARGET_DIR/bin/cephalo" "$HOME/.gemini/antigravity-cli/bin/cephalo"
fi
if [ -d "$HOME/.gemini/antigravity/bin" ]; then
    ln -sf "$TARGET_DIR/bin/cephalo" "$HOME/.gemini/antigravity/bin/cephalo"
fi

# Shell managed blocks integration (Bash, Zsh, Fish)
SHELL_BLOCK="# Cephalo Sovereign Memory CLI & Environment
export CEPHALO_DIR=\"$TARGET_DIR\"
if [[ \":\$PATH:\" != *\":\$CEPHALO_DIR/bin:\"* ]]; then
    export PATH=\"\$CEPHALO_DIR/bin:\$PATH\"
fi"

if [ -f "$HOME/.bashrc" ]; then
    merge_managed_block "$HOME/.bashrc" "$SHELL_BLOCK" "cephalo initialize"
fi
if [ -f "$HOME/.zshrc" ]; then
    merge_managed_block "$HOME/.zshrc" "$SHELL_BLOCK" "cephalo initialize"
fi
if [ -f "$HOME/.config/fish/config.fish" ]; then
    FISH_BLOCK="# Cephalo Sovereign Memory CLI & Environment
set -gx CEPHALO_DIR \"$TARGET_DIR\"
if not contains \"\$CEPHALO_DIR/bin\" \$PATH
    set -gx PATH \"\$CEPHALO_DIR/bin\" \$PATH
end"
    merge_managed_block "$HOME/.config/fish/config.fish" "$FISH_BLOCK" "cephalo initialize"
fi

# 6. Adaptive Multi-Harness Agent Integrations
echo "[5/7] Configuring Multi-Harness Agent integrations (non-destructive)..."

# A. Google Antigravity Integration
if [ -d "$HOME/.gemini" ]; then
    AGY_PLUGIN="$HOME/.gemini/config/plugins/cephalo"
    mkdir -p "$AGY_PLUGIN/rules" "$AGY_PLUGIN/skills/cephalo" "$HOME/.gemini/config/skills/cephalo" "$HOME/.gemini/config/rules"

    # Plugin Manifest
    cat << EOF > "$AGY_PLUGIN/plugin.json"
{
  "name": "cephalo",
  "description": "Cephalo Omnipresent Autonomous Second Brain and Personal Memory Engine",
  "version": "2.1.0"
}
EOF

    # Skills & Rules
    if [ -f "$TARGET_DIR/integrations/antigravity/SKILL.md" ]; then
        cp "$TARGET_DIR/integrations/antigravity/SKILL.md" "$AGY_PLUGIN/skills/cephalo/SKILL.md"
        # Clean up global copy if present to prevent duplicate skill discovery
        rm -rf "$HOME/.gemini/config/skills/cephalo" 2>/dev/null || true
    fi

    if [ -f "$TARGET_DIR/integrations/antigravity/cephalo_second_brain.md" ]; then
        sed "s|{{CEPHALO_DIR}}|$TARGET_DIR|g" "$TARGET_DIR/integrations/antigravity/cephalo_second_brain.md" > "$AGY_PLUGIN/rules/AGENTS.md"
        # Avoid duplicate rule loading inside plugin (AGENTS.md alone is discovered by Antigravity)
        rm -f "$AGY_PLUGIN/rules/GEMINI.md" 2>/dev/null || true
        # Clean up legacy global rules to eliminate duplicate prompt injection (~3,000 tokens/turn saved)
        rm -f "$HOME/.gemini/config/rules/cephalo_second_brain.md" 2>/dev/null || true
        # Clean up ~/.gemini/AGENTS.md and GEMINI.md if they only duplicate Cephalo rules
        python3 -c "
import os
for fname in ('AGENTS.md', 'GEMINI.md'):
    p = os.path.expanduser(f'~/.gemini/{fname}')
    if os.path.exists(p):
        with open(p, 'r', encoding='utf-8') as f:
            txt = f.read()
        if 'Cephalo' in txt and 'USER_PROFILE.md' in txt:
            os.remove(p)
" 2>/dev/null || true
    fi

    # Hooks configuration: Strictly register in plugin only; prune from global hooks to prevent 2x execution
    merge_hooks_json "$AGY_PLUGIN/hooks.json" "$PY_CMD" "$TARGET_DIR/src/cephalo/learning/auto_harvest.py"
    if [ -f "$HOME/.gemini/config/hooks.json" ]; then
        python3 -c "
import json, os
p = os.path.expanduser('~/.gemini/config/hooks.json')
try:
    with open(p, 'r', encoding='utf-8') as f:
        data = json.load(f)
    if 'cephalo-autonomous-brain' in data:
        del data['cephalo-autonomous-brain']
        with open(p, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2)
except Exception:
    pass
" 2>/dev/null || true
    fi

    # Native MCP Integration: Register globally so permissions match mcp(cephalo/...), prune plugin mcp to avoid cephalo_cephalo duplicate
    if [ "$ENABLE_MCP" -eq 1 ]; then
        merge_mcp_config "$HOME/.gemini/config/mcp_config.json" "$PY_CMD" "$TARGET_DIR/src/cephalo/services/mcp_server.py" "$TARGET_DIR/src"
        rm -f "$AGY_PLUGIN/mcp_config.json" 2>/dev/null || true
        echo "      Configured Cephalo stdio MCP server in Antigravity (deduplicated)."
    fi
fi

# B. Claude Code Integration (Clean MCP or Managed Block)
if [ -d "$HOME/.claude" ] || command -v claude &> /dev/null; then
    if [ "$ENABLE_MCP" -eq 1 ] && command -v claude &> /dev/null; then
        claude mcp add cephalo -- "$PY_CMD" "$TARGET_DIR/src/cephalo/services/mcp_server.py" 2>/dev/null || true
        echo "      Registered Cephalo MCP server cleanly via 'claude mcp add'."
    fi

    if [ -d "$HOME/.claude" ]; then
        CLAUDE_TARGET="$HOME/.claude/CLAUDE.md"
        CLAUDE_BLOCK="### Cephalo Sovereign Memory Integration
- **Root Directory:** $TARGET_DIR
- **Grounding Invariant:** Consult Cephalo before answering past preferences or decisions (\`cephalo search \"<query>\" --json\`).
- **Autonomous Capture:** Record preferences & decisions immediately (\`cephalo record \"<statement>\" --category \"<category>\"\`)."
        merge_managed_block "$CLAUDE_TARGET" "$CLAUDE_BLOCK" "Cephalo Sovereign Memory Integration" "<!--"
    fi
fi

# C. Multi-Editor MCP Integrations
if [ "$ENABLE_MCP" -eq 1 ]; then
    # Cursor IDE
    CURSOR_STORAGE="$HOME/.cursor/mcp.json"
    if [ -d "$HOME/.cursor" ]; then
        merge_mcp_config "$CURSOR_STORAGE" "$PY_CMD" "$TARGET_DIR/src/cephalo/services/mcp_server.py" "$TARGET_DIR/src"
        echo "      Configured Cephalo MCP server in Cursor."
    fi

    # Windsurf Cascade
    WINDSURF_CONFIG="$HOME/.codeium/windsurf/mcp_config.json"
    if [ -d "$HOME/.codeium/windsurf" ]; then
        merge_mcp_config "$WINDSURF_CONFIG" "$PY_CMD" "$TARGET_DIR/src/cephalo/services/mcp_server.py" "$TARGET_DIR/src"
        echo "      Configured Cephalo MCP server in Windsurf."
    fi

    # VS Code / Cline / Roo Code
    for cline_mcp in \
        "$HOME/.config/Code/User/globalStorage/saoudrizwan.claude-dev/settings/cline_mcp_settings.json" \
        "$HOME/.config/Code/User/globalStorage/rooveterinaryinc.roo-cline/settings/cline_mcp_settings.json"; do
        if [ -d "$(dirname "$cline_mcp")" ]; then
            merge_mcp_config "$cline_mcp" "$PY_CMD" "$TARGET_DIR/src/cephalo/services/mcp_server.py" "$TARGET_DIR/src"
            echo "      Configured Cephalo MCP server in VS Code Cline/Roo: $cline_mcp"
        fi
    done
fi

# F. Background Auto-Update Configuration
echo "      Configuring autonomous background update engine (zero flow disruption)..."
$PY_CMD "$TARGET_DIR/brain.py" update policy auto >/dev/null 2>&1 || true

# 7. Screen Memory & Visual Timeline Configuration
echo "[6/7] Configuring Desktop Screen Memory & Safeguards..."
echo ""
echo "=============================================================================="
echo "  📸 Optional Feature: Desktop Screen Memory & Visual Timeline"
echo "=============================================================================="
echo "  • How it operates:"
echo "    Periodically captures desktop keyframes on significant visual shifts,"
echo "    computes a 64-bit dHash perceptual difference (100% safe Rust, 0 unsafe),"
echo "    and enqueues background OCR to power the 24-hour DeepWiki visual timeline."
echo "  • Resource Profile:"
echo "    - CPU: ~15-20% CPU for ~2s only during background OCR jobs."
echo "    - Disk: ~50-80 KB WebP keyframe per unique screen state."
echo "    - Battery: Automatically throttles or pauses when battery < 20%."
echo "    - Privacy: Shielded against password managers, incognito, and banking sites."
echo "=============================================================================="

ENABLE_SCREEN=0
if [ "$CEPHALO_ENABLE_SCREEN" = "1" ]; then
    ENABLE_SCREEN=1
elif [ "$CEPHALO_ENABLE_SCREEN" = "0" ]; then
    ENABLE_SCREEN=0
elif [ -t 0 ]; then
    read -r -p "Would you like to enable continuous Desktop Screen Memory? [y/N] (Default: No): " screen_choice
    case "$screen_choice" in
        [yY][eE][sS]|[yY])
            ENABLE_SCREEN=1
            ;;
        *)
            ENABLE_SCREEN=0
            ;;
    esac
fi

if [ "$ENABLE_SCREEN" = "1" ]; then
    "$TARGET_DIR/bin/cephalo" screen enable
    echo "      Desktop Screen Memory enabled."
else
    "$TARGET_DIR/bin/cephalo" screen disable
    echo "      Desktop Screen Memory disabled (Zero-overhead mode). You can enable anytime via: cephalo screen enable"
fi

# 8. Verify Installation
echo "[7/7] Verifying Cephalo..."
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
