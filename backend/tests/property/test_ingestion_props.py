"""Property-based tests for invalid source input error reporting.

# Feature: architectural-reverse-engineer, Property 2: Invalid source input error reporting

**Validates: Requirements 1.3, 1.4**

For any invalid source input (non-existent local path, inaccessible path,
malformed GitHub URL, or unreachable URL), the Analyzer should return an error
result containing a descriptive message that identifies the nature of the problem.
"""

from __future__ import annotations

from hypothesis import given, settings, assume
from hypothesis import strategies as st

import pytest

from app.code_ingester import ingest
from app.errors import InputError, GitError
from app.models import SourceInput

# ---------------------------------------------------------------------------
# Strategies
# ---------------------------------------------------------------------------

# Generate random non-existent local paths: random strings that won't exist on disk.
# We use printable ASCII segments joined by '/' to form path-like strings,
# and prefix with a non-existent root to guarantee they don't resolve.
_nonexistent_path = st.from_regex(
    r"/tmp/__nonexistent_[a-z0-9]{4,12}/[a-z0-9_/]{1,30}", fullmatch=True
)

# Generate malformed GitHub URLs that do NOT match the expected pattern:
#   ^https?://github\.com/[\w.\-]+/[\w.\-]+(\.git)?(/.*)?$
# We produce URLs that violate this in various ways.
_malformed_github_url = st.one_of(
    # Random strings that aren't URLs at all
    st.from_regex(r"[a-z]{3,20}", fullmatch=True),
    # URLs to wrong hosts
    st.from_regex(r"https://gitlab\.com/[a-z]{2,10}/[a-z]{2,10}", fullmatch=True),
    st.from_regex(r"https://bitbucket\.org/[a-z]{2,10}/[a-z]{2,10}", fullmatch=True),
    # github.com but missing owner/repo segments
    st.just("https://github.com/"),
    st.just("https://github.com"),
    st.from_regex(r"https://github\.com/[a-z]{2,10}", fullmatch=True),
    # Completely invalid schemes
    st.from_regex(r"ftp://github\.com/[a-z]{2,10}/[a-z]{2,10}", fullmatch=True),
)


# ---------------------------------------------------------------------------
# Property 2: Invalid source input error reporting
# ---------------------------------------------------------------------------


@settings(max_examples=100, deadline=None)
@given(path=_nonexistent_path)
def test_nonexistent_local_path_raises_descriptive_error(path):
    """Non-existent local paths produce InputError with a descriptive message.

    # Feature: architectural-reverse-engineer, Property 2: Invalid source input error reporting
    **Validates: Requirements 1.3**
    """
    source = SourceInput(input_type="local_path", value=path)

    with pytest.raises(InputError) as exc_info:
        ingest(source)

    msg = str(exc_info.value)
    # The error message must be non-empty and descriptive
    assert len(msg) > 0, "Error message must not be empty"
    # It should reference the problematic path or describe the nature of the issue
    assert path in msg or "does not exist" in msg or "not a directory" in msg or "not accessible" in msg, (
        f"Error message should identify the problem; got: {msg}"
    )


@settings(max_examples=100, deadline=None)
@given(url=_malformed_github_url)
def test_malformed_github_url_raises_descriptive_error(url):
    """Malformed GitHub URLs produce InputError with a descriptive message.

    # Feature: architectural-reverse-engineer, Property 2: Invalid source input error reporting
    **Validates: Requirements 1.4**
    """
    source = SourceInput(input_type="github_url", value=url)

    with pytest.raises(InputError) as exc_info:
        ingest(source)

    msg = str(exc_info.value)
    # The error message must be non-empty and descriptive
    assert len(msg) > 0, "Error message must not be empty"
    # It should reference the URL or describe the nature of the issue
    assert url in msg or "Invalid GitHub URL" in msg or "malformed" in msg.lower(), (
        f"Error message should identify the problem; got: {msg}"
    )
