"""Property-based tests for Document Generator – ADR and Markdown generation.

Properties 15, 16, and 18 from the design document.
"""

from __future__ import annotations

from hypothesis import given, settings, assume
from hypothesis import strategies as st

from app.document_generator import adr_to_markdown, generate_adrs, generate_markdown
from app.models import (
    ADR,
    ClassifiedElement,
    DiagramOutput,
    Element,
    ReconciledModel,
    Relationship,
)


# ---------------------------------------------------------------------------
# Strategies
# ---------------------------------------------------------------------------

# Known patterns that produce ADRs
_KNOWN_PATTERNS = [
    "microservices",
    "layered",
    "event-driven",
    "monolithic",
    "hexagonal",
]

# Known layers that produce ADRs
_KNOWN_LAYERS = [
    "presentation",
    "data access",
]

# Known element types that produce ADRs
_KNOWN_ELEMENT_TYPES = [
    "database",
    "gateway",
    "queue",
]

# All element types (including ones that don't produce ADRs)
_ALL_ELEMENT_TYPES = [
    "service",
    "class",
    "module",
    "interface",
    "database",
    "gateway",
    "queue",
]

_RELATIONSHIP_TYPES = [
    "depends_on",
    "calls",
    "REST",
    "gRPC",
    "event",
    "implements",
    "inherits",
]

_LEANIX_TYPES = [
    "Organization",
    "Interface",
    "Data Object",
    "IT Component",
    "unclassified",
]

_DIAGRAM_TYPES = [
    "dependency_graph",
    "component",
    "uml_class",
    "uml_sequence",
    "lld",
]


def _element_strategy() -> st.SearchStrategy[ClassifiedElement]:
    return st.builds(
        ClassifiedElement,
        element=st.builds(
            Element,
            name=st.text(
                alphabet=st.characters(min_codepoint=65, max_codepoint=90),
                min_size=1,
                max_size=10,
            ),
            element_type=st.sampled_from(_ALL_ELEMENT_TYPES),
            metadata=st.just({}),
        ),
        leanix_type=st.sampled_from(_LEANIX_TYPES),
        confidence=st.floats(min_value=0.0, max_value=1.0),
        alternative_types=st.just([]),
        evidence=st.just([]),
    )


def _relationship_strategy() -> st.SearchStrategy[Relationship]:
    return st.builds(
        Relationship,
        source=st.text(
            alphabet=st.characters(min_codepoint=65, max_codepoint=90),
            min_size=1,
            max_size=10,
        ),
        target=st.text(
            alphabet=st.characters(min_codepoint=65, max_codepoint=90),
            min_size=1,
            max_size=10,
        ),
        relationship_type=st.sampled_from(_RELATIONSHIP_TYPES),
    )


def _reconciled_model_strategy() -> st.SearchStrategy[ReconciledModel]:
    """Generate a ReconciledModel with at least one pattern that produces ADRs."""
    return st.builds(
        ReconciledModel,
        elements=st.lists(_element_strategy(), min_size=0, max_size=5),
        relationships=st.lists(_relationship_strategy(), min_size=0, max_size=5),
        patterns=st.lists(
            st.sampled_from(_KNOWN_PATTERNS),
            min_size=1,
            max_size=3,
            unique=True,
        ),
        layers=st.lists(
            st.sampled_from(_KNOWN_LAYERS),
            min_size=0,
            max_size=2,
            unique=True,
        ),
        discrepancies=st.lists(
            st.text(min_size=1, max_size=30),
            min_size=0,
            max_size=2,
        ),
    )


def _adr_strategy() -> st.SearchStrategy[ADR]:
    return st.builds(
        ADR,
        title=st.text(
            alphabet=st.characters(min_codepoint=32, max_codepoint=126),
            min_size=3,
            max_size=50,
        ).filter(lambda s: s.strip()),
        status=st.sampled_from(["Proposed", "Accepted", "Deprecated", "Superseded"]),
        context=st.text(min_size=3, max_size=80).filter(lambda s: s.strip()),
        decision=st.text(min_size=3, max_size=80).filter(lambda s: s.strip()),
        consequences=st.text(min_size=3, max_size=80).filter(lambda s: s.strip()),
    )


def _diagram_output_strategy() -> st.SearchStrategy[DiagramOutput]:
    return st.builds(
        DiagramOutput,
        diagram_type=st.sampled_from(_DIAGRAM_TYPES),
        rendered_image=st.binary(min_size=1, max_size=20),
        image_format=st.sampled_from(["png", "svg"]),
        structured_data=st.just({}),
        source_file=st.none(),
    )


# ---------------------------------------------------------------------------
# Property 15: ADR structural completeness
# ---------------------------------------------------------------------------
# Feature: architectural-reverse-engineer, Property 15: ADR structural completeness
#
# **Validates: Requirements 8.1, 8.2, 8.3**
#
# For any generated ADR, the output should be valid Markdown containing all
# five required sections: Title, Status, Context, Decision, and Consequences.
# ---------------------------------------------------------------------------


@settings(max_examples=100, deadline=None)
@given(model=_reconciled_model_strategy())
def test_adr_structural_completeness(model: ReconciledModel):
    """Every generated ADR has all five required sections in Markdown.

    # Feature: architectural-reverse-engineer, Property 15: ADR structural completeness
    **Validates: Requirements 8.1, 8.2, 8.3**
    """
    adrs = generate_adrs(model)

    # Model has at least one known pattern, so we expect at least one ADR
    assert len(adrs) >= 1, (
        f"Expected at least 1 ADR from patterns={model.patterns}, got 0"
    )

    for adr in adrs:
        # Check the ADR model fields are non-empty
        assert adr.title.strip(), "ADR title must be non-empty"
        assert adr.status.strip(), "ADR status must be non-empty"
        assert adr.context.strip(), "ADR context must be non-empty"
        assert adr.decision.strip(), "ADR decision must be non-empty"
        assert adr.consequences.strip(), "ADR consequences must be non-empty"

        # Check the Markdown rendering contains all five sections
        md = adr_to_markdown(adr)
        assert f"# {adr.title}" in md, "Markdown missing Title section"
        assert "## Status" in md, "Markdown missing Status section"
        assert "## Context" in md, "Markdown missing Context section"
        assert "## Decision" in md, "Markdown missing Decision section"
        assert "## Consequences" in md, "Markdown missing Consequences section"

        # Verify it's valid Markdown (contains the actual content)
        assert adr.status in md
        assert adr.context in md
        assert adr.decision in md
        assert adr.consequences in md


# ---------------------------------------------------------------------------
# Property 16: ADR deduplication against existing set
# ---------------------------------------------------------------------------
# Feature: architectural-reverse-engineer, Property 16: ADR deduplication against existing set
#
# **Validates: Requirements 8.4**
#
# For any set of existing ADRs and a set of newly detected architectural
# decisions, the Document Generator should produce ADRs only for decisions
# not already covered by the existing set. The intersection of existing ADR
# topics and newly generated ADR topics should be empty.
# ---------------------------------------------------------------------------


@settings(max_examples=100, deadline=None)
@given(
    model=_reconciled_model_strategy(),
    existing_adrs=st.lists(_adr_strategy(), min_size=1, max_size=5),
)
def test_adr_deduplication_against_existing_set(
    model: ReconciledModel,
    existing_adrs: list[ADR],
):
    """Newly generated ADR titles never overlap with existing ADR titles.

    # Feature: architectural-reverse-engineer, Property 16: ADR deduplication against existing set
    **Validates: Requirements 8.4**
    """
    new_adrs = generate_adrs(model, existing_adrs=existing_adrs)

    existing_titles = {adr.title.strip().lower() for adr in existing_adrs}
    new_titles = {adr.title.strip().lower() for adr in new_adrs}

    overlap = existing_titles & new_titles
    assert overlap == set(), (
        f"Generated ADRs overlap with existing ADRs.\n"
        f"  Overlapping titles: {overlap}\n"
        f"  Existing: {existing_titles}\n"
        f"  New: {new_titles}"
    )


# ---------------------------------------------------------------------------
# Property 18: Markdown documentation section completeness
# ---------------------------------------------------------------------------
# Feature: architectural-reverse-engineer, Property 18: Markdown documentation section completeness
#
# **Validates: Requirements 10.1, 10.2, 10.3**
#
# For any generated Markdown document, it should contain a table of contents
# and all four required sections (system overview, component descriptions,
# dependency summary, interface catalog), with the TOC containing links that
# correspond to each section. Every generated diagram should be embedded or
# linked within the document.
# ---------------------------------------------------------------------------


@settings(max_examples=100, deadline=None)
@given(
    model=st.builds(
        ReconciledModel,
        elements=st.lists(_element_strategy(), min_size=0, max_size=5),
        relationships=st.lists(_relationship_strategy(), min_size=0, max_size=5),
        patterns=st.lists(
            st.text(min_size=1, max_size=20).filter(lambda s: s.strip()),
            min_size=0,
            max_size=3,
        ),
        layers=st.lists(
            st.text(min_size=1, max_size=20).filter(lambda s: s.strip()),
            min_size=0,
            max_size=3,
        ),
        discrepancies=st.lists(
            st.text(min_size=1, max_size=30).filter(lambda s: s.strip()),
            min_size=0,
            max_size=2,
        ),
    ),
    diagrams=st.lists(_diagram_output_strategy(), min_size=0, max_size=4),
)
def test_markdown_documentation_section_completeness(
    model: ReconciledModel,
    diagrams: list[DiagramOutput],
):
    """Markdown doc has TOC, all four sections, and all diagrams embedded.

    # Feature: architectural-reverse-engineer, Property 18: Markdown documentation section completeness
    **Validates: Requirements 10.1, 10.2, 10.3**
    """
    md = generate_markdown(model, diagrams=diagrams)

    # 1. Table of contents exists
    assert "## Table of Contents" in md, "Missing Table of Contents"

    # 2. All four required sections exist
    required_sections = [
        "System Overview",
        "Component Descriptions",
        "Dependency Summary",
        "Interface Catalog",
    ]
    for section in required_sections:
        assert f"## {section}" in md, f"Missing section: {section}"

    # 3. TOC contains links to each required section
    for section in required_sections:
        assert f"[{section}]" in md, f"TOC missing link for: {section}"

    # 4. Every diagram is embedded or linked
    for diag in diagrams:
        label = diag.diagram_type.replace("_", " ").title()
        filename = f"{diag.diagram_type}.{diag.image_format}"
        assert filename in md, (
            f"Diagram '{diag.diagram_type}' not embedded in Markdown.\n"
            f"  Expected filename: {filename}"
        )
