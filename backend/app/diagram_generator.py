"""Diagram Generator for the Architectural Reverse Engineer.

Produces dependency graphs, component diagrams, and UML diagrams from
reconciled analysis models.  Uses Graphviz for graph rendering and
PlantUML for UML diagram rendering.  Includes circular dependency
detection with visual highlighting.
"""

from __future__ import annotations

import subprocess
import tempfile
from pathlib import Path
from typing import Literal

import graphviz  # type: ignore[import-untyped]

from app.errors import RenderError
from app.models import ComponentModel, DiagramOutput, ReconciledModel


# ---------------------------------------------------------------------------
# Circular dependency detection (DFS-based)
# ---------------------------------------------------------------------------


def _detect_cycles(adj: dict[str, list[str]]) -> list[list[str]]:
    """Return elementary cycles found via DFS.

    Each cycle is a list of node names forming the loop, e.g.
    ["A", "B", "C"] means A→B→C→A.

    Note: this finds *some* cycles (one per DFS back-edge) but may not
    enumerate every elementary cycle.  Use :func:`_cycle_edges_and_nodes`
    for the complete set of nodes/edges participating in *any* cycle.
    """
    WHITE, GRAY, BLACK = 0, 1, 2
    color: dict[str, int] = {n: WHITE for n in adj}
    path: list[str] = []
    cycles: list[list[str]] = []

    def dfs(node: str) -> None:
        color[node] = GRAY
        path.append(node)
        for neighbour in adj.get(node, []):
            if color.get(neighbour, WHITE) == GRAY:
                # Back-edge → extract cycle from path
                idx = path.index(neighbour)
                cycles.append(list(path[idx:]))
            elif color.get(neighbour, WHITE) == WHITE:
                dfs(neighbour)
        path.pop()
        color[node] = BLACK

    for node in adj:
        if color[node] == WHITE:
            dfs(node)

    return cycles


def _can_reach(adj: dict[str, list[str]], source: str, target: str) -> bool:
    """Return True if *target* is reachable from *source* via directed edges."""
    visited: set[str] = set()
    stack = [source]
    while stack:
        node = stack.pop()
        if node == target and node != source or (node == target and visited):
            return True
        if node in visited:
            continue
        visited.add(node)
        for nb in adj.get(node, []):
            if nb not in visited or nb == target:
                stack.append(nb)
    return False


def _cycle_edges_and_nodes(
    cycles: list[list[str]],
    adj: dict[str, list[str]],
    all_edges: list[tuple[str, str]],
) -> tuple[set[str], set[tuple[str, str]]]:
    """Derive the *complete* set of nodes and directed edges on any cycle.

    A node is on a cycle iff it can reach itself.  An edge ``(u, v)`` is on
    a cycle iff ``v`` can reach ``u``.
    """
    nodes: set[str] = set()
    edges: set[tuple[str, str]] = set()

    # A node is on a cycle if it can reach itself
    for node in adj:
        # Quick check: if already found in a DFS cycle, skip reachability
        if any(node in c for c in cycles):
            nodes.add(node)
            continue
        if _can_reach(adj, node, node):
            nodes.add(node)

    # An edge (u, v) is on a cycle if v can reach u
    for u, v in all_edges:
        if u in nodes and v in nodes:
            # Check if v can reach u
            visited: set[str] = set()
            stack = [v]
            found = False
            while stack:
                n = stack.pop()
                if n == u:
                    found = True
                    break
                if n in visited:
                    continue
                visited.add(n)
                for nb in adj.get(n, []):
                    if nb not in visited or nb == u:
                        stack.append(nb)
            if found:
                edges.add((u, v))

    return nodes, edges


# ---------------------------------------------------------------------------
# Dependency graph generation
# ---------------------------------------------------------------------------


def generate_dependency_graph(
    analysis: ReconciledModel,
    image_format: Literal["png", "svg"] = "png",
) -> DiagramOutput:
    """Produce a dependency graph from a reconciled analysis model.

    Each element becomes a node; each ``depends_on`` relationship becomes a
    directed edge.  Circular dependencies are detected and highlighted in red.

    Parameters
    ----------
    analysis:
        The reconciled model containing elements and relationships.
    image_format:
        Output image format – ``"png"`` (default) or ``"svg"``.

    Returns
    -------
    DiagramOutput
        Contains the rendered image bytes, structured JSON data, and metadata.

    Raises
    ------
    RenderError
        If the Graphviz CLI fails to render the graph.
    """

    # -- Build adjacency list & collect dependency edges --
    node_names: list[str] = [ce.element.name for ce in analysis.elements]
    dep_relationships = [
        r for r in analysis.relationships if r.relationship_type == "depends_on"
    ]

    adj: dict[str, list[str]] = {name: [] for name in node_names}
    for rel in dep_relationships:
        adj.setdefault(rel.source, []).append(rel.target)

    # -- Detect cycles --
    cycles = _detect_cycles(adj)
    all_edges = [(rel.source, rel.target) for rel in dep_relationships]
    cycle_nodes, cycle_edges = _cycle_edges_and_nodes(cycles, adj, all_edges)

    # -- Build structured data --
    nodes_data = [
        {
            "id": name,
            "in_cycle": name in cycle_nodes,
        }
        for name in node_names
    ]
    edges_data = [
        {
            "source": rel.source,
            "target": rel.target,
            "in_cycle": (rel.source, rel.target) in cycle_edges,
        }
        for rel in dep_relationships
    ]
    structured_data: dict = {
        "nodes": nodes_data,
        "edges": edges_data,
        "circular_dependencies": [list(c) for c in cycles],
    }

    # -- Render with Graphviz --
    dot = graphviz.Digraph(
        name="dependency_graph",
        format=image_format,
        graph_attr={"rankdir": "LR", "label": "Dependency Graph"},
    )

    for name in node_names:
        attrs: dict[str, str] = {"shape": "box", "style": "filled", "fillcolor": "#d0e8ff"}
        if name in cycle_nodes:
            attrs["fillcolor"] = "#ff6666"
            attrs["fontcolor"] = "white"
        dot.node(name, **attrs)

    for rel in dep_relationships:
        edge_attrs: dict[str, str] = {}
        if (rel.source, rel.target) in cycle_edges:
            edge_attrs["color"] = "red"
            edge_attrs["penwidth"] = "2.0"
        dot.edge(rel.source, rel.target, **edge_attrs)

    try:
        rendered_bytes: bytes = dot.pipe()
    except Exception as exc:
        raise RenderError(
            f"Graphviz rendering failed: {exc}",
            details={"format": image_format, "original_error": str(exc)},
        ) from exc

    return DiagramOutput(
        diagram_type="dependency_graph",
        rendered_image=rendered_bytes,
        image_format=image_format,
        structured_data=structured_data,
        source_file=dot.source,
    )


# ---------------------------------------------------------------------------
# Component diagram generation
# ---------------------------------------------------------------------------


def generate_component_diagram(
    analysis: ReconciledModel,
    image_format: Literal["png", "svg"] = "png",
) -> DiagramOutput:
    """Produce a component diagram from a reconciled analysis model.

    Each :class:`ClassifiedElement` becomes a component node labelled with
    its *name*, *element_type*, and *leanix_type*.  Every
    :class:`Relationship` (regardless of ``relationship_type``) becomes a
    labelled connector between components.

    Parameters
    ----------
    analysis:
        The reconciled model containing classified elements and relationships.
    image_format:
        Output image format – ``"png"`` (default) or ``"svg"``.

    Returns
    -------
    DiagramOutput
        Contains the rendered image bytes, structured JSON data, and metadata.

    Raises
    ------
    RenderError
        If the Graphviz CLI fails to render the graph.
    """

    # -- Build structured data --
    components: list[dict] = [
        {
            "name": ce.element.name,
            "type": ce.element.element_type,
            "leanix_type": ce.leanix_type,
        }
        for ce in analysis.elements
    ]

    connectors: list[dict] = [
        {
            "source": rel.source,
            "target": rel.target,
            "interface_type": rel.relationship_type,
        }
        for rel in analysis.relationships
    ]

    structured_data: dict = {
        "components": components,
        "connectors": connectors,
    }

    # -- Render with Graphviz --
    dot = graphviz.Digraph(
        name="component_diagram",
        format=image_format,
        graph_attr={"rankdir": "LR", "label": "Component Diagram"},
    )

    for ce in analysis.elements:
        label = f"{ce.element.name}\\n[{ce.element.element_type}]\\n«{ce.leanix_type}»"
        dot.node(
            ce.element.name,
            label=label,
            shape="component",
            style="filled",
            fillcolor="#d0e8ff",
        )

    for rel in analysis.relationships:
        dot.edge(
            rel.source,
            rel.target,
            label=rel.relationship_type,
        )

    try:
        rendered_bytes: bytes = dot.pipe()
    except Exception as exc:
        raise RenderError(
            f"Graphviz rendering failed: {exc}",
            details={"format": image_format, "original_error": str(exc)},
        ) from exc

    return DiagramOutput(
        diagram_type="component",
        rendered_image=rendered_bytes,
        image_format=image_format,
        structured_data=structured_data,
        source_file=dot.source,
    )


# ---------------------------------------------------------------------------
# PlantUML rendering helper
# ---------------------------------------------------------------------------

_OO_TYPES = frozenset({"class", "interface", "module"})


def _render_plantuml(
    source: str,
    image_format: Literal["png", "svg"] = "png",
) -> bytes:
    """Render PlantUML *source* to image bytes via the ``plantuml`` CLI.

    Parameters
    ----------
    source:
        PlantUML source text (including ``@startuml`` / ``@enduml``).
    image_format:
        ``"png"`` or ``"svg"``.

    Returns
    -------
    bytes
        The rendered image data.

    Raises
    ------
    RenderError
        If the ``plantuml`` CLI is not found or returns a non-zero exit code.
    """
    fmt_flag = "-tsvg" if image_format == "svg" else "-tpng"

    with tempfile.TemporaryDirectory() as tmpdir:
        src_path = Path(tmpdir) / "diagram.puml"
        src_path.write_text(source, encoding="utf-8")

        try:
            result = subprocess.run(
                ["plantuml", fmt_flag, "-pipe"],
                input=source.encode("utf-8"),
                capture_output=True,
                check=False,
                timeout=60,
            )
        except FileNotFoundError as exc:
            raise RenderError(
                "PlantUML CLI not found. Please install PlantUML.",
                details={"original_error": str(exc)},
            ) from exc

        if result.returncode != 0:
            raise RenderError(
                f"PlantUML rendering failed (exit code {result.returncode}): "
                f"{result.stderr.decode('utf-8', errors='replace')}",
                details={
                    "format": image_format,
                    "stderr": result.stderr.decode("utf-8", errors="replace"),
                },
            )

        return result.stdout


# ---------------------------------------------------------------------------
# UML class diagram generation
# ---------------------------------------------------------------------------


def generate_uml_class_diagram(
    analysis: ReconciledModel,
    image_format: Literal["png", "svg"] = "png",
) -> DiagramOutput:
    """Produce a UML class diagram from a reconciled analysis model.

    Elements with ``element_type`` in ``("class", "interface", "module")``
    become UML classes/interfaces.  Relationships of type ``"inherits"``,
    ``"composition"``, and ``"association"`` are rendered as UML connectors.

    Parameters
    ----------
    analysis:
        The reconciled model containing classified elements and relationships.
    image_format:
        Output image format – ``"png"`` (default) or ``"svg"``.

    Returns
    -------
    DiagramOutput
        Contains the rendered image bytes, structured JSON data, PlantUML
        source, and metadata.

    Raises
    ------
    RenderError
        If the PlantUML CLI fails to render the diagram.
    """

    # -- Filter OO elements --
    oo_elements = [
        ce for ce in analysis.elements
        if ce.element.element_type in _OO_TYPES
    ]

    oo_names = {ce.element.name for ce in oo_elements}

    # -- Filter relevant relationships --
    class_rel_types = {"inherits", "composition", "association", "implements"}
    class_rels = [
        r for r in analysis.relationships
        if r.relationship_type in class_rel_types
        and r.source in oo_names
        and r.target in oo_names
    ]

    # -- Build structured data --
    classes_data: list[dict] = [
        {
            "name": ce.element.name,
            "type": ce.element.element_type,
            "leanix_type": ce.leanix_type,
        }
        for ce in oo_elements
    ]

    relationships_data: list[dict] = [
        {
            "source": r.source,
            "target": r.target,
            "relationship_type": r.relationship_type,
        }
        for r in class_rels
    ]

    structured_data: dict = {
        "classes": classes_data,
        "relationships": relationships_data,
    }

    # -- Build PlantUML source --
    _REL_ARROWS = {
        "inherits": "--|>",
        "implements": "..|>",
        "composition": "*--",
        "association": "-->",
    }

    lines: list[str] = ["@startuml"]
    for ce in oo_elements:
        keyword = "interface" if ce.element.element_type == "interface" else "class"
        lines.append(f"{keyword} {ce.element.name}")
    for r in class_rels:
        arrow = _REL_ARROWS.get(r.relationship_type, "-->")
        lines.append(f"{r.source} {arrow} {r.target}")
    lines.append("@enduml")
    source = "\n".join(lines)

    # -- Render --
    try:
        rendered_bytes = _render_plantuml(source, image_format)
    except RenderError:
        raise
    except Exception as exc:
        raise RenderError(
            f"PlantUML rendering failed: {exc}",
            details={"format": image_format, "original_error": str(exc)},
        ) from exc

    return DiagramOutput(
        diagram_type="uml_class",
        rendered_image=rendered_bytes,
        image_format=image_format,
        structured_data=structured_data,
        source_file=source,
    )


# ---------------------------------------------------------------------------
# UML sequence diagram generation
# ---------------------------------------------------------------------------


def generate_uml_sequence_diagram(
    analysis: ReconciledModel,
    image_format: Literal["png", "svg"] = "png",
) -> DiagramOutput:
    """Produce a UML sequence diagram from a reconciled analysis model.

    ``"calls"`` relationships are rendered as messages between participants.
    Each unique source/target in a ``calls`` relationship becomes a
    participant.

    Parameters
    ----------
    analysis:
        The reconciled model containing classified elements and relationships.
    image_format:
        Output image format – ``"png"`` (default) or ``"svg"``.

    Returns
    -------
    DiagramOutput
        Contains the rendered image bytes, structured JSON data, PlantUML
        source, and metadata.

    Raises
    ------
    RenderError
        If the PlantUML CLI fails to render the diagram.
    """

    # -- Filter "calls" relationships --
    call_rels = [
        r for r in analysis.relationships
        if r.relationship_type == "calls"
    ]

    # -- Derive participants (preserve order of first appearance) --
    seen: set[str] = set()
    participants: list[str] = []
    for r in call_rels:
        for name in (r.source, r.target):
            if name not in seen:
                seen.add(name)
                participants.append(name)

    # -- Build structured data --
    participants_data: list[dict] = [{"name": p} for p in participants]
    messages_data: list[dict] = [
        {
            "from": r.source,
            "to": r.target,
            "label": r.relationship_type,
        }
        for r in call_rels
    ]

    structured_data: dict = {
        "participants": participants_data,
        "messages": messages_data,
    }

    # -- Build PlantUML source --
    lines: list[str] = ["@startuml"]
    for p in participants:
        lines.append(f'participant "{p}" as {p}')
    for r in call_rels:
        lines.append(f"{r.source} -> {r.target} : {r.relationship_type}")
    lines.append("@enduml")
    source = "\n".join(lines)

    # -- Render --
    try:
        rendered_bytes = _render_plantuml(source, image_format)
    except RenderError:
        raise
    except Exception as exc:
        raise RenderError(
            f"PlantUML rendering failed: {exc}",
            details={"format": image_format, "original_error": str(exc)},
        ) from exc

    return DiagramOutput(
        diagram_type="uml_sequence",
        rendered_image=rendered_bytes,
        image_format=image_format,
        structured_data=structured_data,
        source_file=source,
    )


# ---------------------------------------------------------------------------
# LLD (Lower Level Design) diagram generation
# ---------------------------------------------------------------------------


def generate_lld(
    component: ComponentModel,
    image_format: Literal["png", "svg"] = "png",
) -> DiagramOutput:
    """Produce a Lower Level Design diagram for a single component.

    The LLD shows internal classes, functions, data transformations, and
    data flow edges within the component.  Each internal element becomes a
    labelled node; data flows become directed edges.

    Parameters
    ----------
    component:
        A :class:`ComponentModel` describing the component's internals.
    image_format:
        Output image format – ``"png"`` (default) or ``"svg"``.

    Returns
    -------
    DiagramOutput
        Contains the rendered image bytes, structured JSON data, and metadata.

    Raises
    ------
    RenderError
        If the Graphviz CLI fails to render the graph.
    """

    # -- Build structured data --
    nodes: list[dict] = []
    for cls_name in component.classes:
        nodes.append({"id": cls_name, "label": cls_name, "type": "class"})
    for fn_name in component.functions:
        nodes.append({"id": fn_name, "label": fn_name, "type": "function"})
    for dt_name in component.data_transformations:
        nodes.append({"id": dt_name, "label": dt_name, "type": "data_transformation"})

    edges: list[dict] = [
        {"source": src, "target": tgt}
        for src, tgt in component.data_flows
    ]

    structured_data: dict = {
        "component_name": component.name,
        "nodes": nodes,
        "edges": edges,
    }

    # -- Render with Graphviz --
    dot = graphviz.Digraph(
        name="lld",
        format=image_format,
        graph_attr={
            "rankdir": "TB",
            "label": f"LLD – {component.name}",
            "compound": "true",
        },
    )

    _SHAPE_MAP = {
        "class": "box",
        "function": "ellipse",
        "data_transformation": "hexagon",
    }
    _COLOR_MAP = {
        "class": "#d0e8ff",
        "function": "#d0ffd0",
        "data_transformation": "#ffe8d0",
    }

    for node in nodes:
        dot.node(
            node["id"],
            label=node["label"],
            shape=_SHAPE_MAP.get(node["type"], "box"),
            style="filled",
            fillcolor=_COLOR_MAP.get(node["type"], "#ffffff"),
        )

    for edge in edges:
        dot.edge(edge["source"], edge["target"])

    try:
        rendered_bytes: bytes = dot.pipe()
    except Exception as exc:
        raise RenderError(
            f"Graphviz rendering failed: {exc}",
            details={"format": image_format, "original_error": str(exc)},
        ) from exc

    return DiagramOutput(
        diagram_type="lld",
        rendered_image=rendered_bytes,
        image_format=image_format,
        structured_data=structured_data,
        source_file=dot.source,
    )
