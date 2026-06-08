#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
OS="$(uname -s)"

echo "========================================"
echo "  🚀 Dotfiles Bootstrap (Stage 1)"
echo "========================================"
echo ""

# macOS: Xcode Command Line Tools + Homebrew + python3
if [[ "$OS" == "Darwin" ]]; then
  if ! xcode-select -p &>/dev/null; then
    echo "🍎 Installing Xcode Command Line Tools..."
    xcode-select --install
  fi

  if ! command -v brew &>/dev/null; then
    echo "🍺 Installing Homebrew..."
    /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
  fi
  brew update
  brew install python@3 curl unzip stow

# Linux / WSL: ensure python3 + base packages
elif [[ "$OS" == "Linux" ]]; then
  missing_pkgs=()
  for pkg in python3 curl unzip stow; do
    command -v "$pkg" &>/dev/null || missing_pkgs+=("$pkg")
  done

  # Ensure en_US.UTF-8 locale (common issue on minimal WSL installs)
  if command -v locale-gen &>/dev/null; then
    locale -a 2>/dev/null | grep -qi en_US.UTF-8 || sudo locale-gen en_US.UTF-8
  fi

  # Ensure pip3 is available (needed by tools like Ruff via Mason)
  if ! command -v pip3 &>/dev/null; then
    if command -v apt &>/dev/null; then
      sudo apt install -y python3-pip
    elif command -v pacman &>/dev/null; then
      sudo pacman -Syu --noconfirm python-pip
    elif command -v dnf &>/dev/null; then
      sudo dnf install -y python3-pip
    fi
  fi

  if [ ${#missing_pkgs[@]} -gt 0 ]; then
    if command -v apt &>/dev/null; then
      sudo apt update
      sudo apt install -y "${missing_pkgs[@]}"
    elif command -v pacman &>/dev/null; then
      sudo pacman -Syu --noconfirm "${missing_pkgs[@]}"
    elif command -v dnf &>/dev/null; then
      sudo dnf install -y "${missing_pkgs[@]}"
    else
      echo "⚠️  No package manager found. Install manually: ${missing_pkgs[*]}"
      exit 1
    fi
  fi
fi

echo ""
echo "✅ Stage 1 complete. Handing off to Python..."
echo ""

exec python3 "$SCRIPT_DIR/2_management.py" install "$@"
