@echo off
REM ============================================================================
REM Build script for Windows — produces a standalone .exe installer
REM
REM Prerequisites:
REM   - Python 3.11+, Node.js 18+, npm
REM   - pip install pyinstaller
REM   - (Optional) Inno Setup 6 for .exe installer creation
REM     Download from: https://jrsoftware.org/isdl.php
REM
REM Usage:
REM   cd <project-root>
REM   packaging\build_windows.bat
REM
REM Output:
REM   dist\ArchReverse\ArchReverse.exe          (standalone app)
REM   dist\ArchitecturalReverseEngineer-Setup.exe (installer, if Inno Setup available)
REM ============================================================================

setlocal enabledelayedexpansion

set "ROOT=%~dp0.."
set "VERSION=0.1.0"
set "APP_NAME=Architectural Reverse Engineer"

echo ==========================================================
echo   Building %APP_NAME% for Windows
echo   Root: %ROOT%
echo ==========================================================
echo.

REM ------------------------------------------------------------------
REM Step 1: Build the React frontend
REM ------------------------------------------------------------------
echo ==^> Step 1: Building frontend...
cd /d "%ROOT%\frontend"

if not exist "node_modules" (
    echo     Installing npm dependencies...
    call npm install --silent
)

echo     Running production build...
set "REACT_APP_API_BASE_URL="
call npm run build 2>nul || (
    echo     react-scripts not found, installing...
    call npm install react-scripts --save-dev --silent
    call npx react-scripts build
)

echo     Frontend build complete.

REM ------------------------------------------------------------------
REM Step 2: Set up Python environment
REM ------------------------------------------------------------------
echo.
echo ==^> Step 2: Setting up Python environment...
cd /d "%ROOT%"

if not exist "packaging\.build_venv" (
    python -m venv packaging\.build_venv
)
call packaging\.build_venv\Scripts\activate.bat

pip install --quiet --upgrade pip
pip install --quiet -e "backend\.[dev]"
pip install --quiet pyinstaller

REM ------------------------------------------------------------------
REM Step 3: Bundle with PyInstaller
REM ------------------------------------------------------------------
echo.
echo ==^> Step 3: Bundling with PyInstaller...
cd /d "%ROOT%"

pyinstaller ^
    --noconfirm ^
    --clean ^
    --distpath "%ROOT%\dist" ^
    --workpath "%ROOT%\build" ^
    packaging\pyinstaller.spec

echo     PyInstaller bundle complete.

REM ------------------------------------------------------------------
REM Step 4: Create installer with Inno Setup (if available)
REM ------------------------------------------------------------------
echo.
echo ==^> Step 4: Creating installer...

set "ISCC="
if exist "C:\Program Files (x86)\Inno Setup 6\ISCC.exe" (
    set "ISCC=C:\Program Files (x86)\Inno Setup 6\ISCC.exe"
)
if exist "C:\Program Files\Inno Setup 6\ISCC.exe" (
    set "ISCC=C:\Program Files\Inno Setup 6\ISCC.exe"
)

if defined ISCC (
    echo     Found Inno Setup at: !ISCC!
    "!ISCC!" "%ROOT%\packaging\installer.iss"
    echo     Installer created.
) else (
    echo     Inno Setup not found — skipping installer creation.
    echo     The standalone executable is at: dist\ArchReverse\ArchReverse.exe
    echo.
    echo     To create an installer, install Inno Setup 6 from:
    echo     https://jrsoftware.org/isdl.php
    echo     Then re-run this script.
)

call deactivate 2>nul

echo.
echo ==========================================================
echo   Build complete!
echo   Executable: dist\ArchReverse\ArchReverse.exe
if defined ISCC (
    echo   Installer:  dist\ArchitecturalReverseEngineer-Setup.exe
)
echo ==========================================================

endlocal
