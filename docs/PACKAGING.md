# Packaging Guide

This document explains how to build distributable installers for macOS (.dmg) and Windows (.exe).

The packaging system uses PyInstaller to bundle the Python backend into a native executable, includes the pre-built React frontend as static files served by the backend, and wraps everything into platform-specific installers.

## Architecture

When packaged, the application runs as a single process:

```
ArchReverse.exe / .app
  └── Embedded Python runtime
       └── FastAPI server (port 8000)
            ├── REST API endpoints (/analyze, /status, /results, /download)
            └── Static file server (React frontend at /)
```

The launcher opens the user's default browser to `http://127.0.0.1:8000` automatically.

## Prerequisites (Both Platforms)

| Tool | Version | Purpose |
|------|---------|---------|
| Python | 3.11+ | Backend runtime |
| Node.js | 18+ | Frontend build |
| npm | 9+ | Frontend dependencies |
| Git | any | Repository cloning feature |

## Building for macOS (.dmg)

### Additional macOS Prerequisites

```bash
# Install PyInstaller
pip install pyinstaller

# Install create-dmg (optional, for polished DMG with drag-to-Applications)
brew install create-dmg
```

### Build Steps

```bash
# From the project root:
bash packaging/build_mac.sh
```

This script:
1. Builds the React frontend (`npm run build`)
2. Creates a temporary Python venv and installs all backend dependencies
3. Runs PyInstaller to bundle everything into `Architectural Reverse Engineer.app`
4. Wraps the `.app` into a `.dmg` with a drag-to-Applications layout

### Output

```
dist/ArchitecturalReverseEngineer-0.1.0-mac.dmg
```

### Installing the DMG

1. Double-click the `.dmg` file
2. Drag "Architectural Reverse Engineer" to the Applications folder
3. Open from Applications (you may need to right-click → Open the first time due to Gatekeeper)
4. The app starts a local server and opens your browser automatically

### macOS Gatekeeper Note

Since the app is not signed with an Apple Developer certificate, users will see a warning on first launch. To bypass:
- Right-click the app → Open → click "Open" in the dialog
- Or: `xattr -cr "/Applications/Architectural Reverse Engineer.app"`

To sign the app for distribution, you'll need an Apple Developer account and should add codesigning to the build script:
```bash
codesign --deep --force --sign "Developer ID Application: Your Name" \
    "dist/Architectural Reverse Engineer.app"
```

## Building for Windows (.exe)

### Additional Windows Prerequisites

- PyInstaller: `pip install pyinstaller`
- Inno Setup 6 (optional, for creating a proper installer): https://jrsoftware.org/isdl.php

### Build Steps

```cmd
REM From the project root:
packaging\build_windows.bat
```

This script:
1. Builds the React frontend (`npm run build`)
2. Creates a temporary Python venv and installs all backend dependencies
3. Runs PyInstaller to bundle everything into `dist\ArchReverse\`
4. If Inno Setup is installed, creates `dist\ArchitecturalReverseEngineer-Setup.exe`

### Output

```
dist\ArchReverse\ArchReverse.exe                    (standalone, run directly)
dist\ArchitecturalReverseEngineer-Setup.exe          (installer, if Inno Setup available)
```

### Without Inno Setup

Distribute the entire `dist\ArchReverse\` folder as a ZIP. Users extract it and run `ArchReverse.exe`.

### With Inno Setup

The installer:
- Installs to `C:\Program Files\Architectural Reverse Engineer\`
- Creates Start Menu shortcuts
- Optionally creates a Desktop shortcut
- Registers an uninstaller in Add/Remove Programs
- Launches the app after installation

### Windows SmartScreen Note

Since the executable is not code-signed, Windows SmartScreen may show a warning. Users click "More info" → "Run anyway". To avoid this, sign the executable with an Authenticode certificate:
```cmd
signtool sign /f certificate.pfx /p password /t http://timestamp.digicert.com ArchReverse.exe
```

## Runtime Requirements

The packaged application is self-contained for the Python runtime, but these external tools must be installed on the user's system for full functionality:

| Tool | Required For | Without It |
|------|-------------|------------|
| Graphviz (`dot`) | Dependency graphs, component diagrams, LLD rendering | Structured JSON data still generated; image rendering fails gracefully |
| PlantUML | UML class and sequence diagram rendering | Structured JSON and PlantUML source still generated; image rendering fails gracefully |
| Git | Cloning GitHub repositories | Local path analysis still works; GitHub URL analysis fails |
| OpenAI API key | AI-powered analysis | Must be set as `OPENAI_API_KEY` environment variable |

The app reports missing tools as non-fatal errors — users still get partial results.

## Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `OPENAI_API_KEY` | Yes | — | OpenAI API key for GPT-4 |
| `ARE_HOST` | No | `127.0.0.1` | Server bind address |
| `ARE_PORT` | No | `8000` | Server port |

## Project Structure (Packaging Files)

```
packaging/
  launcher.py          # Unified entry point — starts server, opens browser
  pyinstaller.spec     # PyInstaller configuration
  build_mac.sh         # macOS build script → .dmg
  build_windows.bat    # Windows build script → .exe
  build_frontend.sh    # Frontend-only build helper
  installer.iss        # Inno Setup script for Windows installer
  icon.icns            # (optional) macOS app icon
  icon.ico             # (optional) Windows app icon
Makefile               # Convenience targets: make build-mac, make build-windows
```

## Troubleshooting

### PyInstaller "module not found" errors

If PyInstaller can't find a module, add it to the `hiddenimports` list in `packaging/pyinstaller.spec`.

### Frontend build fails

Make sure `react-scripts` is installed:
```bash
cd frontend && npm install react-scripts --save-dev
```

### DMG creation fails on macOS

If `create-dmg` isn't installed, the script falls back to `hdiutil` which creates a basic DMG without the drag-to-Applications layout. Install `create-dmg` for the polished version:
```bash
brew install create-dmg
```

### App opens but shows "API-only mode"

The frontend build wasn't included. Make sure `frontend/build/` exists before running PyInstaller. Run `bash packaging/build_frontend.sh` first.

### Windows antivirus flags the executable

PyInstaller-bundled executables are sometimes flagged by antivirus software. This is a known false positive. Code-signing the executable resolves this.
