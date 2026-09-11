"""Unit tests for the Code Ingester component."""

from __future__ import annotations

import os
import subprocess
from unittest.mock import MagicMock, patch

import pytest

from app.code_ingester import (
    _build_module_boundaries,
    _parse_java,
    _parse_js_ts,
    _parse_python,
    _scan_directory,
    detect_language,
    ingest,
)
from app.errors import GitError, InputError
from app.models import CodebaseModel, SourceFile, SourceInput


# ---------------------------------------------------------------------------
# detect_language
# ---------------------------------------------------------------------------

class TestDetectLanguage:
    def test_python(self):
        assert detect_language("main.py") == "python"

    def test_javascript(self):
        assert detect_language("index.js") == "javascript"

    def test_typescript(self):
        assert detect_language("app.ts") == "typescript"

    def test_tsx(self):
        assert detect_language("Component.tsx") == "typescript"

    def test_java(self):
        assert detect_language("Main.java") == "java"

    def test_go(self):
        assert detect_language("main.go") == "go"

    def test_rust(self):
        assert detect_language("lib.rs") == "rust"

    def test_unsupported_extension(self):
        assert detect_language("readme.md") is None

    def test_no_extension(self):
        assert detect_language("Makefile") is None


# ---------------------------------------------------------------------------
# _scan_directory
# ---------------------------------------------------------------------------

class TestScanDirectory:
    def test_finds_python_files(self, tmp_path):
        (tmp_path / "main.py").write_text("print('hi')")
        (tmp_path / "lib.py").write_text("x = 1")
        result = _scan_directory(str(tmp_path))
        assert len(result) == 2

    def test_recurses_into_subdirs(self, tmp_path):
        sub = tmp_path / "pkg"
        sub.mkdir()
        (sub / "mod.py").write_text("pass")
        result = _scan_directory(str(tmp_path))
        assert len(result) == 1
        assert "mod.py" in result[0]

    def test_skips_node_modules(self, tmp_path):
        nm = tmp_path / "node_modules"
        nm.mkdir()
        (nm / "dep.js").write_text("module.exports = {}")
        (tmp_path / "app.js").write_text("const x = 1;")
        result = _scan_directory(str(tmp_path))
        assert len(result) == 1

    def test_skips_pycache(self, tmp_path):
        pc = tmp_path / "__pycache__"
        pc.mkdir()
        (pc / "mod.cpython-311.pyc").write_text("")
        (tmp_path / "mod.py").write_text("pass")
        result = _scan_directory(str(tmp_path))
        assert len(result) == 1

    def test_ignores_non_source_files(self, tmp_path):
        (tmp_path / "readme.md").write_text("# Hello")
        (tmp_path / "data.csv").write_text("a,b")
        result = _scan_directory(str(tmp_path))
        assert len(result) == 0

    def test_empty_directory(self, tmp_path):
        result = _scan_directory(str(tmp_path))
        assert result == []

    def test_deeply_nested(self, tmp_path):
        deep = tmp_path / "a" / "b" / "c"
        deep.mkdir(parents=True)
        (deep / "deep.py").write_text("pass")
        result = _scan_directory(str(tmp_path))
        assert len(result) == 1


# ---------------------------------------------------------------------------
# Python parser
# ---------------------------------------------------------------------------

class TestParsePython:
    def test_imports(self):
        code = "import os\nfrom pathlib import Path\n"
        imports, _, _ = _parse_python(code)
        assert "import os" in imports
        assert "from pathlib import Path" in imports

    def test_public_class_and_function(self):
        code = "class Foo:\n    pass\n\ndef bar():\n    pass\n"
        _, exports, public = _parse_python(code)
        assert "Foo" in public
        assert "bar" in public

    def test_private_excluded(self):
        code = "def _helper():\n    pass\nclass _Internal:\n    pass\n"
        _, _, public = _parse_python(code)
        assert public == []

    def test_all_export(self):
        code = '__all__ = ["Foo", "bar"]\nclass Foo:\n    pass\ndef bar():\n    pass\n'
        _, exports, _ = _parse_python(code)
        assert any("__all__" in e for e in exports)


# ---------------------------------------------------------------------------
# JS/TS parser
# ---------------------------------------------------------------------------

class TestParseJsTs:
    def test_import_statements(self):
        code = "import React from 'react';\nconst fs = require('fs');\n"
        imports, _, _ = _parse_js_ts(code)
        assert len(imports) == 2

    def test_export_function(self):
        code = "export function greet() {}\nexport default class App {}\n"
        _, exports, public = _parse_js_ts(code)
        assert len(exports) == 2
        assert "greet" in public
        assert "App" in public

    def test_export_const(self):
        code = "export const VERSION = '1.0';\n"
        _, exports, public = _parse_js_ts(code)
        assert "VERSION" in public


# ---------------------------------------------------------------------------
# Java parser
# ---------------------------------------------------------------------------

class TestParseJava:
    def test_imports_and_package(self):
        code = "package com.example;\nimport java.util.List;\npublic class Main {}\n"
        imports, exports, public = _parse_java(code)
        assert "import java.util.List" in imports
        assert "package com.example" in exports
        assert "Main" in public


# ---------------------------------------------------------------------------
# Module boundaries
# ---------------------------------------------------------------------------

class TestModuleBoundaries:
    def test_groups_by_top_level_dir(self, tmp_path):
        files = [
            SourceFile(path=str(tmp_path / "pkg_a" / "mod.py"), language="python", imports=[], exports=[], public_interfaces=[]),
            SourceFile(path=str(tmp_path / "pkg_b" / "mod.py"), language="python", imports=[], exports=[], public_interfaces=[]),
            SourceFile(path=str(tmp_path / "main.py"), language="python", imports=[], exports=[], public_interfaces=[]),
        ]
        boundaries = _build_module_boundaries(str(tmp_path), files)
        names = {b.name for b in boundaries}
        assert "pkg_a" in names
        assert "pkg_b" in names
        assert "(root)" in names

    def test_dependency_detection(self, tmp_path):
        files = [
            SourceFile(
                path=str(tmp_path / "api" / "views.py"),
                language="python",
                imports=["from models import User"],
                exports=[],
                public_interfaces=[],
            ),
            SourceFile(
                path=str(tmp_path / "models" / "user.py"),
                language="python",
                imports=[],
                exports=["User"],
                public_interfaces=["User"],
            ),
        ]
        boundaries = _build_module_boundaries(str(tmp_path), files)
        api_mod = next(b for b in boundaries if b.name == "api")
        assert "models" in api_mod.dependencies


# ---------------------------------------------------------------------------
# ingest – local path
# ---------------------------------------------------------------------------

class TestIngestLocal:
    def test_valid_directory(self, tmp_path):
        (tmp_path / "app.py").write_text("import os\n\nclass App:\n    pass\n")
        sub = tmp_path / "utils"
        sub.mkdir()
        (sub / "helpers.py").write_text("def helper():\n    pass\n")

        source = SourceInput(input_type="local_path", value=str(tmp_path))
        model = ingest(source)

        assert isinstance(model, CodebaseModel)
        assert model.root_path == str(tmp_path)
        assert len(model.files) == 2
        langs = {f.language for f in model.files}
        assert langs == {"python"}

    def test_nonexistent_path_raises_input_error(self):
        source = SourceInput(input_type="local_path", value="/nonexistent/path/xyz")
        with pytest.raises(InputError, match="does not exist"):
            ingest(source)

    def test_file_instead_of_dir_raises_input_error(self, tmp_path):
        f = tmp_path / "file.txt"
        f.write_text("hi")
        source = SourceInput(input_type="local_path", value=str(f))
        with pytest.raises(InputError, match="not a directory"):
            ingest(source)

    def test_parses_imports_and_exports(self, tmp_path):
        (tmp_path / "mod.py").write_text(
            "import os\nfrom sys import argv\n\nclass Foo:\n    pass\n\ndef bar():\n    pass\n"
        )
        source = SourceInput(input_type="local_path", value=str(tmp_path))
        model = ingest(source)
        sf = model.files[0]
        assert len(sf.imports) == 2
        assert "Foo" in sf.public_interfaces
        assert "bar" in sf.public_interfaces

    def test_module_boundaries_created(self, tmp_path):
        sub = tmp_path / "pkg"
        sub.mkdir()
        (sub / "a.py").write_text("pass")
        (tmp_path / "main.py").write_text("pass")
        source = SourceInput(input_type="local_path", value=str(tmp_path))
        model = ingest(source)
        assert len(model.module_boundaries) >= 2

    def test_mixed_languages(self, tmp_path):
        (tmp_path / "app.py").write_text("pass")
        (tmp_path / "index.js").write_text("const x = 1;")
        (tmp_path / "Main.java").write_text("public class Main {}")
        source = SourceInput(input_type="local_path", value=str(tmp_path))
        model = ingest(source)
        langs = {f.language for f in model.files}
        assert langs == {"python", "javascript", "java"}


# ---------------------------------------------------------------------------
# ingest – GitHub URL (mocked)
# ---------------------------------------------------------------------------

class TestIngestGitHub:
    def test_invalid_url_raises_input_error(self):
        source = SourceInput(input_type="github_url", value="not-a-url")
        with pytest.raises(InputError, match="Invalid GitHub URL"):
            ingest(source)

    def test_malformed_github_url_raises_input_error(self):
        source = SourceInput(input_type="github_url", value="https://gitlab.com/user/repo")
        with pytest.raises(InputError, match="Invalid GitHub URL"):
            ingest(source)

    @patch("app.code_ingester.subprocess.run")
    @patch("app.code_ingester.tempfile.mkdtemp")
    def test_clone_failure_raises_git_error(self, mock_mkdtemp, mock_run, tmp_path):
        mock_mkdtemp.return_value = str(tmp_path / "clone_dir")
        os.makedirs(str(tmp_path / "clone_dir"), exist_ok=True)
        mock_run.return_value = MagicMock(returncode=1, stderr="fatal: repo not found")

        source = SourceInput(
            input_type="github_url",
            value="https://github.com/user/repo",
        )
        with pytest.raises(GitError, match="Failed to clone"):
            ingest(source)

    @patch("app.code_ingester.subprocess.run")
    @patch("app.code_ingester.tempfile.mkdtemp")
    def test_successful_clone(self, mock_mkdtemp, mock_run, tmp_path):
        clone_dir = tmp_path / "cloned"
        clone_dir.mkdir()
        (clone_dir / "main.py").write_text("import os\n\ndef main():\n    pass\n")
        mock_mkdtemp.return_value = str(clone_dir)
        mock_run.return_value = MagicMock(returncode=0, stderr="")

        source = SourceInput(
            input_type="github_url",
            value="https://github.com/user/repo",
        )
        model = ingest(source)

        assert isinstance(model, CodebaseModel)
        assert model.root_path == "https://github.com/user/repo"
        assert len(model.files) >= 1

    @patch("app.code_ingester.subprocess.run")
    @patch("app.code_ingester.tempfile.mkdtemp")
    def test_git_not_found_raises_git_error(self, mock_mkdtemp, mock_run, tmp_path):
        mock_mkdtemp.return_value = str(tmp_path / "clone_dir")
        os.makedirs(str(tmp_path / "clone_dir"), exist_ok=True)
        mock_run.side_effect = FileNotFoundError("git not found")

        source = SourceInput(
            input_type="github_url",
            value="https://github.com/user/repo",
        )
        with pytest.raises(GitError, match="git CLI not found"):
            ingest(source)

    @patch("app.code_ingester.subprocess.run")
    @patch("app.code_ingester.tempfile.mkdtemp")
    def test_clone_timeout_raises_git_error(self, mock_mkdtemp, mock_run, tmp_path):
        mock_mkdtemp.return_value = str(tmp_path / "clone_dir")
        os.makedirs(str(tmp_path / "clone_dir"), exist_ok=True)
        mock_run.side_effect = subprocess.TimeoutExpired(cmd="git clone", timeout=120)

        source = SourceInput(
            input_type="github_url",
            value="https://github.com/user/repo",
        )
        with pytest.raises(GitError, match="timed out"):
            ingest(source)
