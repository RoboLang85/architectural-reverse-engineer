"""Property-based tests for recursive file discovery completeness.

# Feature: architectural-reverse-engineer, Property 1: Recursive file discovery completeness

**Validates: Requirements 1.1**

For any valid local directory tree containing source code files at arbitrary
nesting depths, the Code Ingester should return a set of identified source files
that exactly matches the set of actual source code files in the directory tree.
"""

from __future__ import annotations

import os
from pathlib import Path

from hypothesis import given, settings, assume
from hypothesis import strategies as st

from app.code_ingester import EXTENSION_LANGUAGE_MAP, SKIP_DIRS, ingest
from app.models import SourceInput

# ---------------------------------------------------------------------------
# Strategies
# ---------------------------------------------------------------------------

# Source extensions that the ingester recognises
_SOURCE_EXTENSIONS = list(EXTENSION_LANGUAGE_MAP.keys())

# Non-source extensions that must NOT be discovered
_NON_SOURCE_EXTENSIONS = [".md", ".txt", ".csv", ".json", ".xml", ".yaml", ".yml",
                          ".toml", ".ini", ".cfg", ".log", ".png", ".jpg", ".svg",
                          ".gif", ".pdf", ".docx", ".zip", ".tar"]

# Safe directory name characters (avoid OS-problematic chars)
_dir_name = st.from_regex(r"[a-z][a-z0-9_]{0,7}", fullmatch=True).filter(
    lambda n: n not in SKIP_DIRS
)

_skip_dir_name = st.sampled_from(sorted(SKIP_DIRS))

# A single file entry: (relative_parts, extension)
# relative_parts is a list of directory segments (0 = root-level file)
_file_entry = st.tuples(
    st.lists(_dir_name, min_size=0, max_size=4),  # nesting depth 0-4
    st.sampled_from(_SOURCE_EXTENSIONS),
)

_non_source_entry = st.tuples(
    st.lists(_dir_name, min_size=0, max_size=4),
    st.sampled_from(_NON_SOURCE_EXTENSIONS),
)

_skip_dir_entry = st.tuples(
    _skip_dir_name,
    st.sampled_from(_SOURCE_EXTENSIONS),
)


@st.composite
def directory_tree(draw: st.DrawFn):
    """Generate a random directory tree description.

    Returns (source_entries, non_source_entries, skip_dir_entries) where each
    entry is (dir_parts, extension).
    """
    source_entries = draw(st.lists(_file_entry, min_size=1, max_size=15))
    non_source_entries = draw(st.lists(_non_source_entry, min_size=0, max_size=5))
    skip_dir_entries = draw(st.lists(_skip_dir_entry, min_size=0, max_size=3))
    return source_entries, non_source_entries, skip_dir_entries


def _create_tree(tmp_dir: Path, source_entries, non_source_entries, skip_dir_entries):
    """Materialise the generated tree on disk. Returns the set of expected source paths."""
    expected_source_paths: set[str] = set()
    counter = 0

    for dir_parts, ext in source_entries:
        target_dir = tmp_dir
        for part in dir_parts:
            target_dir = target_dir / part
        target_dir.mkdir(parents=True, exist_ok=True)
        fname = f"file_{counter}{ext}"
        fpath = target_dir / fname
        fpath.write_text(f"// source {counter}")
        expected_source_paths.add(str(fpath))
        counter += 1

    for dir_parts, ext in non_source_entries:
        target_dir = tmp_dir
        for part in dir_parts:
            target_dir = target_dir / part
        target_dir.mkdir(parents=True, exist_ok=True)
        fname = f"nonsrc_{counter}{ext}"
        fpath = target_dir / fname
        fpath.write_text(f"non-source {counter}")
        counter += 1

    for skip_name, ext in skip_dir_entries:
        skip_dir = tmp_dir / skip_name
        skip_dir.mkdir(parents=True, exist_ok=True)
        fname = f"hidden_{counter}{ext}"
        fpath = skip_dir / fname
        fpath.write_text(f"hidden {counter}")
        counter += 1

    return expected_source_paths


# ---------------------------------------------------------------------------
# Property 1: Recursive file discovery completeness
# ---------------------------------------------------------------------------


@settings(max_examples=100, deadline=None)
@given(tree=directory_tree())
def test_file_discovery_completeness(tmp_path_factory, tree):
    """The set of discovered source files exactly matches the actual source files.

    # Feature: architectural-reverse-engineer, Property 1: Recursive file discovery completeness
    **Validates: Requirements 1.1**
    """
    source_entries, non_source_entries, skip_dir_entries = tree
    tmp_dir = tmp_path_factory.mktemp("tree")

    expected = _create_tree(tmp_dir, source_entries, non_source_entries, skip_dir_entries)

    result = ingest(SourceInput(input_type="local_path", value=str(tmp_dir)))

    discovered = {sf.path for sf in result.files}
    assert discovered == expected, (
        f"Mismatch!\n"
        f"  Missing (expected but not found): {expected - discovered}\n"
        f"  Extra   (found but not expected): {discovered - expected}"
    )
