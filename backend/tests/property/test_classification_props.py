"""Property-based tests for LeanIX classification validity.

# Feature: architectural-reverse-engineer, Property 7: LeanIX classification validity

**Validates: Requirements 3.4, 3.5, 9.1**

For any list of discovered architectural elements, every classified element should
have a `leanix_type` that is one of: "Organization", "Interface", "Data Object",
"IT Component", or a recognized custom LeanIX type. Elements with confidence below
the threshold should be flagged as "unclassified".
"""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

from hypothesis import given, settings
from hypothesis import strategies as st

from app.ai_engine import AIEngine, CONFIDENCE_THRESHOLD, VALID_LEANIX_TYPES
from app.models import ClassifiedElement, Element


# ---------------------------------------------------------------------------
# Valid types set (includes "unclassified" for low-confidence elements)
# ---------------------------------------------------------------------------

ALLOWED_LEANIX_TYPES = set(VALID_LEANIX_TYPES) | {"unclassified"}

# ---------------------------------------------------------------------------
# Strategies
# ---------------------------------------------------------------------------

_element_name = st.text(
    alphabet=st.characters(whitelist_categories=("L", "N", "Pd")),
    min_size=1,
    max_size=30,
)

_element_type = st.sampled_from(
    ["service", "class", "module", "interface", "database", "component", "library"]
)

_element_strategy = st.builds(
    Element,
    name=_element_name,
    element_type=_element_type,
    metadata=st.just({}),
)

_elements_list = st.lists(_element_strategy, min_size=1, max_size=10)

# Confidence scores spanning the full range, including around the threshold
_confidence = st.floats(min_value=0.0, max_value=1.0, allow_nan=False)

# LeanIX types the mock AI might return (valid + some edge cases)
_mock_leanix_type = st.sampled_from(
    ["Organization", "Interface", "Data Object", "IT Component"]
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _build_mock_response(elements: list[Element], confidences: list[float], types: list[str]) -> str:
    """Build a JSON string mimicking the OpenAI classification response."""
    classified = []
    for elem, conf, ltype in zip(elements, confidences, types):
        classified.append({
            "element": {
                "name": elem.name,
                "element_type": elem.element_type,
                "metadata": {},
            },
            "leanix_type": ltype,
            "confidence": conf,
            "alternative_types": [],
            "evidence": ["auto-generated evidence"],
        })
    return json.dumps({"classified": classified})


def _make_engine_with_mock(mock_response: str) -> AIEngine:
    """Create an AIEngine with a mocked OpenAI client returning mock_response."""
    with patch("app.ai_engine.openai.OpenAI"):
        engine = AIEngine(api_key="test-key")

    mock_client = MagicMock()
    mock_resp = MagicMock()
    mock_resp.choices = [MagicMock()]
    mock_resp.choices[0].message.content = mock_response
    mock_client.chat.completions.create.return_value = mock_resp
    engine._client = mock_client
    return engine


# ---------------------------------------------------------------------------
# Property 7: LeanIX classification validity
# ---------------------------------------------------------------------------


@settings(max_examples=100, deadline=None)
@given(
    elements=_elements_list,
    data=st.data(),
)
def test_classified_elements_have_valid_leanix_types(elements, data):
    """Every classified element has a valid leanix_type or is 'unclassified'.

    # Feature: architectural-reverse-engineer, Property 7: LeanIX classification validity
    **Validates: Requirements 3.4, 3.5, 9.1**
    """
    # Generate a confidence and type for each element
    confidences = [data.draw(_confidence) for _ in elements]
    types = [data.draw(_mock_leanix_type) for _ in elements]

    mock_response = _build_mock_response(elements, confidences, types)
    engine = _make_engine_with_mock(mock_response)

    result = engine.classify_elements(elements)

    assert len(result) == len(elements)

    for classified_elem in result:
        assert isinstance(classified_elem, ClassifiedElement)
        # Every element must have a valid leanix_type
        assert classified_elem.leanix_type in ALLOWED_LEANIX_TYPES, (
            f"leanix_type '{classified_elem.leanix_type}' is not in {ALLOWED_LEANIX_TYPES}"
        )


@settings(max_examples=100, deadline=None)
@given(
    elements=_elements_list,
    data=st.data(),
)
def test_low_confidence_elements_flagged_unclassified(elements, data):
    """Elements with confidence < CONFIDENCE_THRESHOLD are flagged as 'unclassified'.

    # Feature: architectural-reverse-engineer, Property 7: LeanIX classification validity
    **Validates: Requirements 3.4, 3.5, 9.1**
    """
    # Generate confidences — mix of below and above threshold
    confidences = [data.draw(_confidence) for _ in elements]
    types = [data.draw(_mock_leanix_type) for _ in elements]

    mock_response = _build_mock_response(elements, confidences, types)
    engine = _make_engine_with_mock(mock_response)

    result = engine.classify_elements(elements)

    assert len(result) == len(elements)

    for classified_elem in result:
        if classified_elem.confidence < CONFIDENCE_THRESHOLD:
            assert classified_elem.leanix_type == "unclassified", (
                f"Element '{classified_elem.element.name}' has confidence "
                f"{classified_elem.confidence} (< {CONFIDENCE_THRESHOLD}) "
                f"but leanix_type is '{classified_elem.leanix_type}' instead of 'unclassified'"
            )
