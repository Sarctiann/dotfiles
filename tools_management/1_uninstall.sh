#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
OS="$(uname -s)"

echo "========================================"
echo "  🗑  Dotfiles Uninstall"
echo "========================================"
echo ""

# macOS: ensure python3
if [[ "$OS" == "Darwin" ]]; then
  if ! command -v python3 &>/dev/null; then
    echo "🍎 Installing Xcode Command Line Tools..."
    xcode-select --install
  fi

# Linux / WSL: ensure python3
elif [[ "$OS" == "Linux" ]]; then
  if ! command -v python3 &>/dev/null; then
    if command -v apt &>/dev/null; then
      sudo apt update && sudo apt install -y python3
    elif command -v pacman &>/dev/null; then
      sudo pacman -Syu --noconfirm python3
    elif command -v dnf &>/dev/null; then
      sudo dnf install -y python3
    else
      echo "⚠️  No package manager found. Install python3 manually."
      exit 1
    fi
  fi
fi

echo ""
exec python3 "$SCRIPT_DIR/2_management.py" uninstall "$@"
