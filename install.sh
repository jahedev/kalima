#!/bin/bash
# Kalima — one-command installer & launcher for macOS
# Usage: bash <(curl -fsSL https://raw.githubusercontent.com/jahedev/kalima/main/install.sh)

set -e

REPO="https://github.com/jahedev/kalima.git"
INSTALL_DIR="$HOME/Library/Application Support/Kalima/source"

# ── Colours ──────────────────────────────────────────────────────────────────
B='\033[1m'; G='\033[0;32m'; Y='\033[1;33m'; R='\033[0;31m'; N='\033[0m'
step()  { echo -e "\n${B}▸ $1${N}"; }
ok()    { echo -e "${G}  ✓ $1${N}"; }
warn()  { echo -e "${Y}  ! $1${N}"; }
die()   { echo -e "${R}  ✗ $1${N}" >&2; exit 1; }

# ── Header ───────────────────────────────────────────────────────────────────
echo ""
echo -e "${B}  كلمة  Kalima — Arabic EPUB Reader${N}"
echo    "  ────────────────────────────────────"
echo    "  This script will install and launch Kalima."
echo    "  It may ask for your Mac password to install"
echo    "  Homebrew (a standard macOS package manager)."
echo ""

[[ "$(uname)" == "Darwin" ]] || die "This installer is for macOS only."

# ── Homebrew ─────────────────────────────────────────────────────────────────
step "Checking Homebrew"

if ! command -v brew &>/dev/null; then
    warn "Homebrew not found — installing it now (you may be asked for your password)…"
    /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
fi

# Ensure brew is on PATH (needed right after a fresh install)
if   [[ -x /opt/homebrew/bin/brew ]]; then   # Apple Silicon
    eval "$(/opt/homebrew/bin/brew shellenv)"
elif [[ -x /usr/local/bin/brew ]]; then       # Intel
    eval "$(/usr/local/bin/brew shellenv)"
fi

command -v brew &>/dev/null || die "Homebrew installation failed."
ok "Homebrew $(brew --version | head -1)"

# ── Python ───────────────────────────────────────────────────────────────────
step "Checking Python"

if ! brew list python@3.12 &>/dev/null; then
    warn "Installing Python 3.12 via Homebrew…"
    brew install python@3.12 --quiet
fi

PYTHON="$(brew --prefix)/bin/python3.12"
[[ -x "$PYTHON" ]] || die "Python 3.12 not found after install."
ok "$($PYTHON --version)"

# ── Git ───────────────────────────────────────────────────────────────────────
step "Checking Git"

if ! command -v git &>/dev/null; then
    warn "Installing git via Homebrew…"
    brew install git --quiet
fi
ok "$(git --version)"

# ── Clone / update source ─────────────────────────────────────────────────────
step "Downloading Kalima"

mkdir -p "$INSTALL_DIR"

if [[ -d "$INSTALL_DIR/.git" ]]; then
    warn "Existing install found — updating to latest version…"
    git -C "$INSTALL_DIR" pull --quiet
    ok "Updated"
else
    git clone "$REPO" "$INSTALL_DIR" --quiet
    ok "Downloaded"
fi

# ── Virtual environment ───────────────────────────────────────────────────────
step "Setting up Python environment"

VENV="$INSTALL_DIR/.venv"

if [[ ! -d "$VENV" ]]; then
    "$PYTHON" -m venv "$VENV"
    ok "Virtual environment created"
else
    ok "Virtual environment already exists"
fi

# ── Dependencies ──────────────────────────────────────────────────────────────
step "Installing dependencies (first run may take a minute)"

"$VENV/bin/pip" install --upgrade pip --quiet
"$VENV/bin/pip" install -r "$INSTALL_DIR/requirements.txt" --quiet
ok "All dependencies installed"

# ── Launch ────────────────────────────────────────────────────────────────────
echo ""
echo -e "${B}  ✦ Launching Kalima…${N}"
echo ""

exec "$VENV/bin/python" "$INSTALL_DIR/guiapp.py"
