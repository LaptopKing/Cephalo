#!/usr/bin/env bash
# ==============================================================================
# Cephalo - Clean & Reversible Uninstaller (Linux / macOS / WSL)
# ==============================================================================
# Safely removes Cephalo managed blocks from shell configurations and restores
# previous agent configurations without touching any user-created files.
# ==============================================================================

set -e

echo ""
echo "=========================================================="
echo "  🧹 Cephalo Clean Uninstaller / Revert Utility"
echo "=========================================================="
echo ""

read -r -p "Are you sure you want to revert Cephalo integrations from your environment? [y/N]: " confirm
if [[ ! "$confirm" =~ ^[yY] ]]; then
    echo "Uninstallation cancelled."
    exit 0
fi

remove_managed_block() {
    local target_file="$1"
    local tag="$2"
    local comment_style="${3:-#}"

    if [ ! -f "$target_file" ]; then
        return
    fi

    local start_tag end_tag
    if [ "$comment_style" = "<!--" ]; then
        start_tag="<!-- ${tag} START -->"
        end_tag="<!-- ${tag} END -->"
    else
        start_tag="# >>> ${tag} >>>"
        end_tag="# <<< ${tag} <<<"
    fi

    if grep -qF "$start_tag" "$target_file"; then
        python3 -c "
import sys, re
path = sys.argv[1]
start = sys.argv[2]
end = sys.argv[3]
with open(path, 'r', encoding='utf-8') as f:
    text = f.read()
pattern = re.escape(start) + r'.*?' + re.escape(end) + r'\n?'
text = re.sub(pattern, '', text, flags=re.DOTALL)
with open(path, 'w', encoding='utf-8') as f:
    f.write(text.rstrip() + '\n')
" "$target_file" "$start_tag" "$end_tag"
        echo "  [✓] Removed Cephalo managed block from $target_file"
    fi
}

remove_json_key() {
    local target_file="$1"
    local key_path="$2"

    if [ ! -f "$target_file" ]; then
        return
    fi

    python3 -c "
import sys, json, os
path = sys.argv[1]
key = sys.argv[2]
try:
    with open(path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    if key == 'mcpServers.cephalo':
        if 'mcpServers' in data and 'cephalo' in data['mcpServers']:
            del data['mcpServers']['cephalo']
    elif key == 'hooks.cephalo':
        if 'cephalo-autonomous-brain' in data:
            del data['cephalo-autonomous-brain']
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2)
    print(f'  [✓] Cleaned {key} from {path}')
except Exception:
    pass
" "$target_file" "$key_path"
}

# 1. Shell configs
remove_managed_block "$HOME/.bashrc" "cephalo initialize" "#"
remove_managed_block "$HOME/.zshrc" "cephalo initialize" "#"
remove_managed_block "$HOME/.config/fish/config.fish" "cephalo initialize" "#"

# 2. Symlinks
for bin_sym in "$HOME/.local/bin/cephalo" "$HOME/.gemini/antigravity-cli/bin/cephalo" "$HOME/.gemini/antigravity/bin/cephalo"; do
    if [ -L "$bin_sym" ]; then
        rm -f "$bin_sym"
        echo "  [✓] Removed symlink $bin_sym"
    fi
done

# 3. Antigravity plugin & configs
remove_json_key "$HOME/.gemini/config/mcp_config.json" "mcpServers.cephalo"
remove_json_key "$HOME/.gemini/config/hooks.json" "hooks.cephalo"

if [ -d "$HOME/.gemini/config/plugins/cephalo" ]; then
    rm -rf "$HOME/.gemini/config/plugins/cephalo"
    echo "  [✓] Removed Antigravity plugin at ~/.gemini/config/plugins/cephalo"
fi

# 4. Claude Code
remove_managed_block "$HOME/.claude/CLAUDE.md" "Cephalo Sovereign Memory Integration" "<!--"

# 5. Cursor & Windsurf
remove_json_key "$HOME/.cursor/mcp.json" "mcpServers.cephalo"
remove_json_key "$HOME/.codeium/windsurf/mcp_config.json" "mcpServers.cephalo"

echo ""
echo "=========================================================="
echo "  [+] Cephalo Reverted Cleanly with Zero Residual Impact."
echo "      (Your Cephalo memory data remains untouched at $PWD/data)"
echo "=========================================================="
