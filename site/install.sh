#!/bin/bash
# Pratibmb Installer — one command to install everything
# Usage: curl -fsSL https://pratibmb.com/install.sh | bash
set -euo pipefail

FILE_VERSION="0.5.0"  # must match version in desktop/src-tauri/tauri.conf.json
REPO="tapaskar/Pratibmb"
INSTALL_DIR="$HOME/Pratibmb"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

info()  { echo -e "${CYAN}[pratibmb]${NC} $1"; }
ok()    { echo -e "${GREEN}[✓]${NC} $1"; }
warn()  { echo -e "${YELLOW}[!]${NC} $1"; }
fail()  { echo -e "${RED}[✗]${NC} $1"; exit 1; }

echo ""
echo -e "${CYAN}╔══════════════════════════════════════════════════╗${NC}"
echo -e "${CYAN}║${NC}  Pratibmb — Chat with your 10-years-younger self ${CYAN}║${NC}"
echo -e "${CYAN}║${NC}  100% local. No cloud. No telemetry.              ${CYAN}║${NC}"
echo -e "${CYAN}╚══════════════════════════════════════════════════╝${NC}"
echo ""

# ── Step 1: Check Python ──────────────────────────────────────────────
info "Checking Python..."

PYTHON=""
for cmd in python3 python; do
    if command -v "$cmd" &>/dev/null; then
        PY_VERSION=$("$cmd" --version 2>&1 | grep -oE '[0-9]+\.[0-9]+')
        PY_MAJOR=$(echo "$PY_VERSION" | cut -d. -f1)
        PY_MINOR=$(echo "$PY_VERSION" | cut -d. -f2)
        if [ "$PY_MAJOR" -eq 3 ] && [ "$PY_MINOR" -ge 9 ]; then
            PYTHON="$cmd"
            ok "Found $cmd ($($cmd --version 2>&1))"
            break
        else
            warn "$cmd is version $PY_VERSION (need 3.9+), skipping"
        fi
    fi
done

if [ -z "$PYTHON" ]; then
    fail "Python 3.9+ not found. Install from https://python.org/downloads/"
fi

# ── Step 1b: Check RAM ──
info "Checking system resources..."
if [ "$OS" = "Darwin" ]; then
    RAM_MB=$(sysctl -n hw.memsize 2>/dev/null | awk '{print int($1/1048576)}')
elif [ "$OS" = "Linux" ]; then
    RAM_MB=$(grep MemTotal /proc/meminfo 2>/dev/null | awk '{print int($2/1024)}')
fi
if [ -n "$RAM_MB" ] && [ "$RAM_MB" -lt 7500 ]; then
    warn "Only ${RAM_MB}MB RAM detected. Pratibmb needs ~8GB for the full pipeline."
    warn "Embedding and chat may fail on this machine."
fi

# ── Step 2: Detect platform ───────────────────────────────────────────
OS=$(uname -s)
ARCH=$(uname -m)

case "$OS" in
    Darwin)
        if [ "$ARCH" = "arm64" ]; then
            PLATFORM="macOS (Apple Silicon)"
            DMG_FILE="Pratibmb_${FILE_VERSION}_aarch64.dmg"
        else
            PLATFORM="macOS (Intel)"
            DMG_FILE="Pratibmb_${FILE_VERSION}_x64.dmg"
        fi
        ;;
    Linux)
        PLATFORM="Linux"
        DEB_FILE="Pratibmb_${FILE_VERSION}_amd64.deb"
        APPIMAGE_FILE="Pratibmb_${FILE_VERSION}_amd64.AppImage"
        ;;
    *)
        fail "Unsupported OS: $OS. Use the Windows installer from https://pratibmb.com/#downloads"
        ;;
esac

ok "Platform: $PLATFORM ($ARCH)"

# ── Step 3: Clone or update the repo ──────────────────────────────────
info "Setting up Pratibmb at $INSTALL_DIR..."

if [ -d "$INSTALL_DIR/.git" ]; then
    info "Repository exists, pulling latest..."
    cd "$INSTALL_DIR"
    git pull --quiet origin main 2>/dev/null || warn "Could not pull updates (offline?)"
    ok "Repository updated"
elif [ -d "$INSTALL_DIR/pratibmb" ]; then
    ok "Pratibmb package found at $INSTALL_DIR"
else
    info "Cloning repository..."
    git clone --quiet --depth 1 https://github.com/$REPO.git "$INSTALL_DIR" 2>/dev/null \
        || fail "Could not clone repository. Check your internet connection."
    ok "Repository cloned"
fi

cd "$INSTALL_DIR"

# ── Step 4: Install Python dependencies ───────────────────────────────
info "Installing Python dependencies..."

# Linux: install build deps if needed (for native extensions like llama-cpp-python)
if [ "$OS" = "Linux" ] && ! command -v cmake &>/dev/null; then
    info "Installing build tools for native extensions..."
    if command -v apt-get &>/dev/null; then
        sudo apt-get install -y -qq python3-dev cmake build-essential 2>/dev/null || warn "Could not install build tools"
    elif command -v dnf &>/dev/null; then
        sudo dnf install -y python3-devel cmake gcc-c++ 2>/dev/null || warn "Could not install build tools"
    fi
fi

$PYTHON -m pip install --quiet --upgrade pip 2>/dev/null || true

# Install the package in editable mode (so the Tauri app can find it)
$PYTHON -m pip install --quiet --prefer-binary --extra-index-url https://abetlen.github.io/llama-cpp-python/whl/cpu -e . 2>&1 | tail -3 || {
    warn "pip install failed, trying with --user flag..."
    $PYTHON -m pip install --quiet --user --prefer-binary --extra-index-url https://abetlen.github.io/llama-cpp-python/whl/cpu -e . 2>&1 | tail -3 \
        || fail "Could not install Python dependencies. Try: cd $INSTALL_DIR && pip install -e ."
}

# Verify installation
if $PYTHON -c "import pratibmb; print('ok')" 2>/dev/null; then
    ok "Python package installed"
else
    fail "Package installed but import failed. Run: $PYTHON -c 'import pratibmb'"
fi

# ── Step 5: Install the desktop app ───────────────────────────────────
info "Installing desktop app..."

DOWNLOAD_URL="https://github.com/$REPO/releases/latest/download"

case "$OS" in
    Darwin)
        DMG_PATH="/tmp/$DMG_FILE"
        if [ ! -f "$DMG_PATH" ]; then
            info "Downloading $DMG_FILE..."
            curl -fSL "$DOWNLOAD_URL/$DMG_FILE" -o "$DMG_PATH" \
                || fail "Download failed. Check https://github.com/$REPO/releases"
        fi

        info "Mounting DMG..."
        MOUNT_DIR=$(hdiutil attach "$DMG_PATH" -nobrowse -quiet 2>/dev/null | grep "/Volumes" | awk '{print $NF}') \
            || MOUNT_DIR=$(hdiutil attach "$DMG_PATH" -nobrowse 2>/dev/null | tail -1 | awk '{for(i=3;i<=NF;i++) printf "%s ", $i; print ""}' | xargs)

        if [ -z "$MOUNT_DIR" ] || [ ! -d "$MOUNT_DIR" ]; then
            # Try a simpler approach
            hdiutil attach "$DMG_PATH" -nobrowse 2>/dev/null
            MOUNT_DIR="/Volumes/Pratibmb"
        fi

        if [ -d "$MOUNT_DIR/Pratibmb.app" ]; then
            info "Copying to /Applications..."
            cp -Rf "$MOUNT_DIR/Pratibmb.app" /Applications/ 2>/dev/null \
                || sudo cp -Rf "$MOUNT_DIR/Pratibmb.app" /Applications/
            hdiutil detach "$MOUNT_DIR" -quiet 2>/dev/null || true

            # Remove quarantine flag (unsigned app)
            xattr -cr /Applications/Pratibmb.app 2>/dev/null || true
            ok "App installed to /Applications/Pratibmb.app"
        else
            hdiutil detach "$MOUNT_DIR" -quiet 2>/dev/null || true
            warn "Could not find Pratibmb.app in DMG. You may need to install manually."
        fi

        rm -f "$DMG_PATH"
        ;;

    Linux)
        if command -v dpkg &>/dev/null; then
            DEB_PATH="/tmp/$DEB_FILE"
            info "Downloading $DEB_FILE..."
            curl -fSL "$DOWNLOAD_URL/$DEB_FILE" -o "$DEB_PATH" \
                || fail "Download failed"
            info "Installing .deb package..."
            sudo dpkg -i "$DEB_PATH" 2>/dev/null || sudo apt-get install -f -y
            rm -f "$DEB_PATH"
            ok "Deb package installed"
        else
            APPIMAGE_PATH="$HOME/.local/bin/pratibmb"
            mkdir -p "$HOME/.local/bin"
            info "Downloading AppImage..."
            curl -fSL "$DOWNLOAD_URL/$APPIMAGE_FILE" -o "$APPIMAGE_PATH" \
                || fail "Download failed"
            chmod +x "$APPIMAGE_PATH"
            ok "AppImage installed to $APPIMAGE_PATH"
            info "Make sure ~/.local/bin is in your PATH"
        fi
        ;;
esac

# ── Step 6: Verify ────────────────────────────────────────────────────
info "Running diagnostics..."

if command -v pratibmb &>/dev/null; then
    pratibmb doctor 2>/dev/null || true
else
    # Run doctor via python directly
    $PYTHON -m pratibmb.cli doctor 2>/dev/null || {
        warn "Could not run diagnostics (non-critical)"
    }
fi

# ── Done ──────────────────────────────────────────────────────────────
echo ""
echo -e "${GREEN}╔══════════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║${NC}  Installation complete!                           ${GREEN}║${NC}"
echo -e "${GREEN}╚══════════════════════════════════════════════════╝${NC}"
echo ""

case "$OS" in
    Darwin)
        echo "  To launch:  open /Applications/Pratibmb.app"
        echo "  Or CLI:     pratibmb --help"
        ;;
    Linux)
        echo "  To launch:  pratibmb (from app menu or terminal)"
        echo "  Or CLI:     pratibmb --help"
        ;;
esac

echo ""
echo "  Requirements: 8GB+ RAM recommended for embedding & chat."
echo "  First launch downloads AI models (~2.5GB)."
echo "  After that, it works fully offline."
echo ""
echo -e "  ${CYAN}https://pratibmb.com${NC}"
echo ""
