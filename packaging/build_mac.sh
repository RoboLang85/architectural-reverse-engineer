#!/usr/bin/env bash
# ============================================================================
# Build script for macOS — produces a .dmg installer
#
# Prerequisites:
#   - Python 3.11+, Node.js 18+, npm
#   - pip install pyinstaller
#   - brew install create-dmg  (for DMG creation)
#
# Usage:
#   cd <project-root>
#   bash packaging/build_mac.sh
#
# Output:
#   dist/ArchitecturalReverseEngineer-0.1.0-mac.dmg
# ============================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
VERSION="0.1.0"
APP_NAME="Architectural Reverse Engineer"
DMG_NAME="ArchitecturalReverseEngineer-${VERSION}-mac.dmg"

echo "==> Building Architectural Reverse Engineer for macOS"
echo "    Root: $ROOT"
echo ""

# ------------------------------------------------------------------
# Step 1: Build the React frontend
# ------------------------------------------------------------------
echo "==> Step 1: Building frontend..."
cd "$ROOT/frontend"

if [ ! -d "node_modules" ]; then
    echo "    Installing npm dependencies..."
    npm install --silent
fi

echo "    Running production build..."
REACT_APP_API_BASE_URL="" npm run build 2>/dev/null || {
    echo "    react-scripts not found, installing..."
    npm install react-scripts --save-dev --silent
    REACT_APP_API_BASE_URL="" npx react-scripts build
}

echo "    Frontend build complete: frontend/build/"

# ------------------------------------------------------------------
# Step 2: Set up Python environment and install dependencies
# ------------------------------------------------------------------
echo ""
echo "==> Step 2: Setting up Python environment..."
cd "$ROOT"

if [ ! -d "packaging/.build_venv" ]; then
    python3 -m venv packaging/.build_venv
fi
source packaging/.build_venv/bin/activate

pip install --quiet --upgrade pip
pip install --quiet -e "backend/.[dev]"
pip install --quiet pyinstaller

# ------------------------------------------------------------------
# Step 3: Bundle with PyInstaller
# ------------------------------------------------------------------
echo ""
echo "==> Step 3: Bundling with PyInstaller..."
cd "$ROOT"

pyinstaller \
    --noconfirm \
    --clean \
    --distpath "$ROOT/dist" \
    --workpath "$ROOT/build" \
    packaging/pyinstaller.spec

echo "    PyInstaller bundle complete."

# ------------------------------------------------------------------
# Step 4: Create DMG
# ------------------------------------------------------------------
echo ""
echo "==> Step 4: Creating DMG installer..."

APP_PATH="$ROOT/dist/${APP_NAME}.app"
DMG_PATH="$ROOT/dist/${DMG_NAME}"

# Remove old DMG if it exists
rm -f "$DMG_PATH"

if command -v create-dmg &>/dev/null; then
    create-dmg \
        --volname "$APP_NAME" \
        --volicon "$ROOT/packaging/icon.icns" 2>/dev/null || true \
        --window-pos 200 120 \
        --window-size 600 400 \
        --icon-size 100 \
        --icon "$APP_NAME.app" 150 190 \
        --app-drop-link 450 190 \
        --no-internet-enable \
        "$DMG_PATH" \
        "$APP_PATH" \
    || {
        # Fallback: create-dmg may fail on icon if icon.icns doesn't exist
        create-dmg \
            --volname "$APP_NAME" \
            --window-pos 200 120 \
            --window-size 600 400 \
            --icon-size 100 \
            --icon "$APP_NAME.app" 150 190 \
            --app-drop-link 450 190 \
            --no-internet-enable \
            "$DMG_PATH" \
            "$APP_PATH"
    }
else
    echo "    create-dmg not found, using hdiutil fallback..."
    # Fallback using hdiutil directly
    STAGING="$ROOT/build/dmg_staging"
    rm -rf "$STAGING"
    mkdir -p "$STAGING"
    cp -R "$APP_PATH" "$STAGING/"
    ln -s /Applications "$STAGING/Applications"

    hdiutil create \
        -volname "$APP_NAME" \
        -srcfolder "$STAGING" \
        -ov \
        -format UDZO \
        "$DMG_PATH"

    rm -rf "$STAGING"
fi

deactivate 2>/dev/null || true

echo ""
echo "============================================"
echo "  Build complete!"
echo "  DMG: $DMG_PATH"
echo "============================================"
