"""Unit tests for the LeanIX Mapper component."""

from __future__ import annotations

import pytest

from app.leanix_mapper import map, _build_ranked_types, _derive_relationships
from app.models import ClassifiedElement, Element, LeanIXMapping, LeanIXReport


# --- Helpers ---


def _ce(
    name: str,
    element_type: str = "service",
    leanix_type: str = "IT Component",
    confidence: float = 0.9,
    alternative_types: list[dict] | None = None,
    evidence: list[str] | None = None,
    metadata: dict | None = None,
) -> ClassifiedElement:
    """Shorthand factory for ClassifiedElement."""
    return ClassifiedElement(
        element=Element(name=name, element_type=element_type, metadata=metadata or {}),
        leanix_type=leanix_type,
        confidence=confidence,
        alternative_types=alternative_types or [],
        evidence=evidence or [],
    )


# --- map() tests ---


class TestMap:
    def test_empty_input_returns_empty_report(self):
        report = map([])
        assert isinstance(report, LeanIXReport)
        assert report.mappings == []

    def test_single_element_mapping(self):
        elements = [
            _ce("AuthService", leanix_type="IT Component", confidence=0.9, evidence=["runs as container"]),
        ]
        report = map(elements)

        assert len(report.mappings) == 1
        m = report.mappings[0]
        assert m.element_name == "AuthService"
        assert m.evidence == ["runs as container"]
        # Primary type should be present
        assert any(t["type"] == "IT Component" for t in m.leanix_types)

    def test_multiple_elements_produce_one_mapping_each(self):
        elements = [
            _ce("Svc1"),
            _ce("Svc2"),
            _ce("Svc3"),
        ]
        report = map(elements)
        assert len(report.mappings) == 3
        names = [m.element_name for m in report.mappings]
        assert names == ["Svc1", "Svc2", "Svc3"]

    def test_alternative_types_included_and_ranked(self):
        elements = [
            _ce(
                "PaymentAPI",
                leanix_type="Interface",
                confidence=0.85,
                alternative_types=[
                    {"type": "IT Component", "confidence": 0.95},
                    {"type": "Data Object", "confidence": 0.3},
                ],
            ),
        ]
        report = map(elements)
        m = report.mappings[0]

        # Should have 3 types total (primary + 2 alternatives)
        assert len(m.leanix_types) == 3
        # Sorted descending by confidence
        confidences = [t["confidence"] for t in m.leanix_types]
        assert confidences == sorted(confidences, reverse=True)
        # IT Component (0.95) should be first
        assert m.leanix_types[0]["type"] == "IT Component"
        assert m.leanix_types[0]["confidence"] == 0.95

    def test_relationships_derived_from_metadata_dependencies(self):
        elements = [
            _ce("OrderService", leanix_type="IT Component", confidence=0.9, metadata={"dependencies": ["OrderDB"]}),
            _ce("OrderDB", leanix_type="Data Object", confidence=0.8),
        ]
        report = map(elements)

        order_mapping = report.mappings[0]
        assert any(r["target"] == "OrderDB" for r in order_mapping.relationships)

    def test_implicit_relationships_it_component_to_interface(self):
        elements = [
            _ce("Backend", leanix_type="IT Component", confidence=0.9),
            _ce("RestAPI", leanix_type="Interface", confidence=0.85),
        ]
        report = map(elements)

        backend_mapping = report.mappings[0]
        # IT Component -> Interface should produce "provides" relationship
        rel = next((r for r in backend_mapping.relationships if r["target"] == "RestAPI"), None)
        assert rel is not None
        assert "provides" in rel["relationship"]

    def test_implicit_relationships_org_to_it_component(self):
        elements = [
            _ce("Engineering", leanix_type="Organization", confidence=0.8),
            _ce("DeployService", leanix_type="IT Component", confidence=0.9),
        ]
        report = map(elements)

        org_mapping = report.mappings[0]
        rel = next((r for r in org_mapping.relationships if r["target"] == "DeployService"), None)
        assert rel is not None
        assert "owns" in rel["relationship"]

    def test_evidence_preserved(self):
        evidence = ["Exposes REST endpoints", "Handles HTTP requests"]
        elements = [_ce("API", evidence=evidence)]
        report = map(elements)
        assert report.mappings[0].evidence == evidence

    def test_leanix_types_always_sorted_descending(self):
        elements = [
            _ce(
                "Svc",
                leanix_type="IT Component",
                confidence=0.5,
                alternative_types=[
                    {"type": "Interface", "confidence": 0.8},
                    {"type": "Organization", "confidence": 0.2},
                ],
            ),
        ]
        report = map(elements)
        types = report.mappings[0].leanix_types
        for i in range(len(types) - 1):
            assert types[i]["confidence"] >= types[i + 1]["confidence"]


# --- _build_ranked_types tests ---


class TestBuildRankedTypes:
    def test_primary_only(self):
        ce = _ce("X", leanix_type="Interface", confidence=0.7)
        result = _build_ranked_types(ce)
        assert result == [{"type": "Interface", "confidence": 0.7}]

    def test_with_alternatives_sorted(self):
        ce = _ce(
            "X",
            leanix_type="Data Object",
            confidence=0.6,
            alternative_types=[
                {"type": "IT Component", "confidence": 0.9},
                {"type": "Organization", "confidence": 0.3},
            ],
        )
        result = _build_ranked_types(ce)
        assert len(result) == 3
        assert result[0]["type"] == "IT Component"
        assert result[0]["confidence"] == 0.9
        assert result[-1]["type"] == "Organization"

    def test_skips_empty_type_strings(self):
        ce = _ce(
            "X",
            leanix_type="Interface",
            confidence=0.8,
            alternative_types=[{"type": "", "confidence": 0.5}],
        )
        result = _build_ranked_types(ce)
        # Empty type string should be skipped
        assert len(result) == 1


# --- _derive_relationships tests ---


class TestDeriveRelationships:
    def test_no_relationships_for_isolated_element(self):
        ce = _ce("Lonely", leanix_type="Data Object")
        result = _derive_relationships(ce, [ce])
        assert result == []

    def test_metadata_dependency_creates_relationship(self):
        svc = _ce("Svc", leanix_type="IT Component", metadata={"dependencies": ["DB"]})
        db = _ce("DB", leanix_type="Data Object")
        result = _derive_relationships(svc, [svc, db])
        assert len(result) >= 1
        assert any(r["target"] == "DB" for r in result)

    def test_no_duplicate_relationships(self):
        # If metadata dependency and implicit relationship would both fire,
        # we should not get duplicates
        svc = _ce("Svc", leanix_type="IT Component", metadata={"dependencies": ["API"]})
        api = _ce("API", leanix_type="Interface")
        result = _derive_relationships(svc, [svc, api])
        targets = [r["target"] for r in result]
        assert len(targets) == len(set(targets))

    def test_unknown_dependency_ignored(self):
        svc = _ce("Svc", leanix_type="IT Component", metadata={"dependencies": ["NonExistent"]})
        result = _derive_relationships(svc, [svc])
        assert result == []
