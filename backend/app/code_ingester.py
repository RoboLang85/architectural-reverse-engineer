"""Code Ingester: scans local paths or clones GitHub repos and parses source files."""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import tempfile
from collections.abc import Callable
from pathlib import Path

from app.errors import GitError, InputError
from app.models import CodebaseModel, ModuleBoundary, SourceFile, SourceInput

# Type alias for parser callables
ParserFn = Callable[[str], tuple[list[str], list[str], list[str]]]

# Extension → language mapping
EXTENSION_LANGUAGE_MAP: dict[str, str] = {
    ".py": "python",
    ".js": "javascript",
    ".ts": "typescript",
    ".tsx": "typescript",
    ".jsx": "javascript",
    ".java": "java",
    ".kt": "kotlin",
    ".go": "go",
    ".rs": "rust",
    ".rb": "ruby",
    ".c": "c",
    ".cpp": "cpp",
    ".h": "c",
    ".hpp": "cpp",
    ".cs": "csharp",
    ".swift": "swift",
    ".scala": "scala",
    ".php": "php",
    ".r": "r",
    ".R": "r",
    ".m": "objective-c",
    ".mm": "objective-c",
    ".sh": "shell",
    ".bash": "shell",
    ".pl": "perl",
    ".lua": "lua",
    ".dart": "dart",
    ".ex": "elixir",
    ".exs": "elixir",
    ".erl": "erlang",
    ".hs": "haskell",
    ".clj": "clojure",
}

# Directories to skip during scanning
SKIP_DIRS: set[str] = {
    ".git", ".svn", ".hg", "node_modules", "__pycache__",
    ".venv", "venv", ".tox", ".mypy_cache", ".pytest_cache",
    "dist", "build", ".next", ".nuxt", "target",
}


_GITHUB_URL_RE = re.compile(
    r"^https?://github\.com/[\w.\-]+/[\w.\-]+(\.git)?(/.*)?$"
)


def detect_language(file_path: str) -> str | None:
    """Return the language for a file based on its extension, or None if unsupported."""
    ext = Path(file_path).suffix.lower()
    return EXTENSION_LANGUAGE_MAP.get(ext)


def _scan_directory(root: str) -> list[str]:
    """Recursively find all source files under *root*, skipping common non-source dirs."""
    source_files: list[str] = []
    for dirpath, dirnames, filenames in os.walk(root):
        # Prune directories we don't want to descend into
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        for fname in filenames:
            full = os.path.join(dirpath, fname)
            if detect_language(full) is not None:
                source_files.append(full)
    return source_files


# ---------------------------------------------------------------------------
# Language-specific import / export / interface parsers
# ---------------------------------------------------------------------------

def _parse_python(content: str) -> tuple[list[str], list[str], list[str]]:
    """Parse a Python file for imports, exports, and public interfaces."""
    imports: list[str] = []
    exports: list[str] = []
    public_interfaces: list[str] = []

    for line in content.splitlines():
        stripped = line.strip()
        # imports
        if stripped.startswith("import "):
            imports.append(stripped)
        elif stripped.startswith("from ") and "import" in stripped:
            imports.append(stripped)
        # __all__ as exports
        if stripped.startswith("__all__"):
            exports.append(stripped)
        # top-level class / function definitions → public interfaces
        if line.startswith("class ") or line.startswith("def "):
            name_match = re.match(r"(?:class|def)\s+(\w+)", line)
            if name_match:
                name = name_match.group(1)
                if not name.startswith("_"):
                    public_interfaces.append(name)
                    if not any("__all__" in e for e in exports):
                        exports.append(name)

    return imports, exports, public_interfaces


def _parse_js_ts(content: str) -> tuple[list[str], list[str], list[str]]:
    """Parse a JavaScript/TypeScript file for imports, exports, and public interfaces."""
    imports: list[str] = []
    exports: list[str] = []
    public_interfaces: list[str] = []

    for line in content.splitlines():
        stripped = line.strip()
        if stripped.startswith("import ") or stripped.startswith("import{"):
            imports.append(stripped)
        if "require(" in stripped:
            imports.append(stripped)
        if stripped.startswith("export "):
            exports.append(stripped)
            # extract name from common patterns
            m = re.match(
                r"export\s+(?:default\s+)?(?:function|class|const|let|var|interface|type|enum)\s+(\w+)",
                stripped,
            )
            if m:
                public_interfaces.append(m.group(1))

    return imports, exports, public_interfaces


def _parse_java(content: str) -> tuple[list[str], list[str], list[str]]:
    """Parse a Java file for imports, exports (package), and public interfaces."""
    imports: list[str] = []
    exports: list[str] = []
    public_interfaces: list[str] = []

    for line in content.splitlines():
        stripped = line.strip()
        if stripped.startswith("import "):
            imports.append(stripped.rstrip(";"))
        if stripped.startswith("package "):
            exports.append(stripped.rstrip(";"))
        m = re.match(r"public\s+(?:class|interface|enum|abstract\s+class)\s+(\w+)", stripped)
        if m:
            public_interfaces.append(m.group(1))

    return imports, exports, public_interfaces


_PARSER_REGISTRY: dict[str, ParserFn] = {
    "python": _parse_python,
    "javascript": _parse_js_ts,
    "typescript": _parse_js_ts,
    "java": _parse_java,
}


def _parse_file(file_path: str, language: str) -> tuple[list[str], list[str], list[str]]:
    """Read a file and return (imports, exports, public_interfaces)."""
    try:
        with open(file_path, encoding="utf-8", errors="replace") as fh:
            content = fh.read()
    except OSError:
        return [], [], []

    parser = _PARSER_REGISTRY.get(language)
    if parser is None:
        return [], [], []
    return parser(content)


# ---------------------------------------------------------------------------
# Module boundary detection
# ---------------------------------------------------------------------------

def _build_module_boundaries(
    root: str, source_files: list[SourceFile]
) -> list[ModuleBoundary]:
    """Group files by their top-level directory relative to *root*."""
    modules: dict[str, list[str]] = {}
    for sf in source_files:
        rel = os.path.relpath(sf.path, root)
        parts = Path(rel).parts
        module_name = parts[0] if len(parts) > 1 else "(root)"
        modules.setdefault(module_name, []).append(sf.path)

    # Build dependency info: a module depends on another if any of its files
    # import something that looks like it belongs to another module.
    all_module_names = set(modules.keys())
    boundaries: list[ModuleBoundary] = []
    for mod_name, files in modules.items():
        deps: set[str] = set()
        for sf in source_files:
            if sf.path in files:
                for imp in sf.imports:
                    for other in all_module_names:
                        if other != mod_name and other != "(root)" and other in imp:
                            deps.add(other)
        boundaries.append(
            ModuleBoundary(name=mod_name, files=files, dependencies=sorted(deps))
        )
    return boundaries


# ---------------------------------------------------------------------------
# GitHub cloning
# ---------------------------------------------------------------------------

def _clone_github_repo(url: str) -> str:
    """Clone a GitHub repo to a temp directory. Returns the path. Raises GitError on failure."""
    if not _GITHUB_URL_RE.match(url):
        raise InputError(
            f"Invalid GitHub URL: {url}",
            details={"url": url, "reason": "URL does not match expected GitHub format"},
        )

    tmp_dir = tempfile.mkdtemp(prefix="arch_re_")
    try:
        result = subprocess.run(
            ["git", "clone", "--depth", "1", url, tmp_dir],
            capture_output=True,
            text=True,
            timeout=120,
        )
        if result.returncode != 0:
            raise GitError(
                f"Failed to clone repository: {url}",
                details={"url": url, "stderr": result.stderr.strip()},
            )
    except FileNotFoundError:
        shutil.rmtree(tmp_dir, ignore_errors=True)
        raise GitError(
            "git CLI not found. Please install git.",
            details={"url": url, "reason": "git executable not found"},
        )
    except subprocess.TimeoutExpired:
        shutil.rmtree(tmp_dir, ignore_errors=True)
        raise GitError(
            f"Cloning timed out for repository: {url}",
            details={"url": url, "reason": "clone timed out after 120s"},
        )
    except GitError:
        shutil.rmtree(tmp_dir, ignore_errors=True)
        raise
    return tmp_dir


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def ingest(source: SourceInput) -> CodebaseModel:
    """Ingest a codebase from a local path or GitHub URL and return a CodebaseModel."""
    if source.input_type == "local_path":
        return _ingest_local(source.value)
    elif source.input_type == "github_url":
        return _ingest_github(source.value)
    else:
        raise InputError(
            f"Unsupported input type: {source.input_type}",
            details={"input_type": source.input_type},
        )


def _ingest_local(path: str) -> CodebaseModel:
    """Ingest from a local directory path."""
    if not os.path.exists(path):
        raise InputError(
            f"Path does not exist: {path}",
            details={"path": path, "reason": "path does not exist"},
        )
    if not os.path.isdir(path):
        raise InputError(
            f"Path is not a directory: {path}",
            details={"path": path, "reason": "path is not a directory"},
        )
    if not os.access(path, os.R_OK):
        raise InputError(
            f"Path is not accessible: {path}",
            details={"path": path, "reason": "permission denied"},
        )

    raw_files = _scan_directory(path)
    source_files: list[SourceFile] = []
    for fp in raw_files:
        lang = detect_language(fp)
        if lang is None:
            continue
        imports, exports, public_interfaces = _parse_file(fp, lang)
        source_files.append(
            SourceFile(
                path=fp,
                language=lang,
                imports=imports,
                exports=exports,
                public_interfaces=public_interfaces,
            )
        )

    boundaries = _build_module_boundaries(path, source_files)
    return CodebaseModel(
        root_path=path,
        files=source_files,
        module_boundaries=boundaries,
    )


def _ingest_github(url: str) -> CodebaseModel:
    """Clone a GitHub repo and ingest it."""
    clone_dir = _clone_github_repo(url)
    try:
        model = _ingest_local(clone_dir)
        # Replace root_path with the original URL for clarity
        model = model.model_copy(update={"root_path": url})
        return model
    finally:
        shutil.rmtree(clone_dir, ignore_errors=True)
