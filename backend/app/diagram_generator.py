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


def _tarjan_sccs(adj: dict[str, list[str]]) -> list[set[str]]:
    """Return all strongly connected components using Tarjan's algorithm.

    Each SCC is returned as a ``set[str]`` of node names.  Only SCCs with
    size > 1 (i.e. actual cycles) are useful for cycle detection, but all
    SCCs are returned for completeness.
    """
    index_counter = [0]
    stack: list[str] = []
    on_stack: set[str] = set()
    index: dict[str, int] = {}
    lowlink: dict[str, int] = {}
    sccs: list[set[str]] = []

    def strongconnect(node: str) -> None:
        index[node] = index_counter[0]
        lowlink[node] = index_counter[0]
        index_counter[0] += 1
        stack.append(node)
        on_stack.add(node)

        for neighbour in adj.get(node, []):
            if neighbour not in index:
                strongconnect(neighbour)
                lowlink[node] = min(lowlink[node], lowlink[neighbour])
            elif neighbour in on_stack:
                lowlink[node] = min(lowlink[node], index[neighbour])

        if lowlink[node] == index[node]:
            scc: set[str] = set()
            while True:
                w = stack.pop()
                on_stack.discard(w)
                scc.add(w)
                if w == node:
                    break
            sccs.append(scc)

    for node in adj:
        if node not in index:
            strongconnect(node)

    return sccs


def _cycle_edges_and_nodes(
    adj: dict[str, list[str]],
    all_edges: list[tuple[str, str]],
) -> tuple[set[str], set[tuple[str, str]]]:
    """Derive the *complete* set of nodes and directed edges on any cycle.

    Uses Tarjan's SCC algorithm: a node is on a cycle iff it belongs to an
    SCC of size > 1.  An edge ``(u, v)`` is on a cycle iff both ``u`` and
    ``v`` are in the same SCC of size > 1.
    """
    # Find all SCCs with size > 1 (these contain cycles)
    sccs = _tarjan_sccs(adj)
    cycle_sccs = [scc for scc in sccs if len(scc) > 1]

    # Also detect self-loops: a node with an edge to itself is on a cycle
    # even though Tarjan's algorithm places it in an SCC of size 1
    self_loop_nodes: set[str] = set()
    for node, neighbours in adj.items():
        if node in neighbours:
            self_loop_nodes.add(node)

    # Build node → SCC mapping for cycle SCCs only
    node_to_scc: dict[str, int] = {}
    for i, scc in enumerate(cycle_sccs):
        for node in scc:
            node_to_scc[node] = i

    # Assign self-loop-only nodes their own SCC ids
    next_id = len(cycle_sccs)
    for node in self_loop_nodes:
        if node not in node_to_scc:
            node_to_scc[node] = next_id
            next_id += 1

    # Cycle nodes: all nodes in any SCC of size > 1, plus self-loop nodes
    nodes: set[str] = set(node_to_scc.keys())

    # Cycle edges: edges where both endpoints are in the same SCC of size > 1,
    # plus self-loop edges
    edges: set[tuple[str, str]] = set()
    for u, v in all_edges:
        if u == v and u in self_loop_nodes:
            edges.add((u, v))
        elif u in node_to_scc and v in node_to_scc and node_to_scc[u] == node_to_scc[v]:
            edges.add((u, v))

    return nodes, edges


# ---------------------------------------------------------------------------
# Shared rendering helpers
# ---------------------------------------------------------------------------


def _render_graphviz_diagram(
    dot: graphviz.Digraph,
    diagram_type: str,
    image_format: str,
    structured_data: dict,
) -> DiagramOutput:
    """Render a Graphviz graph and wrap the result in a :class:`DiagramOutput`.

    Parameters
    ----------
    dot:
        A fully-constructed :class:`graphviz.Digraph` ready to render.
    diagram_type:
        Diagram type label (e.g. ``"dependency_graph"``, ``"component"``).
    image_format:
        ``"png"`` or ``"svg"``.
    structured_data:
        JSON-serializable dict to embed in the output.

    Returns
    -------
    DiagramOutput

    Raises
    ------
    RenderError
        If the Graphviz CLI fails to render the graph.
    """
    try:
        rendered_bytes: bytes = dot.pipe()
    except Exception as exc:
        raise RenderError(
            f"Graphviz rendering failed: {exc}",
            details={"format": image_format, "original_error": str(exc)},
        ) from exc

    return DiagramOutput(
        diagram_type=diagram_type,
        rendered_image=rendered_bytes,
        image_format=image_format,
        structured_data=structured_data,
        source_file=dot.source,
    )


def _render_plantuml_diagram(
    source: str,
    diagram_type: str,
    image_format: str,
    structured_data: dict,
) -> DiagramOutput:
    """Render PlantUML *source* and wrap the result in a :class:`DiagramOutput`.

    Parameters
    ----------
    source:
        PlantUML source text (including ``@startuml`` / ``@enduml``).
    diagram_type:
        Diagram type label (e.g. ``"uml_class"``, ``"uml_sequence"``).
    image_format:
        ``"png"`` or ``"svg"``.
    structured_data:
        JSON-serializable dict to embed in the output.

    Returns
    -------
    DiagramOutput

    Raises
    ------
    RenderError
        If the PlantUML CLI fails to render the diagram.
    """
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
        diagram_type=diagram_type,
        rendered_image=rendered_bytes,
        image_format=image_format,
        structured_data=structured_data,
        source_file=source,
    )


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
    cycle_nodes, cycle_edges = _cycle_edges_and_nodes(adj, all_edges)

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

    return _render_graphviz_diagram(dot, "dependency_graph", image_format, structured_data)


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

    return _render_graphviz_diagram(dot, "component", image_format, structured_data)


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
    return _render_plantuml_diagram(source, "uml_class", image_format, structured_data)


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
    return _render_plantuml_diagram(source, "uml_sequence", image_format, structured_data)


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

    return _render_graphviz_diagram(dot, "lld", image_format, structured_data)
