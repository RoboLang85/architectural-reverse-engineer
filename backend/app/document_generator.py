"""Document Generator for the Architectural Reverse Engineer.

Produces Architectural Decision Records (ADRs) and comprehensive Markdown
documentation from reconciled analysis models and generated diagrams.
"""

from __future__ import annotations

import re

from app.models import ADR, ClassifiedElement, DiagramOutput, ReconciledModel


# ---------------------------------------------------------------------------
# Pattern-to-ADR mapping
# ---------------------------------------------------------------------------

_PATTERN_ADR_MAP: dict[str, dict[str, str]] = {
    "microservices": {
        "title": "Use Microservices Architecture",
        "context": (
            "The system requires independent deployment and scaling of "
            "components. Multiple teams need to work on different parts "
            "of the system concurrently."
        ),
        "decision": (
            "Adopt a microservices architecture where each service is "
            "independently deployable and communicates via well-defined APIs."
        ),
        "consequences": (
            "Increased operational complexity and need for service discovery, "
            "but improved scalability and team autonomy."
        ),
    },
    "layered": {
        "title": "Use Layered Architecture",
        "context": (
            "The system needs clear separation of concerns between "
            "presentation, business logic, and data access."
        ),
        "decision": (
            "Organize the system into distinct layers with well-defined "
            "responsibilities and dependencies flowing downward."
        ),
        "consequences": (
            "Clear separation of concerns and easier testing, but potential "
            "performance overhead from layer traversal."
        ),
    },
    "event-driven": {
        "title": "Use Event-Driven Architecture",
        "context": (
            "The system requires loose coupling between components and "
            "needs to react to state changes asynchronously."
        ),
        "decision": (
            "Adopt an event-driven architecture where components communicate "
            "through events published to a message broker."
        ),
        "consequences": (
            "Improved decoupling and scalability, but increased complexity "
            "in debugging and ensuring event ordering."
        ),
    },
    "monolithic": {
        "title": "Use Monolithic Architecture",
        "context": (
            "The system is a single deployable unit with tightly coupled "
            "components sharing the same process."
        ),
        "decision": (
            "Maintain a monolithic architecture for simplicity of deployment "
            "and development."
        ),
        "consequences": (
            "Simpler deployment and debugging, but limited scalability and "
            "potential for tighter coupling over time."
        ),
    },
    "hexagonal": {
        "title": "Use Hexagonal Architecture",
        "context": (
            "The system needs to be testable in isolation and adaptable to "
            "different external systems."
        ),
        "decision": (
            "Adopt hexagonal (ports and adapters) architecture to decouple "
            "core business logic from external dependencies."
        ),
        "consequences": (
            "Improved testability and flexibility, but more boilerplate code "
            "for port and adapter definitions."
        ),
    },
}

# Mapping from element types to ADR templates
_ELEMENT_TYPE_ADR_MAP: dict[str, dict[str, str]] = {
    "database": {
        "title": "Use Dedicated Database Component",
        "context": (
            "The system requires persistent data storage with specific "
            "query and consistency requirements."
        ),
        "decision": (
            "Introduce a dedicated database component to manage persistent "
            "state separately from application logic."
        ),
        "consequences": (
            "Clear data ownership and optimized storage, but added "
            "operational overhead for database management."
        ),
    },
    "gateway": {
        "title": "Use API Gateway",
        "context": (
            "The system exposes multiple services that need a unified "
            "entry point for external consumers."
        ),
        "decision": (
            "Introduce an API gateway to route, authenticate, and "
            "aggregate requests to backend services."
        ),
        "consequences": (
            "Simplified client integration and centralized cross-cutting "
            "concerns, but potential single point of failure."
        ),
    },
    "queue": {
        "title": "Use Message Queue for Asynchronous Communication",
        "context": (
            "Components need to communicate asynchronously to handle "
            "varying load and ensure reliability."
        ),
        "decision": (
            "Introduce a message queue for asynchronous inter-component "
            "communication."
        ),
        "consequences": (
            "Improved resilience and load handling, but added complexity "
            "in message ordering and delivery guarantees."
        ),
    },
}

# Mapping from layer names to ADR templates
_LAYER_ADR_MAP: dict[str, dict[str, str]] = {
    "presentation": {
        "title": "Separate Presentation Layer",
        "context": (
            "The system needs a distinct layer for user interface and "
            "API endpoint handling."
        ),
        "decision": (
            "Establish a dedicated presentation layer responsible for "
            "request handling, response formatting, and UI rendering."
        ),
        "consequences": (
            "Clear separation of UI concerns from business logic, "
            "enabling independent frontend evolution."
        ),
    },
    "data access": {
        "title": "Separate Data Access Layer",
        "context": (
            "The system needs to abstract database operations from "
            "business logic."
        ),
        "decision": (
            "Establish a dedicated data access layer encapsulating all "
            "database interactions behind repository interfaces."
        ),
        "consequences": (
            "Easier database migration and testing with mocks, but "
            "additional abstraction layer to maintain."
        ),
    },
}


# ---------------------------------------------------------------------------
# ADR generation
# ---------------------------------------------------------------------------


def generate_adrs(
    analysis: ReconciledModel,
    existing_adrs: list[ADR] | None = None,
) -> list[ADR]:
    """Generate ADRs from detected architectural patterns and decisions.

    Analyzes the reconciled model to detect architectural decisions from
    patterns, layers, and element types, then produces ADRs in Markdown
    format with Title, Status, Context, Decision, and Consequences sections.

    Deduplicates against *existing_adrs* by comparing titles
    case-insensitively.

    Parameters
    ----------
    analysis:
        The reconciled analysis model.
    existing_adrs:
        Optional list of existing ADRs to deduplicate against.

    Returns
    -------
    list[ADR]
        Newly generated ADRs (excluding any that duplicate existing ones).
    """
    existing_titles: set[str] = set()
    if existing_adrs:
        existing_titles = {adr.title.strip().lower() for adr in existing_adrs}

    candidates: list[ADR] = []

    # Derive ADRs from detected patterns
    for pattern in analysis.patterns:
        pattern_lower = pattern.strip().lower()
        for key, template in _PATTERN_ADR_MAP.items():
            if key in pattern_lower:
                candidates.append(
                    ADR(
                        title=template["title"],
                        status="Proposed",
                        context=template["context"],
                        decision=template["decision"],
                        consequences=template["consequences"],
                    )
                )
                break

    # Derive ADRs from detected layers
    for layer in analysis.layers:
        layer_lower = layer.strip().lower()
        for key, template in _LAYER_ADR_MAP.items():
            if key in layer_lower:
                candidates.append(
                    ADR(
                        title=template["title"],
                        status="Proposed",
                        context=template["context"],
                        decision=template["decision"],
                        consequences=template["consequences"],
                    )
                )
                break

    # Derive ADRs from element types
    seen_element_types: set[str] = set()
    for ce in analysis.elements:
        et = ce.element.element_type.strip().lower()
        if et in _ELEMENT_TYPE_ADR_MAP and et not in seen_element_types:
            seen_element_types.add(et)
            template = _ELEMENT_TYPE_ADR_MAP[et]
            candidates.append(
                ADR(
                    title=template["title"],
                    status="Proposed",
                    context=template["context"],
                    decision=template["decision"],
                    consequences=template["consequences"],
                )
            )

    # Deduplicate: remove candidates whose title matches an existing ADR
    # and also remove internal duplicates
    result: list[ADR] = []
    seen_titles: set[str] = set(existing_titles)
    for adr in candidates:
        title_key = adr.title.strip().lower()
        if title_key not in seen_titles:
            seen_titles.add(title_key)
            result.append(adr)

    return result


# ---------------------------------------------------------------------------
# ADR to Markdown rendering
# ---------------------------------------------------------------------------


def adr_to_markdown(adr: ADR) -> str:
    """Render a single ADR as a Markdown string with all five sections."""
    return (
        f"# {adr.title}\n\n"
        f"## Status\n\n{adr.status}\n\n"
        f"## Context\n\n{adr.context}\n\n"
        f"## Decision\n\n{adr.decision}\n\n"
        f"## Consequences\n\n{adr.consequences}\n"
    )


# ---------------------------------------------------------------------------
# Markdown documentation generation
# ---------------------------------------------------------------------------


def _slugify(text: str) -> str:
    """Convert a section title to a GitHub-compatible anchor slug."""
    slug = text.strip().lower()
    slug = re.sub(r"[^\w\s-]", "", slug)
    slug = re.sub(r"[\s]+", "-", slug)
    return slug


def generate_markdown(
    analysis: ReconciledModel,
    diagrams: list[DiagramOutput] | None = None,
) -> str:
    """Generate comprehensive Markdown documentation.

    Produces a Markdown document containing:
    - Table of contents with anchor links
    - System Overview
    - Component Descriptions
    - Dependency Summary
    - Interface Catalog
    - Embedded/linked diagrams

    Formatted for GitHub and standard Markdown renderer compatibility.

    Parameters
    ----------
    analysis:
        The reconciled analysis model.
    diagrams:
        Optional list of generated diagram outputs to embed.

    Returns
    -------
    str
        Complete Markdown document string.
    """
    if diagrams is None:
        diagrams = []

    sections: list[str] = []

    # --- Table of Contents ---
    toc_entries = [
        "System Overview",
        "Component Descriptions",
        "Dependency Summary",
        "Interface Catalog",
    ]
    if diagrams:
        toc_entries.append("Diagrams")

    toc_lines = ["# Architecture Documentation\n", "## Table of Contents\n"]
    for entry in toc_entries:
        slug = _slugify(entry)
        toc_lines.append(f"- [{entry}](#{slug})")
    toc_lines.append("")
    sections.append("\n".join(toc_lines))

    # --- System Overview ---
    overview_lines = ["## System Overview\n"]
    if analysis.patterns:
        overview_lines.append(
            "**Detected Patterns:** " + ", ".join(analysis.patterns)
        )
    else:
        overview_lines.append("No architectural patterns detected.")
    overview_lines.append("")
    if analysis.layers:
        overview_lines.append(
            "**Detected Layers:** " + ", ".join(analysis.layers)
        )
    else:
        overview_lines.append("No architectural layers detected.")
    overview_lines.append("")
    if analysis.discrepancies:
        overview_lines.append("**Discrepancies:**\n")
        for d in analysis.discrepancies:
            overview_lines.append(f"- {d}")
        overview_lines.append("")
    sections.append("\n".join(overview_lines))

    # --- Component Descriptions ---
    comp_lines = ["## Component Descriptions\n"]
    if analysis.elements:
        for ce in analysis.elements:
            comp_lines.append(f"### {ce.element.name}\n")
            comp_lines.append(f"- **Type:** {ce.element.element_type}")
            comp_lines.append(f"- **LeanIX Type:** {ce.leanix_type}")
            comp_lines.append(
                f"- **Confidence:** {ce.confidence:.0%}"
            )
            if ce.element.metadata:
                comp_lines.append(f"- **Metadata:** {ce.element.metadata}")
            comp_lines.append("")
    else:
        comp_lines.append("No components identified.\n")
    sections.append("\n".join(comp_lines))

    # --- Dependency Summary ---
    dep_lines = ["## Dependency Summary\n"]
    dep_rels = [
        r
        for r in analysis.relationships
        if r.relationship_type == "depends_on"
    ]
    if dep_rels:
        dep_lines.append("| Source | Target | Type |")
        dep_lines.append("|--------|--------|------|")
        for r in dep_rels:
            dep_lines.append(
                f"| {r.source} | {r.target} | {r.relationship_type} |"
            )
        dep_lines.append("")
    else:
        dep_lines.append("No dependency relationships identified.\n")
    sections.append("\n".join(dep_lines))

    # --- Interface Catalog ---
    iface_lines = ["## Interface Catalog\n"]
    iface_rels = [
        r
        for r in analysis.relationships
        if r.relationship_type != "depends_on"
    ]
    if iface_rels:
        iface_lines.append("| Source | Target | Interface Type |")
        iface_lines.append("|--------|--------|----------------|")
        for r in iface_rels:
            iface_lines.append(
                f"| {r.source} | {r.target} | {r.relationship_type} |"
            )
        iface_lines.append("")
    else:
        iface_lines.append("No interface relationships identified.\n")
    sections.append("\n".join(iface_lines))

    # --- Diagrams ---
    if diagrams:
        diag_lines = ["## Diagrams\n"]
        for i, diag in enumerate(diagrams):
            label = diag.diagram_type.replace("_", " ").title()
            ext = diag.image_format
            filename = f"{diag.diagram_type}.{ext}"
            diag_lines.append(f"### {label}\n")
            diag_lines.append(f"![{label}]({filename})\n")
        sections.append("\n".join(diag_lines))

    return "\n".join(sections)
