"""Property-based tests for source file parsing completeness.

# Feature: architectural-reverse-engineer, Property 3: Source file parsing completeness

**Validates: Requirements 1.5**

For any set of identified source code files, the Analyzer should produce a
CodebaseModel where every file has a corresponding entry with non-empty file
structure, and all import/export relationships present in the source are captured.
"""

from __future__ import annotations

import os
from pathlib import Path

from hypothesis import given, settings, assume
from hypothesis import strategies as st

from app.code_ingester import ingest
from app.models import SourceInput

# ---------------------------------------------------------------------------
# Strategies
# ---------------------------------------------------------------------------

# Safe Python identifier names for modules, classes, and functions
_identifier = st.from_regex(r"[a-z][a-z0-9_]{1,10}", fullmatch=True)

# Generate a list of "import X" statements
_simple_import = _identifier.map(lambda name: f"import {name}")

# Generate a list of "from X import Y" statements
_from_import = st.tuples(_identifier, _identifier).map(
    lambda pair: f"from {pair[0]} import {pair[1]}"
)

_import_statement = st.one_of(_simple_import, _from_import)

# Generate a public class definition (top-level, no leading underscore)
_public_class = _identifier.filter(lambda n: not n.startswith("_")).map(
    lambda name: f"class {name}:\n    pass"
)

# Generate a public function definition (top-level, no leading underscore)
_public_function = _identifier.filter(lambda n: not n.startswith("_")).map(
    lambda name: f"def {name}():\n    pass"
)

_public_definition = st.one_of(_public_class, _public_function)

# Safe directory segment names
_dir_name = st.from_regex(r"[a-z][a-z0-9_]{0,7}", fullmatch=True)


@st.composite
def python_source_file(draw: st.DrawFn):
    """Generate a Python source file with known imports and public definitions.

    Returns (imports, public_names, file_content) where:
    - imports: list of import statement strings
    - public_names: list of public class/function names
    - file_content: the full file text
    """
    imports = draw(st.lists(_import_statement, min_size=0, max_size=5))
    definitions = draw(st.lists(_public_definition, min_size=0, max_size=5))

    # Extract the public names from definitions
    public_names: list[str] = []
    for defn in definitions:
        # "class Foo:\n    pass" -> "Foo"  or  "def bar():\n    pass" -> "bar"
        first_line = defn.split("\n")[0]
        if first_line.startswith("class "):
            name = first_line.split()[1].rstrip(":")
        else:
            name = first_line.split("(")[0].split()[1]
        public_names.append(name)

    # Deduplicate names (keep order) to avoid redefinition confusion
    seen: set[str] = set()
    unique_definitions: list[str] = []
    unique_public_names: list[str] = []
    for defn, name in zip(definitions, public_names):
        if name not in seen:
            seen.add(name)
            unique_definitions.append(defn)
            unique_public_names.append(name)

    lines = imports + [""] + unique_definitions
    content = "\n".join(lines) + "\n"
    return imports, unique_public_names, content


@st.composite
def python_project(draw: st.DrawFn):
    """Generate a small Python project with 1-5 source files.

    Returns a list of (relative_dir_parts, filename, imports, public_names, content).
    """
    num_files = draw(st.integers(min_value=1, max_value=5))
    files = []
    used_paths: set[str] = set()

    for i in range(num_files):
        dir_parts = draw(st.lists(_dir_name, min_size=0, max_size=2))
        imports, public_names, content = draw(python_source_file())
        fname = f"mod_{i}.py"
        rel_path = os.path.join(*dir_parts, fname) if dir_parts else fname
        # Ensure unique paths
        if rel_path in used_paths:
            continue
        used_paths.add(rel_path)
        files.append((dir_parts, fname, imports, public_names, content))

    assume(len(files) >= 1)
    return files


def _create_project(tmp_dir: Path, files):
    """Write generated files to disk. Returns dict mapping abs path -> (imports, public_names)."""
    file_info: dict[str, tuple[list[str], list[str]]] = {}
    for dir_parts, fname, imports, public_names, content in files:
        target_dir = tmp_dir
        for part in dir_parts:
            target_dir = target_dir / part
        target_dir.mkdir(parents=True, exist_ok=True)
        fpath = target_dir / fname
        fpath.write_text(content)
        file_info[str(fpath)] = (imports, public_names)
    return file_info


# ---------------------------------------------------------------------------
# Property 3: Source file parsing completeness
# ---------------------------------------------------------------------------


@settings(max_examples=100, deadline=None)
@given(project=python_project())
def test_source_file_parsing_completeness(tmp_path_factory, project):
    """Every Python source file is parsed with correct language, imports, and public interfaces.

    # Feature: architectural-reverse-engineer, Property 3: Source file parsing completeness
    **Validates: Requirements 1.5**
    """
    tmp_dir = tmp_path_factory.mktemp("proj")
    file_info = _create_project(tmp_dir, project)

    result = ingest(SourceInput(input_type="local_path", value=str(tmp_dir)))

    discovered_paths = {sf.path for sf in result.files}

    # 1. Every source file has a corresponding SourceFile entry
    for expected_path in file_info:
        assert expected_path in discovered_paths, (
            f"File {expected_path} not found in CodebaseModel.files"
        )

    # Check per-file properties
    for sf in result.files:
        if sf.path not in file_info:
            continue  # skip any unexpected files (shouldn't happen)

        expected_imports, expected_public_names = file_info[sf.path]

        # 2. Correct language detected
        assert sf.language == "python", (
            f"Expected language 'python' for {sf.path}, got '{sf.language}'"
        )

        # 3. All import statements are captured
        for imp in expected_imports:
            assert imp in sf.imports, (
                f"Import '{imp}' not found in parsed imports for {sf.path}.\n"
                f"  Parsed imports: {sf.imports}"
            )

        # 4. All public class/function names are captured
        for name in expected_public_names:
            assert name in sf.public_interfaces, (
                f"Public interface '{name}' not found in parsed public_interfaces for {sf.path}.\n"
                f"  Parsed public_interfaces: {sf.public_interfaces}"
            )
