#!/usr/bin/env bash
# ==============================================================================
# Cephalo - Automated Release Helper (scripts/release.sh)
# ==============================================================================
# Bumps version across pyproject.toml, Cargo.toml, and __init__.py,
# verifies test suites, creates an annotated git tag, and pushes to GitHub
# to trigger the automated GitHub Actions release workflow.
# ==============================================================================

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$SCRIPT_DIR"

if [ -n "$(git status --porcelain)" ]; then
    echo "[-] Error: Working tree has uncommitted modifications. Please stash or commit first:"
    git status -s
    exit 1
fi

BRANCH="$(git rev-parse --abbrev-ref HEAD)"
if [ "$BRANCH" != "main" ] && [ "$BRANCH" != "master" ]; then
    echo "[-] Warning: You are on branch '$BRANCH'. Releases should normally originate from 'main'."
    read -r -p "Continue anyway? [y/N]: " confirm_branch
    if [[ ! "$confirm_branch" =~ ^[yY] ]]; then
        exit 1
    fi
fi

# Detect current version
CURRENT_VERSION=$(python3 -c "import re; f=open('pyproject.toml').read(); print(re.search(r'version\s*=\s*[\"\\\']([^\"\\\']+)[\"\\\']', f).group(1))")
echo "=========================================================="
echo "  🚀 Cephalo Release Management Tool"
echo "=========================================================="
echo "  Current Version: $CURRENT_VERSION"
echo ""

TARGET="$1"
if [ -z "$TARGET" ]; then
    echo "Select release increment:"
    echo "  1) patch (e.g. 2.1.0 -> 2.1.1)"
    echo "  2) minor (e.g. 2.1.0 -> 2.2.0)"
    echo "  3) major (e.g. 2.1.0 -> 3.0.0)"
    echo "  4) custom version"
    read -r -p "Enter choice [1-4]: " choice
    case "$choice" in
        1) TARGET="patch" ;;
        2) TARGET="minor" ;;
        3) TARGET="major" ;;
        4)
            read -r -p "Enter custom semver version (e.g. 2.1.1): " TARGET
            ;;
        *)
            echo "Invalid option. Exiting."
            exit 1
            ;;
    esac
fi

# Compute new version
NEW_VERSION=$(python3 -c "
import sys, re

cur = '$CURRENT_VERSION'
target = '$TARGET'

parts = [int(p) for p in cur.split('.')]
while len(parts) < 3:
    parts.append(0)

if target == 'patch':
    parts[2] += 1
elif target == 'minor':
    parts[1] += 1
    parts[2] = 0
elif target == 'major':
    parts[0] += 1
    parts[1] = 0
    parts[2] = 0
else:
    # Custom version
    clean = re.sub(r'^[vV]', '', target.strip())
    parts = [int(p) for p in clean.split('.')]

print(f'{parts[0]}.{parts[1]}.{parts[2]}')
")

TAG="v$NEW_VERSION"
echo ""
echo "Target New Version: $NEW_VERSION (Tag: $TAG)"
read -r -p "Proceed with test verification and release? [y/N]: " confirm
if [[ ! "$confirm" =~ ^[yY] ]]; then
    echo "Release aborted."
    exit 0
fi

# 1. Update version in pyproject.toml
python3 -c "
import re
with open('pyproject.toml', 'r', encoding='utf-8') as f:
    text = f.read()
text = re.sub(r'version\s*=\s*[\"\\\'][^\"\\\']+[\"\\\']', 'version = \"$NEW_VERSION\"', text)
with open('pyproject.toml', 'w', encoding='utf-8') as f:
    f.write(text)
"

# 2. Update version in rust/Cargo.toml
if [ -f "rust/Cargo.toml" ]; then
    python3 -c "
import re
with open('rust/Cargo.toml', 'r', encoding='utf-8') as f:
    text = f.read()
text = re.sub(r'(name\s*=\s*\"cephalo\"\s*\nversion\s*=\s*\")[^\"]+(\")', r'\g<1>$NEW_VERSION\g<2>', text)
with open('rust/Cargo.toml', 'w', encoding='utf-8') as f:
    f.write(text)
"
fi

# 3. Update version in src/cephalo/__init__.py
if [ -f "src/cephalo/__init__.py" ]; then
    python3 -c "
import re
with open('src/cephalo/__init__.py', 'r', encoding='utf-8') as f:
    text = f.read()
text = re.sub(r'__version__\s*=\s*[\"\\\'][^\"\\\']+[\"\\\']', '__version__ = \"$NEW_VERSION\"', text)
with open('src/cephalo/__init__.py', 'w', encoding='utf-8') as f:
    f.write(text)
"
fi

echo "[1/4] Running core verification tests..."
if [ -d ".venv" ]; then
    .venv/bin/pytest tests -q
else
    pytest tests -q
fi

if command -v cargo &> /dev/null && [ -d "rust" ]; then
    (cd rust && cargo test -q)
fi
echo "[+] All tests passed!"

echo "[2/4] Committing release bump..."
git add pyproject.toml rust/Cargo.toml src/cephalo/__init__.py
git commit -m "chore(release): bump version to $TAG"

echo "[3/4] Creating git release tag $TAG..."
git tag -a "$TAG" -m "Cephalo Release $TAG"

echo "[4/4] Pushing branch and tag to GitHub..."
git push origin "$BRANCH"
git push origin "$TAG"

echo ""
echo "=========================================================="
echo "  🎉 Successfully released $TAG to GitHub!"
echo "=========================================================="
echo "  GitHub Actions is now compiling binaries and publishing"
echo "  the official release at: https://github.com/LaptopKing/Cephalo/releases/tag/$TAG"
echo "=========================================================="
