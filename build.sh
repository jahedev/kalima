#!/bin/bash
# build.sh — Kalima local build script
#
# Usage:
#   ./build.sh                        # build .app + DMG for current arch
#   ./build.sh --dmg                  # same (explicit)
#   ./build.sh --app-only             # .app only, no DMG
#   ./build.sh --arm64                # arm64 .app + DMG
#   ./build.sh --intel                # x86_64 .app + DMG
#   ./build.sh --both                 # arm64 + x86_64 .app + DMG
#   ./build.sh --both --app-only      # arm64 + x86_64 .app, no DMG
#   ./build.sh --version v1.0.0       # set version string used in DMG filename
#   ./build.sh --help

set -e

# ── Colours ───────────────────────────────────────────────────────────────────
B='\033[1m'; G='\033[0;32m'; Y='\033[1;33m'; R='\033[0;31m'; C='\033[0;36m'; N='\033[0m'
step()  { echo -e "\n${B}▸ $1${N}"; }
ok()    { echo -e "${G}  ✓ $1${N}"; }
warn()  { echo -e "${Y}  ! $1${N}"; }
die()   { echo -e "${R}  ✗ $1${N}" >&2; exit 1; }
info()  { echo -e "${C}  → $1${N}"; }

# ── Defaults ──────────────────────────────────────────────────────────────────
ARCH="current"   # current | arm64 | intel | both
DMG=true
VERSION=""

# ── Help ──────────────────────────────────────────────────────────────────────
usage() {
    cat <<EOF

${B}Kalima build script${N}

  ${B}Usage:${N}  ./build.sh [options]

  ${B}Arch options:${N}
    (none)          Build for the current machine's architecture (default)
    --arm64         Build for Apple Silicon only
    --intel         Build for Intel only
    --both          Build for both architectures

  ${B}Output options:${N}
    --app-only      Stop after building Kalima.app (skip DMG creation)
    --dmg           Build .app and wrap it in a DMG (default)

  ${B}Other:${N}
    --version X     Version string used in the DMG filename (e.g. v1.2.0)
    --help          Show this message

  ${B}Examples:${N}
    ./build.sh                        # .app + DMG for this Mac
    ./build.sh --app-only             # .app only, no DMG
    ./build.sh --intel --app-only     # Intel .app only
    ./build.sh --both                 # both arch DMGs
    ./build.sh --arm64 --version v1.0.0

EOF
    exit 0
}

# ── Argument parsing ──────────────────────────────────────────────────────────
while [[ $# -gt 0 ]]; do
    case "$1" in
        --arm64)      ARCH="arm64"   ;;
        --intel)      ARCH="intel"   ;;
        --both)       ARCH="both"    ;;
        --app-only)   DMG=false      ;;
        --dmg)        DMG=true       ;;
        --version)    shift; VERSION="$1" ;;
        --help|-h)    usage ;;
        *) die "Unknown option: $1. Run ./build.sh --help for usage." ;;
    esac
    shift
done

# ── Resolve current arch ──────────────────────────────────────────────────────
MACHINE_ARCH="$(uname -m)"   # arm64 or x86_64
if [[ "$ARCH" == "current" ]]; then
    ARCH="$MACHINE_ARCH"
fi

# Normalise x86_64 → intel label
if [[ "$ARCH" == "x86_64" ]]; then ARCH="intel"; fi

# ── Sanity checks ─────────────────────────────────────────────────────────────
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

[[ -f "kalima.spec" ]] || die "kalima.spec not found — run this script from the repo root."

# ── Environment detection ─────────────────────────────────────────────────────
ARM_PYTHON="/opt/homebrew/bin/python3.12"
INTEL_PYTHON="/usr/local/bin/python3.12"
ARM_PYINSTALLER="/opt/homebrew/bin/pyinstaller"
INTEL_PYINSTALLER="/usr/local/bin/pyinstaller"

# Prefer venv pyinstaller if available
[[ -x ".venv/bin/pyinstaller" ]]       && ARM_PYINSTALLER=".venv/bin/pyinstaller"
[[ -x ".venv-intel/bin/pyinstaller" ]] && INTEL_PYINSTALLER=".venv-intel/bin/pyinstaller"

# ── Header ────────────────────────────────────────────────────────────────────
echo ""
echo -e "${B}  كلمة  Kalima — Build Script${N}"
echo    "  ──────────────────────────────"
echo -e "  Arch:    ${C}${ARCH}${N}"
echo -e "  DMG:     ${C}${DMG}${N}"
[[ -n "$VERSION" ]] && echo -e "  Version: ${C}${VERSION}${N}"
echo ""

# ── Build function ────────────────────────────────────────────────────────────
build_for_arch() {
    local arch="$1"   # arm64 or intel
    local label suffix pyinstaller

    if [[ "$arch" == "arm64" ]]; then
        label="Apple Silicon (arm64)"
        suffix="arm64"
        pyinstaller="$ARM_PYINSTALLER"
    else
        label="Intel (x86_64)"
        suffix="x86_64"
        pyinstaller="$INTEL_PYINSTALLER"
    fi

    # ── Check pyinstaller is available ────────────────────────────────────────
    if [[ ! -x "$pyinstaller" ]]; then
        # Try to find it on PATH as a last resort
        pyinstaller="$(command -v pyinstaller 2>/dev/null || true)"
        [[ -n "$pyinstaller" && -x "$pyinstaller" ]] || \
            die "pyinstaller not found for $label.\n  For arm64: pip install pyinstaller\n  For intel: arch -x86_64 .venv-intel/bin/pip install pyinstaller"
    fi

    step "Building Kalima.app for $label"
    info "Using: $pyinstaller"

    if [[ "$arch" == "intel" && "$MACHINE_ARCH" == "arm64" ]]; then
        arch -x86_64 "$pyinstaller" kalima.spec --noconfirm
    else
        "$pyinstaller" kalima.spec --noconfirm
    fi

    ok "dist/Kalima.app built for $label"

    # ── Verify the binary arch ────────────────────────────────────────────────
    BIN_ARCH="$(file dist/Kalima.app/Contents/MacOS/Kalima | awk '{print $NF}')"
    info "Binary architecture: $BIN_ARCH"

    # ── DMG ───────────────────────────────────────────────────────────────────
    if [[ "$DMG" == true ]]; then
        step "Creating DMG for $label"

        if [[ -n "$VERSION" ]]; then
            DMG_NAME="Kalima-${VERSION}-${suffix}.dmg"
        else
            DMG_NAME="Kalima-${suffix}.dmg"
        fi

        STAGING="$(mktemp -d)"
        cp -R dist/Kalima.app "$STAGING/"
        ln -s /Applications "$STAGING/Applications"

        hdiutil create \
            -volname "Kalima" \
            -srcfolder "$STAGING" \
            -ov -format UDRW \
            /tmp/kalima_rw.dmg \
            -quiet

        hdiutil convert \
            /tmp/kalima_rw.dmg \
            -format UDZO \
            -imagekey zlib-level=9 \
            -o "dist/${DMG_NAME}" \
            -quiet

        rm -rf "$STAGING" /tmp/kalima_rw.dmg

        ok "dist/${DMG_NAME}  ($(du -sh "dist/${DMG_NAME}" | cut -f1))"
    fi
}

# ── Run builds ────────────────────────────────────────────────────────────────
case "$ARCH" in
    arm64)
        build_for_arch arm64
        ;;
    intel)
        build_for_arch intel
        ;;
    both)
        build_for_arch arm64
        build_for_arch intel
        ;;
    *)
        die "Unexpected arch value: $ARCH"
        ;;
esac

# ── Summary ───────────────────────────────────────────────────────────────────
echo ""
echo -e "${B}  Build complete!${N}"
echo    "  ──────────────────────────────"
echo    "  Output files in: dist/"
ls dist/Kalima*.dmg dist/Kalima.app 2>/dev/null | sed 's/^/  /'
echo ""
