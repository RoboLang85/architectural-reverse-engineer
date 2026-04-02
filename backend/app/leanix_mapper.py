"""LeanIX Mapper – maps classified elements to LeanIX object types."""

from __future__ import annotations

from app.models import ClassifiedElement, LeanIXMapping, LeanIXReport


# Relationship templates keyed by (source_element_type, target_element_type).
# These are used to derive relationship labels between LeanIX objects.
_RELATIONSHIP_TEMPLATES: dict[tuple[str, str], str] = {
    ("IT Component", "Interface"): "provides",
    ("IT Component", "Data Object"): "accesses",
    ("IT Component", "IT Component"): "depends on",
    ("Organization", "IT Component"): "owns",
    ("Organization", "Organization"): "part of",
    ("Interface", "Data Object"): "exposes",
    ("Interface", "IT Component"): "provided by",
    ("Data Object", "IT Component"): "stored in",
    ("Data Object", "Interface"): "exposed by",
}


def _derive_relationships(
    element: ClassifiedElement,
    all_elements: list[ClassifiedElement],
) -> list[dict]:
    """Derive relationships for *element* based on its metadata and the full element set."""
    relationships: list[dict] = []
    seen: set[tuple[str, str]] = set()

    source_type = element.leanix_type
    source_name = element.element.name

    # Check element metadata for explicit dependency/relationship hints
    deps = element.element.metadata.get("dependencies", [])
    if isinstance(deps, list):
        target_lookup = {ce.element.name: ce for ce in all_elements}
        for dep_name in deps:
            target_ce = target_lookup.get(dep_name)
            if target_ce is None:
                continue
            target_type = target_ce.leanix_type
            rel_label = _RELATIONSHIP_TEMPLATES.get(
                (source_type, target_type), "relates to"
            )
            key = (source_name, dep_name)
            if key not in seen:
                relationships.append({"target": dep_name, "relationship": f"{source_type} {rel_label} {target_type}"})
                seen.add(key)

    # Infer relationships from element_type semantics
    for other in all_elements:
        if other.element.name == source_name:
            continue
        key = (source_name, other.element.name)
        if key in seen:
            continue

        other_type = other.leanix_type
        template_key = (source_type, other_type)
        if template_key in _RELATIONSHIP_TEMPLATES:
            # Only add implicit relationships for strong pairings
            if template_key in (
                ("IT Component", "Interface"),
                ("Organization", "IT Component"),
            ):
                rel_label = _RELATIONSHIP_TEMPLATES[template_key]
                relationships.append({"target": other.element.name, "relationship": f"{source_type} {rel_label} {other_type}"})
                seen.add(key)

    return relationships


def _build_ranked_types(element: ClassifiedElement) -> list[dict]:
    """Build a list of {type, confidence} entries sorted by confidence descending.

    Includes the primary type and all alternative types.
    """
    types: list[dict] = [
        {"type": element.leanix_type, "confidence": element.confidence},
    ]
    for alt in element.alternative_types:
        alt_type = alt.get("type", "")
        alt_conf = alt.get("confidence", 0.0)
        if alt_type:
            types.append({"type": alt_type, "confidence": alt_conf})

    # Sort descending by confidence
    types.sort(key=lambda t: t["confidence"], reverse=True)
    return types


def map(elements: list[ClassifiedElement]) -> LeanIXReport:
    """Map classified elements to a LeanIX mapping report.

    For each ClassifiedElement, produces a LeanIXMapping entry containing:
    - element_name: the element's name
    - leanix_types: primary + alternative types ranked by confidence (descending)
    - evidence: the classification evidence
    - relationships: derived relationships to other elements

    Args:
        elements: Classified architectural elements from the AI Engine.

    Returns:
        A LeanIXReport with one mapping per element.
    """
    if not elements:
        return LeanIXReport(mappings=[])

    mappings: list[LeanIXMapping] = []
    for ce in elements:
        ranked_types = _build_ranked_types(ce)
        relationships = _derive_relationships(ce, elements)

        mappings.append(
            LeanIXMapping(
                element_name=ce.element.name,
                leanix_types=ranked_types,
                evidence=list(ce.evidence),
                relationships=relationships,
            )
        )

    return LeanIXReport(mappings=mappings)
