#!/usr/bin/env python3
"""Unified launcher for the Architectural Reverse Engineer.

Starts the FastAPI backend server and opens the frontend in the default
browser. When the frontend is a pre-built static bundle, it is served
directly by FastAPI. Otherwise falls back to the API-only mode.
"""

from __future__ import annotations

import os
import signal
import sys
import threading
import time
import webbrowser
from pathlib import Path

import uvicorn
from fastapi.staticfiles import StaticFiles

# Resolve paths relative to this file (works inside PyInstaller bundle too)
if getattr(sys, "frozen", False):
    BASE_DIR = Path(sys._MEIPASS)
else:
    BASE_DIR = Path(__file__).resolve().parent.parent

FRONTEND_BUILD = BASE_DIR / "frontend" / "build"
BACKEND_DIR = BASE_DIR / "backend"

# Ensure backend is importable
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

HOST = os.environ.get("ARE_HOST", "127.0.0.1")
PORT = int(os.environ.get("ARE_PORT", "8000"))


def _open_browser() -> None:
    """Wait for the server to start, then open the browser."""
    time.sleep(1.5)
    webbrowser.open(f"http://{HOST}:{PORT}")


def main() -> None:
    from app.api import app

    # Mount the pre-built React frontend if available
    if FRONTEND_BUILD.is_dir() and (FRONTEND_BUILD / "index.html").exists():
        app.mount("/", StaticFiles(directory=str(FRONTEND_BUILD), html=True), name="frontend")
        print(f"Serving frontend from {FRONTEND_BUILD}")
    else:
        print("No frontend build found — running API-only mode.")
        print("Access the API docs at http://{HOST}:{PORT}/docs")

    # Open browser in a background thread
    threading.Thread(target=_open_browser, daemon=True).start()

    print(f"\n  Architectural Reverse Engineer")
    print(f"  Running at http://{HOST}:{PORT}")
    print(f"  Press Ctrl+C to stop.\n")

    uvicorn.run(app, host=HOST, port=PORT, log_level="info")


if __name__ == "__main__":
    main()
