"""Unit tests for the Document Generator – ADR and Markdown generation."""

from __future__ import annotations

import pytest

from app.document_generator import (
    adr_to_markdown,
    generate_adrs,
    generate_markdown,
)
from app.models import (
    ADR,
    ClassifiedElement,
    DiagramOutput,
    Element,
    ReconciledModel,
    Relationship,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _element(
    name: str,
    element_type: str = "service",
    leanix_type: str = "IT Component",
) -> ClassifiedElement:
    return ClassifiedElement(
        element=Element(name=name, element_type=element_type, metadata={}),
        leanix_type=leanix_type,
        confidence=0.9,
    )


def _dep(source: str, target: str) -> Relationship:
    return Relationship(source=source, target=target, relationship_type="depends_on")


def _rel(source: str, target: str, rel_type: str = "REST") -> Relationship:
    return Relationship(source=source, target=target, relationship_type=rel_type)


def _model(
    elements: list[ClassifiedElement] | None = None,
    relationships: list[Relationship] | None = None,
    patterns: list[str] | None = None,
    layers: list[str] | None = None,
) -> ReconciledModel:
    return ReconciledModel(
        elements=elements or [],
        relationships=relationships or [],
        patterns=patterns or [],
        layers=layers or [],
    )


# ---------------------------------------------------------------------------
# generate_adrs – basic generation
# ---------------------------------------------------------------------------


class TestGenerateADRs:
    def test_adrs_from_patterns(self):
        model = _model(patterns=["microservices", "event-driven"])
        adrs = generate_adrs(model)
        assert len(adrs) == 2
        titles = {a.title for a in adrs}
        assert "Use Microservices Architecture" in titles
        assert "Use Event-Driven Architecture" in titles

    def test_adrs_from_layers(self):
        model = _model(layers=["presentation", "data access"])
        adrs = generate_adrs(model)
        assert len(adrs) == 2
        titles = {a.title for a in adrs}
        assert "Separate Presentation Layer" in titles
        assert "Separate Data Access Layer" in titles

    def test_adrs_from_element_types(self):
        model = _model(elements=[
            _element("MyDB", "database"),
            _element("MyGW", "gateway"),
        ])
        adrs = generate_adrs(model)
        titles = {a.title for a in adrs}
        assert "Use Dedicated Database Component" in titles
        assert "Use API Gateway" in titles

    def test_all_adrs_have_five_sections(self):
        model = _model(
            patterns=["microservices"],
            layers=["presentation"],
            elements=[_element("Q", "queue")],
        )
        adrs = generate_adrs(model)
        assert len(adrs) >= 1
        for adr in adrs:
            assert adr.title
            assert adr.status
            assert adr.context
            assert adr.decision
            assert adr.consequences

    def test_empty_model_produces_no_adrs(self):
        model = _model()
        adrs = generate_adrs(model)
        assert adrs == []

    def test_unknown_pattern_ignored(self):
        model = _model(patterns=["some_unknown_pattern"])
        adrs = generate_adrs(model)
        assert adrs == []

    def test_status_is_proposed(self):
        model = _model(patterns=["layered"])
        adrs = generate_adrs(model)
        assert all(a.status == "Proposed" for a in adrs)


# ---------------------------------------------------------------------------
# generate_adrs – deduplication
# ---------------------------------------------------------------------------


class TestADRDeduplication:
    def test_dedup_against_existing(self):
        existing = [
            ADR(
                title="Use Microservices Architecture",
                status="Accepted",
                context="c",
                decision="d",
                consequences="q",
            )
        ]
        model = _model(patterns=["microservices", "layered"])
        adrs = generate_adrs(model, existing_adrs=existing)
        titles = {a.title for a in adrs}
        assert "Use Microservices Architecture" not in titles
        assert "Use Layered Architecture" in titles

    def test_dedup_case_insensitive(self):
        existing = [
            ADR(
                title="use microservices architecture",
                status="Accepted",
                context="c",
                decision="d",
                consequences="q",
            )
        ]
        model = _model(patterns=["microservices"])
        adrs = generate_adrs(model, existing_adrs=existing)
        assert len(adrs) == 0

    def test_no_internal_duplicates(self):
        """If the same pattern appears twice, only one ADR is generated."""
        model = _model(patterns=["microservices", "microservices architecture"])
        adrs = generate_adrs(model)
        titles = [a.title for a in adrs]
        assert titles.count("Use Microservices Architecture") == 1

    def test_none_existing_adrs(self):
        model = _model(patterns=["layered"])
        adrs = generate_adrs(model, existing_adrs=None)
        assert len(adrs) == 1


# ---------------------------------------------------------------------------
# adr_to_markdown
# ---------------------------------------------------------------------------


class TestADRToMarkdown:
    def test_contains_all_sections(self):
        adr = ADR(
            title="Test ADR",
            status="Proposed",
            context="Some context",
            decision="Some decision",
            consequences="Some consequences",
        )
        md = adr_to_markdown(adr)
        assert "# Test ADR" in md
        assert "## Status" in md
        assert "Proposed" in md
        assert "## Context" in md
        assert "Some context" in md
        assert "## Decision" in md
        assert "Some decision" in md
        assert "## Consequences" in md
        assert "Some consequences" in md


# ---------------------------------------------------------------------------
# generate_markdown – section completeness
# ---------------------------------------------------------------------------


class TestGenerateMarkdown:
    def test_contains_toc(self):
        model = _model()
        md = generate_markdown(model)
        assert "## Table of Contents" in md
        assert "[System Overview]" in md
        assert "[Component Descriptions]" in md
        assert "[Dependency Summary]" in md
        assert "[Interface Catalog]" in md

    def test_contains_all_four_sections(self):
        model = _model()
        md = generate_markdown(model)
        assert "## System Overview" in md
        assert "## Component Descriptions" in md
        assert "## Dependency Summary" in md
        assert "## Interface Catalog" in md

    def test_toc_links_are_anchors(self):
        model = _model()
        md = generate_markdown(model)
        assert "(#system-overview)" in md
        assert "(#component-descriptions)" in md
        assert "(#dependency-summary)" in md
        assert "(#interface-catalog)" in md

    def test_patterns_in_overview(self):
        model = _model(patterns=["microservices", "layered"])
        md = generate_markdown(model)
        assert "microservices" in md
        assert "layered" in md

    def test_layers_in_overview(self):
        model = _model(layers=["presentation", "data access"])
        md = generate_markdown(model)
        assert "presentation" in md
        assert "data access" in md

    def test_components_listed(self):
        model = _model(elements=[
            _element("OrderService", "service", "IT Component"),
            _element("UserDB", "database", "Data Object"),
        ])
        md = generate_markdown(model)
        assert "OrderService" in md
        assert "UserDB" in md
        assert "service" in md
        assert "database" in md

    def test_dependency_table(self):
        model = _model(
            elements=[_element("A"), _element("B")],
            relationships=[_dep("A", "B")],
        )
        md = generate_markdown(model)
        assert "| A | B | depends_on |" in md

    def test_interface_catalog_table(self):
        model = _model(
            elements=[_element("A"), _element("B")],
            relationships=[_rel("A", "B", "REST")],
        )
        md = generate_markdown(model)
        assert "| A | B | REST |" in md

    def test_diagrams_embedded(self):
        diag = DiagramOutput(
            diagram_type="dependency_graph",
            rendered_image=b"fake",
            image_format="png",
            structured_data={},
        )
        model = _model()
        md = generate_markdown(model, diagrams=[diag])
        assert "## Diagrams" in md
        assert "![Dependency Graph](dependency_graph.png)" in md

    def test_diagrams_section_in_toc_when_present(self):
        diag = DiagramOutput(
            diagram_type="component",
            rendered_image=b"fake",
            image_format="svg",
            structured_data={},
        )
        model = _model()
        md = generate_markdown(model, diagrams=[diag])
        assert "[Diagrams]" in md

    def test_no_diagrams_section_when_empty(self):
        model = _model()
        md = generate_markdown(model, diagrams=[])
        assert "## Diagrams" not in md

    def test_empty_model(self):
        model = _model()
        md = generate_markdown(model)
        assert "No architectural patterns detected." in md
        assert "No components identified." in md
