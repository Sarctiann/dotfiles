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
  # Detect package manager
  if command -v apt &>/dev/null; then
    pm="apt"
  elif command -v pacman &>/dev/null; then
    pm="pacman"
  elif command -v dnf &>/dev/null; then
    pm="dnf"
  else
    echo "⚠️  No supported package manager found. Install manually: python3 curl unzip stow python3-pip"
    exit 1
  fi

  # Update package repositories before installing anything
  echo "🔄 Updating package repositories..."
  case "$pm" in
    apt) sudo apt update ;;
    pacman) sudo pacman -Syu --noconfirm ;;
    dnf) sudo dnf update -y ;;
  esac

  # Ensure en_US.UTF-8 locale (common issue on minimal WSL installs)
  if command -v locale-gen &>/dev/null; then
    locale -a 2>/dev/null | grep -qi en_US.UTF-8 || sudo locale-gen en_US.UTF-8
  fi

  # Install all required packages
  echo "📦 Installing packages..."
  case "$pm" in
    apt) sudo apt install -y python3 curl unzip stow python3-pip ;;
    pacman) sudo pacman -Syu --noconfirm python3 curl unzip stow python-pip ;;
    dnf) sudo dnf install -y python3 curl unzip stow python3-pip ;;
  esac
fi

echo ""
echo "✅ Stage 1 complete. Handing off to Python..."
echo ""

exec python3 "$SCRIPT_DIR/2_management.py" install "$@"
