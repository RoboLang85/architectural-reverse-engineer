# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec file for the Architectural Reverse Engineer.

Bundles the Python backend, pre-built React frontend, and JSON schemas
into a single distributable directory or one-file executable.

Usage:
    cd packaging
    pyinstaller pyinstaller.spec
"""

import os
import sys
from pathlib import Path

block_cipher = None

ROOT = Path(SPECPATH).parent
BACKEND = ROOT / "backend"
FRONTEND_BUILD = ROOT / "frontend" / "build"
SCHEMAS = BACKEND / "schemas"

# Collect all backend app modules
backend_app_files = []
for f in (BACKEND / "app").rglob("*.py"):
    rel = f.relative_to(BACKEND)
    backend_app_files.append((str(f), str(rel.parent)))

# Collect JSON schemas
schema_files = []
for f in SCHEMAS.glob("*.json"):
    schema_files.append((str(f), "schemas"))

# Collect frontend build if it exists
frontend_files = []
if FRONTEND_BUILD.is_dir():
    for f in FRONTEND_BUILD.rglob("*"):
        if f.is_file():
            rel = f.relative_to(ROOT)
            frontend_files.append((str(f), str(rel.parent)))

a = Analysis(
    [str(ROOT / "packaging" / "launcher.py")],
    pathex=[str(BACKEND)],
    binaries=[],
    datas=backend_app_files + schema_files + frontend_files,
    hiddenimports=[
        "app",
        "app.api",
        "app.models",
        "app.errors",
        "app.code_ingester",
        "app.document_ingester",
        "app.pdf_processor",
        "app.ai_engine",
        "app.leanix_mapper",
        "app.diagram_generator",
        "app.document_generator",
        "app.serializer",
        "uvicorn",
        "uvicorn.logging",
        "uvicorn.loops",
        "uvicorn.loops.auto",
        "uvicorn.protocols",
        "uvicorn.protocols.http",
        "uvicorn.protocols.http.auto",
        "uvicorn.protocols.websockets",
        "uvicorn.protocols.websockets.auto",
        "uvicorn.lifespan",
        "uvicorn.lifespan.on",
        "fastapi",
        "pydantic",
        "openai",
        "fitz",
        "docx",
        "graphviz",
        "jsonschema",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["tkinter", "matplotlib", "scipy", "numpy"],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="ArchReverse",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,
    icon=str(ROOT / "packaging" / "icon.icns") if (ROOT / "packaging" / "icon.icns").exists() else None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="ArchReverse",
)

# macOS .app bundle
app = BUNDLE(
    coll,
    name="Architectural Reverse Engineer.app",
    icon=str(ROOT / "packaging" / "icon.icns") if (ROOT / "packaging" / "icon.icns").exists() else None,
    bundle_identifier="com.archreverse.app",
    info_plist={
        "CFBundleName": "Architectural Reverse Engineer",
        "CFBundleDisplayName": "Architectural Reverse Engineer",
        "CFBundleVersion": "0.1.0",
        "CFBundleShortVersionString": "0.1.0",
        "NSHighResolutionCapable": True,
    },
)
