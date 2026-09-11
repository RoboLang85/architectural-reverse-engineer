"""Property-based tests for LeanIX mapping report completeness.

# Feature: architectural-reverse-engineer, Property 17: LeanIX mapping report completeness

**Validates: Requirements 9.2, 9.3, 9.4**

For any set of classified elements, the LeanIX mapping report should contain an
entry for every element with its classification, non-empty evidence, and
relationship mappings. Elements with multiple applicable types should list them
in descending order of confidence score.
"""

from __future__ import annotations

from hypothesis import given, settings
from hypothesis import strategies as st

from app.leanix_mapper import map as leanix_map
from app.models import ClassifiedElement, Element


# ---------------------------------------------------------------------------
# Strategies
# ---------------------------------------------------------------------------

_LEANIX_TYPES = ["Organization", "Interface", "Data Object", "IT Component"]

_element_name = st.text(
    alphabet=st.characters(whitelist_categories=("L", "N", "Pd")),
    min_size=1,
    max_size=30,
)

_element_type = st.sampled_from(
    ["service", "class", "module", "interface", "database", "component", "library"]
)

_confidence = st.floats(min_value=0.0, max_value=1.0, allow_nan=False)

_leanix_type = st.sampled_from(_LEANIX_TYPES)

_evidence_item = st.text(
    alphabet=st.characters(whitelist_categories=("L", "N", "Zs", "Pd")),
    min_size=1,
    max_size=60,
)

_alternative_type = st.fixed_dictionaries({
    "type": _leanix_type,
    "confidence": _confidence,
})

_classified_element = st.builds(
    ClassifiedElement,
    element=st.builds(
        Element,
        name=_element_name,
        element_type=_element_type,
        metadata=st.just({}),
    ),
    leanix_type=_leanix_type,
    confidence=_confidence,
    alternative_types=st.lists(_alternative_type, min_size=0, max_size=4),
    evidence=st.lists(_evidence_item, min_size=1, max_size=5),
)

_classified_elements_list = st.lists(_classified_element, min_size=1, max_size=10)


# ---------------------------------------------------------------------------
# Property 17: LeanIX mapping report completeness
# ---------------------------------------------------------------------------


@settings(max_examples=100, deadline=None)
@given(elements=_classified_elements_list)
def test_report_has_one_mapping_per_element(elements: list[ClassifiedElement]):
    """The report contains exactly one mapping per input element.

    # Feature: architectural-reverse-engineer, Property 17: LeanIX mapping report completeness
    **Validates: Requirements 9.2, 9.3, 9.4**
    """
    report = leanix_map(elements)

    assert len(report.mappings) == len(elements)


@settings(max_examples=100, deadline=None)
@given(elements=_classified_elements_list)
def test_each_mapping_has_correct_element_name(elements: list[ClassifiedElement]):
    """Each mapping's element_name matches the corresponding input element.

    # Feature: architectural-reverse-engineer, Property 17: LeanIX mapping report completeness
    **Validates: Requirements 9.2, 9.3, 9.4**
    """
    report = leanix_map(elements)

    for elem, mapping in zip(elements, report.mappings):
        assert mapping.element_name == elem.element.name


@settings(max_examples=100, deadline=None)
@given(elements=_classified_elements_list)
def test_each_mapping_has_non_empty_leanix_types(elements: list[ClassifiedElement]):
    """Each mapping has at least one leanix_type entry (the primary type).

    # Feature: architectural-reverse-engineer, Property 17: LeanIX mapping report completeness
    **Validates: Requirements 9.2, 9.3, 9.4**
    """
    report = leanix_map(elements)

    for mapping in report.mappings:
        assert len(mapping.leanix_types) >= 1, (
            f"Mapping for '{mapping.element_name}' has empty leanix_types"
        )


@settings(max_examples=100, deadline=None)
@given(elements=_classified_elements_list)
def test_leanix_types_sorted_descending_by_confidence(elements: list[ClassifiedElement]):
    """leanix_types are sorted in descending order of confidence score.

    # Feature: architectural-reverse-engineer, Property 17: LeanIX mapping report completeness
    **Validates: Requirements 9.2, 9.3, 9.4**
    """
    report = leanix_map(elements)

    for mapping in report.mappings:
        confidences = [t["confidence"] for t in mapping.leanix_types]
        for i in range(len(confidences) - 1):
            assert confidences[i] >= confidences[i + 1], (
                f"Mapping '{mapping.element_name}' types not sorted descending: {confidences}"
            )


@settings(max_examples=100, deadline=None)
@given(elements=_classified_elements_list)
def test_evidence_preserved_from_input(elements: list[ClassifiedElement]):
    """Evidence from the input ClassifiedElement is preserved in the mapping.

    # Feature: architectural-reverse-engineer, Property 17: LeanIX mapping report completeness
    **Validates: Requirements 9.2, 9.3, 9.4**
    """
    report = leanix_map(elements)

    for elem, mapping in zip(elements, report.mappings):
        assert mapping.evidence == list(elem.evidence), (
            f"Evidence mismatch for '{mapping.element_name}': "
            f"expected {elem.evidence}, got {mapping.evidence}"
        )


@settings(max_examples=100, deadline=None)
@given(elements=_classified_elements_list)
def test_alternative_types_included_in_mapping(elements: list[ClassifiedElement]):
    """Elements with alternative_types have all types included in the mapping.

    # Feature: architectural-reverse-engineer, Property 17: LeanIX mapping report completeness
    **Validates: Requirements 9.2, 9.3, 9.4**
    """
    report = leanix_map(elements)

    for elem, mapping in zip(elements, report.mappings):
        # Collect expected types: primary + non-empty alternatives
        expected_types = {elem.leanix_type}
        for alt in elem.alternative_types:
            alt_type = alt.get("type", "")
            if alt_type:
                expected_types.add(alt_type)

        mapped_types = {t["type"] for t in mapping.leanix_types}

        assert expected_types <= mapped_types, (
            f"Mapping '{mapping.element_name}' missing types: "
            f"{expected_types - mapped_types}"
        )
