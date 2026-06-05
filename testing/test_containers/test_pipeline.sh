#!/bin/bash
set -euo pipefail

PIPELINE_DIR=$(mktemp -d)
trap 'rm -rf "$PIPELINE_DIR"' EXIT

IS_WSL=false
[[ -n "${DOTFILES_WSL:-}" ]] && IS_WSL=true

echo "========================================="
echo "  🧪 Dotfiles Install/Uninstall Pipeline"
echo "========================================="
echo ""

# === Stage 0: Create preexisting files ===
echo "═══ Stage 0: Create preexisting files ═══"

mkdir -p "$HOME/.local/bin"
cat >"$HOME/.local/bin/preexisting-fake" <<'PRETOOL'
#!/bin/bash
echo "preexisting"
PRETOOL
chmod +x "$HOME/.local/bin/preexisting-fake"
echo "   ✓ Created preexisting CLI tool: preexisting-fake"

mkdir -p "$HOME/.config/ghostty"
echo "# preexisting ghostty config" >"$HOME/.config/ghostty/config"
GHOSTTY_MD5=$(md5sum "$HOME/.config/ghostty/config" | cut -d' ' -f1)
echo "   ✓ Created preexisting ghostty/config"

mkdir -p "$HOME/.config/bat"
echo "# preexisting bat config" >"$HOME/.config/bat/config"
BAT_MD5=$(md5sum "$HOME/.config/bat/config" | cut -d' ' -f1)
echo "   ✓ Created preexisting bat/config"

PRETOOL_MD5=$(md5sum "$HOME/.local/bin/preexisting-fake" | cut -d' ' -f1)
echo "   ✓ Recorded checksums"

# Git env vars (needed by the "Git config" install step)
export GIT_NAME="Test User"
export GIT_EMAIL="test@example.com"
export COMPANY_GIT_NAME="Test Work"
export COMPANY_GIT_EMAIL="test@work.com"
export COMPANY_DIR="$HOME/work"
echo "   ✓ Set git env vars for install step"

# === Stage 1: Install ===
echo ""
echo "═══ Stage 1: Install dotfiles ═══"

cd /dotfiles
bash ./install.sh 2>&1 | tee "$PIPELINE_DIR/install.log"
if [ ${PIPESTATUS[0]} -ne 0 ]; then
    echo "❌ Install failed (exit ${PIPESTATUS[0]})"
    exit 1
fi
echo "   ✓ Install completed"

# Install added tools to ~/.local/bin — ensure it's in PATH
export PATH="$HOME/.local/bin:$PATH"

# === Stage 2: Verify install ===
echo ""
echo "═══ Stage 2: Verify install ═══"

FAILED=0

if [ ! -f "$HOME/.local/share/dotfiles/manifest.json" ]; then
    echo "❌ Manifest not found after install"
    FAILED=1
else
    echo "   ✓ Manifest created"
fi

python3 - "$IS_WSL" <<PYEOF
import json, sys
is_wsl = sys.argv[1] == "true"
m = json.load(open("$HOME/.local/share/dotfiles/manifest.json"))
installed = m["cli_tools"]["installed"]
for tool in ["neovim", "ripgrep", "fd", "bat"]:
    assert tool in installed, f"{tool} not in installed list"
print("   ✓ Manifest tracks installed CLI tools")
assert m["stow"]["backups"], "no stow backups recorded"
print("   ✓ Manifest tracks stow packages and backups")
if not is_wsl:
    assert "ghostty" in m["stow"]["packages"], "ghostty not in stow packages"
    print("   ✓ ghostty in stow packages")
PYEOF
PYRC=$?
if [ $PYRC -ne 0 ]; then FAILED=1; fi

for cmd in nvim rg fd bat tmux stow; do
    if command -v "$cmd" &>/dev/null; then
        echo "   ✓ $cmd installed"
    else
        echo "❌ $cmd not found after install"
        FAILED=1
    fi
done

if command -v preexisting-fake &>/dev/null; then
    echo "   ✓ Preexisting tool still present"
else
    echo "❌ Preexisting tool disappeared"
    FAILED=1
fi

if $IS_WSL; then
    echo "   ⚠  Skipping ghostty symlink check (WSL)"
elif [ -L "$HOME/.config/ghostty/config" ]; then
    echo "   ✓ ghostty/config symlinked"
else
    echo "❌ ghostty/config not a symlink"
    FAILED=1
fi

if [ -L "$HOME/.config/bat/config" ]; then
    echo "   ✓ bat/config symlinked"
else
    echo "❌ bat/config not a symlink"
    FAILED=1
fi

BACKUP_DIR="$HOME/.local/share/dotfiles/backups"
if $IS_WSL; then
    echo "   ⚠  Skipping ghostty backup check (WSL)"
elif [ -f "$BACKUP_DIR/ghostty/.config/ghostty/config" ]; then
    echo "   ✓ ghostty backup exists"
else
    echo "❌ ghostty backup missing"
    FAILED=1
fi
if [ -f "$BACKUP_DIR/bat/.config/bat/config" ]; then
    echo "   ✓ bat backup exists"
else
    echo "❌ bat backup missing"
    FAILED=1
fi

# Git config verification
if [ -f "$HOME/.gitconfig" ] && [ ! -L "$HOME/.gitconfig" ]; then
    echo "   ✓ ~/.gitconfig is a regular file (not a stow symlink)"
    if grep -q "Test User" "$HOME/.gitconfig" && grep -q "test@example.com" "$HOME/.gitconfig"; then
        echo "   ✓ ~/.gitconfig has correct git identity"
    else
        echo "❌ ~/.gitconfig missing expected identity"
        FAILED=1
    fi
else
    echo "❌ ~/.gitconfig missing or still a symlink"
    FAILED=1
fi
if [ -f "$HOME/.gitconfig-work" ]; then
    echo "   ✓ ~/.gitconfig-work generated"
else
    echo "❌ ~/.gitconfig-work missing"
    FAILED=1
fi

if [ $FAILED -ne 0 ]; then
    echo "❌ Install verification failed"
    exit 1
fi
echo "   ✅ Install verified"

# === Stage 3: Uninstall ===
echo ""
echo "═══ Stage 3: Uninstall dotfiles ═══"

cd /dotfiles
bash ./uninstall.sh -f 2>&1 | tee "$PIPELINE_DIR/uninstall.log"
if [ ${PIPESTATUS[0]} -ne 0 ]; then
    echo "❌ Uninstall failed (exit ${PIPESTATUS[0]})"
    exit 1
fi
echo "   ✓ Uninstall completed"

# === Stage 4: Verify uninstall ===
echo ""
echo "═══ Stage 4: Verify uninstall ═══"

FAILED=0

if [ -f "$HOME/.local/share/dotfiles/manifest.json" ]; then
    echo "❌ Manifest still exists after uninstall"
    FAILED=1
else
    echo "   ✓ Manifest removed"
fi

# Preexisting ghostty config restored
if $IS_WSL; then
    echo "   ⚠  Skipping ghostty restore check (WSL)"
elif [ -f "$HOME/.config/ghostty/config" ] && [ ! -L "$HOME/.config/ghostty/config" ]; then
    NEW_MD5=$(md5sum "$HOME/.config/ghostty/config" | cut -d' ' -f1)
    if [ "$NEW_MD5" = "$GHOSTTY_MD5" ]; then
        echo "   ✓ ghostty/config restored with original content"
    else
        echo "❌ ghostty/config checksum mismatch: expected $GHOSTTY_MD5 got $NEW_MD5"
        FAILED=1
    fi
else
    echo "❌ ghostty/config missing or still a symlink"
    FAILED=1
fi

# Preexisting bat config restored
if [ -f "$HOME/.config/bat/config" ] && [ ! -L "$HOME/.config/bat/config" ]; then
    NEW_MD5=$(md5sum "$HOME/.config/bat/config" | cut -d' ' -f1)
    if [ "$NEW_MD5" = "$BAT_MD5" ]; then
        echo "   ✓ bat/config restored with original content"
    else
        echo "❌ bat/config checksum mismatch: expected $BAT_MD5 got $NEW_MD5"
        FAILED=1
    fi
else
    echo "❌ bat/config missing or still a symlink"
    FAILED=1
fi

# Preexisting tool preserved
if command -v preexisting-fake &>/dev/null; then
    NEW_MD5=$(md5sum "$HOME/.local/bin/preexisting-fake" | cut -d' ' -f1)
    if [ "$NEW_MD5" = "$PRETOOL_MD5" ]; then
        echo "   ✓ Preexisting tool preserved"
    else
        echo "❌ Preexisting tool content changed"
        FAILED=1
    fi
else
    echo "❌ Preexisting tool removed but should have been preserved"
    FAILED=1
fi

# GitHub-release-installed tools removed
for cmd in nvim rg fd bat; do
    if command -v "$cmd" &>/dev/null; then
        echo "   ⚠  $cmd still in PATH (checking binary location)"
        LOCATION=$(command -v "$cmd")
        if echo "$LOCATION" | grep -q "$HOME/.local/bin"; then
            echo "❌ $cmd still at $LOCATION after uninstall"
            FAILED=1
        else
            echo "   ✓ $cmd is system-installed (not our binary)"
        fi
    else
        echo "   ✓ $cmd removed"
    fi
done

if [ -d "$BACKUP_DIR" ] && [ -n "$(ls -A "$BACKUP_DIR" 2>/dev/null)" ]; then
    echo "   ⚠  Backup directory not empty"
else
    echo "   ✓ Backup directory cleaned or empty"
fi

if [ $FAILED -ne 0 ]; then
    echo "❌ Uninstall verification failed"
    exit 1
fi
echo "   ✅ Uninstall verified"

echo ""
echo "========================================="
echo "  ✅ All pipeline tests passed"
echo "========================================="
exit 0
