"""Property-based tests for Diagram Generator – dependency graph.

# Feature: architectural-reverse-engineer, Property 8: Dependency graph structural correctness
# Feature: architectural-reverse-engineer, Property 9: Circular dependency highlighting

**Validates: Requirements 4.1, 4.2, 4.3**
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from hypothesis import given, settings
from hypothesis import strategies as st

from app.diagram_generator import generate_dependency_graph
from app.models import (
    ClassifiedElement,
    Element,
    ReconciledModel,
    Relationship,
)


# ---------------------------------------------------------------------------
# Strategies
# ---------------------------------------------------------------------------

_name_alphabet = st.characters(whitelist_categories=("L", "N"))
_module_name = st.text(alphabet=_name_alphabet, min_size=1, max_size=20)


def _classified_element(name: str) -> ClassifiedElement:
    return ClassifiedElement(
        element=Element(name=name, element_type="module", metadata={}),
        leanix_type="IT Component",
        confidence=0.9,
    )


@st.composite
def reconciled_models(draw: st.DrawFn) -> ReconciledModel:
    """Generate a ReconciledModel with unique element names and depends_on edges."""
    names = draw(
        st.lists(_module_name, min_size=1, max_size=15, unique=True)
    )
    elements = [_classified_element(n) for n in names]

    # Draw a subset of all possible directed pairs as depends_on relationships
    possible_edges = [(s, t) for s in names for t in names if s != t]
    if possible_edges:
        edges = draw(
            st.lists(
                st.sampled_from(possible_edges),
                max_size=min(len(possible_edges), 30),
                unique=True,
            )
        )
    else:
        edges = []

    relationships = [
        Relationship(source=s, target=t, relationship_type="depends_on")
        for s, t in edges
    ]

    return ReconciledModel(elements=elements, relationships=relationships)


@st.composite
def reconciled_models_with_cycle(draw: st.DrawFn) -> ReconciledModel:
    """Generate a ReconciledModel guaranteed to contain at least one cycle.

    Strategy: create a set of nodes, pick a subset of ≥2 to form a forced
    cycle, then optionally add extra random edges.
    """
    names = draw(
        st.lists(_module_name, min_size=2, max_size=15, unique=True)
    )
    elements = [_classified_element(n) for n in names]

    # Force a cycle: pick ≥2 nodes and chain them into a loop
    cycle_size = draw(st.integers(min_value=2, max_value=len(names)))
    cycle_names = draw(
        st.permutations(names).map(lambda p: list(p[:cycle_size]))
    )
    forced_edges: set[tuple[str, str]] = set()
    for i in range(len(cycle_names)):
        forced_edges.add((cycle_names[i], cycle_names[(i + 1) % len(cycle_names)]))

    # Optionally add extra random edges
    possible_extras = [
        (s, t) for s in names for t in names if s != t and (s, t) not in forced_edges
    ]
    if possible_extras:
        extras = draw(
            st.lists(
                st.sampled_from(possible_extras),
                max_size=min(len(possible_extras), 20),
                unique=True,
            )
        )
    else:
        extras = []

    all_edges = list(forced_edges) + extras
    relationships = [
        Relationship(source=s, target=t, relationship_type="depends_on")
        for s, t in all_edges
    ]

    return ReconciledModel(elements=elements, relationships=relationships)


# ---------------------------------------------------------------------------
# Graphviz mock helper
# ---------------------------------------------------------------------------

def _mock_graphviz():
    """Return a patcher that replaces graphviz.Digraph with a mock."""
    mock_digraph_cls = MagicMock()
    mock_graph = MagicMock()
    mock_graph.pipe.return_value = b"fake-png"
    mock_graph.source = "digraph {}"
    mock_digraph_cls.return_value = mock_graph
    return patch("app.diagram_generator.graphviz.Digraph", mock_digraph_cls)


# ---------------------------------------------------------------------------
# Property 8: Dependency graph structural correctness
# ---------------------------------------------------------------------------


@settings(max_examples=100, deadline=None)
@given(model=reconciled_models())
def test_dependency_graph_structural_correctness(model: ReconciledModel):
    """For any reconciled model, the dependency graph structured data has
    exactly one node per element and one edge per depends_on relationship,
    with no missing or extra entries.

    # Feature: architectural-reverse-engineer, Property 8: Dependency graph structural correctness
    **Validates: Requirements 4.1, 4.2**
    """
    with _mock_graphviz():
        result = generate_dependency_graph(model)

    sd = result.structured_data

    # -- Nodes --
    expected_node_ids = {ce.element.name for ce in model.elements}
    actual_node_ids = {n["id"] for n in sd["nodes"]}
    assert actual_node_ids == expected_node_ids, (
        f"Node mismatch: expected {expected_node_ids}, got {actual_node_ids}"
    )
    # No duplicates
    assert len(sd["nodes"]) == len(expected_node_ids)

    # -- Edges --
    expected_edges = {
        (r.source, r.target)
        for r in model.relationships
        if r.relationship_type == "depends_on"
    }
    actual_edges = {(e["source"], e["target"]) for e in sd["edges"]}
    assert actual_edges == expected_edges, (
        f"Edge mismatch: expected {expected_edges}, got {actual_edges}"
    )
    # No duplicates
    assert len(sd["edges"]) == len(expected_edges)


# ---------------------------------------------------------------------------
# Property 9: Circular dependency highlighting
# ---------------------------------------------------------------------------


def _find_cycle_participants(
    names: list[str], edges: list[tuple[str, str]]
) -> tuple[set[str], set[tuple[str, str]]]:
    """Brute-force DFS to find all nodes and edges on *any* cycle.

    This is an independent reference implementation used to verify the
    diagram generator's cycle detection.
    """
    adj: dict[str, list[str]] = {n: [] for n in names}
    for s, t in edges:
        adj.setdefault(s, []).append(t)

    # For each node, check if it can reach itself
    cycle_nodes: set[str] = set()
    cycle_edges: set[tuple[str, str]] = set()

    for start in names:
        # BFS/DFS: can we reach `start` from `start`?
        visited: set[str] = set()
        stack = list(adj.get(start, []))
        parent_map: dict[str, str] = {n: start for n in stack}
        reachable = False
        while stack:
            node = stack.pop()
            if node == start:
                reachable = True
                break
            if node in visited:
                continue
            visited.add(node)
            for nb in adj.get(node, []):
                if nb not in visited or nb == start:
                    stack.append(nb)
                    if nb not in parent_map:
                        parent_map[nb] = node
        if reachable:
            cycle_nodes.add(start)

    # An edge (u, v) is on a cycle iff both u and v are cycle nodes AND
    # removing the edge would break reachability from v back to u.
    # Simpler correct check: edge (u,v) is on a cycle iff v can reach u.
    for s, t in edges:
        if s in cycle_nodes and t in cycle_nodes:
            # Check if t can reach s
            visited2: set[str] = set()
            stack2 = [t]
            found = False
            while stack2:
                node = stack2.pop()
                if node == s:
                    found = True
                    break
                if node in visited2:
                    continue
                visited2.add(node)
                for nb in adj.get(node, []):
                    if nb not in visited2 or nb == s:
                        stack2.append(nb)
            if found:
                cycle_edges.add((s, t))

    return cycle_nodes, cycle_edges


@settings(max_examples=100, deadline=None)
@given(model=reconciled_models_with_cycle())
def test_circular_dependency_highlighting(model: ReconciledModel):
    """For any dependency graph with at least one cycle, nodes and edges
    participating in cycles are marked in_cycle=True and
    circular_dependencies is non-empty.

    # Feature: architectural-reverse-engineer, Property 9: Circular dependency highlighting
    **Validates: Requirements 4.3**
    """
    with _mock_graphviz():
        result = generate_dependency_graph(model)

    sd = result.structured_data

    # circular_dependencies must be non-empty (we forced at least one cycle)
    assert len(sd["circular_dependencies"]) > 0, (
        "Expected at least one circular dependency but got none"
    )

    # Compute reference cycle participants independently
    names = [ce.element.name for ce in model.elements]
    edges = [
        (r.source, r.target)
        for r in model.relationships
        if r.relationship_type == "depends_on"
    ]
    ref_cycle_nodes, ref_cycle_edges = _find_cycle_participants(names, edges)

    # Every node flagged in_cycle by the generator must actually be on a cycle
    for node_data in sd["nodes"]:
        if node_data["in_cycle"]:
            assert node_data["id"] in ref_cycle_nodes, (
                f"Node '{node_data['id']}' marked in_cycle but is not on any cycle"
            )

    # Every edge flagged in_cycle by the generator must actually be on a cycle
    for edge_data in sd["edges"]:
        if edge_data["in_cycle"]:
            assert (edge_data["source"], edge_data["target"]) in ref_cycle_edges, (
                f"Edge ({edge_data['source']}, {edge_data['target']}) marked "
                f"in_cycle but is not on any cycle"
            )

    # Every node that IS on a cycle must be flagged in_cycle
    flagged_nodes = {n["id"] for n in sd["nodes"] if n["in_cycle"]}
    assert ref_cycle_nodes <= flagged_nodes, (
        f"Cycle nodes not flagged: {ref_cycle_nodes - flagged_nodes}"
    )

    # Every edge that IS on a cycle must be flagged in_cycle
    flagged_edges = {
        (e["source"], e["target"]) for e in sd["edges"] if e["in_cycle"]
    }
    assert ref_cycle_edges <= flagged_edges, (
        f"Cycle edges not flagged: {ref_cycle_edges - flagged_edges}"
    )


# ---------------------------------------------------------------------------
# Strategies for component diagram tests
# ---------------------------------------------------------------------------

_element_type = st.sampled_from(["service", "class", "module", "interface", "library", "database"])
_leanix_type = st.sampled_from([
    "Organization", "Interface", "Data Object", "IT Component",
])
_relationship_type = st.sampled_from([
    "REST", "gRPC", "event", "depends_on", "implements", "calls",
])


@st.composite
def component_models(draw: st.DrawFn) -> ReconciledModel:
    """Generate a ReconciledModel with varied element types and relationship types."""
    names = draw(
        st.lists(_module_name, min_size=1, max_size=15, unique=True)
    )
    elements = [
        ClassifiedElement(
            element=Element(
                name=n,
                element_type=draw(_element_type),
                metadata={},
            ),
            leanix_type=draw(_leanix_type),
            confidence=draw(st.floats(min_value=0.0, max_value=1.0)),
        )
        for n in names
    ]

    # Draw a subset of all possible directed pairs as relationships
    possible_edges = [(s, t) for s in names for t in names if s != t]
    if possible_edges:
        edges = draw(
            st.lists(
                st.sampled_from(possible_edges),
                max_size=min(len(possible_edges), 30),
                unique=True,
            )
        )
    else:
        edges = []

    relationships = [
        Relationship(source=s, target=t, relationship_type=draw(_relationship_type))
        for s, t in edges
    ]

    return ReconciledModel(elements=elements, relationships=relationships)


# ---------------------------------------------------------------------------
# Property 11: Component diagram labeling completeness
# ---------------------------------------------------------------------------

from app.diagram_generator import generate_component_diagram


@settings(max_examples=100, deadline=None)
@given(model=component_models())
def test_component_diagram_labeling_completeness(model: ReconciledModel):
    """For any component in a generated component diagram, the component node
    should be labeled with its name, type, and associated LeanIX object type.
    Every inter-component relationship should have a labeled connector
    indicating the interface type.

    # Feature: architectural-reverse-engineer, Property 11: Component diagram labeling completeness
    **Validates: Requirements 5.1, 5.2, 5.3**
    """
    with _mock_graphviz():
        result = generate_component_diagram(model)

    sd = result.structured_data

    # -- Components --
    assert len(sd["components"]) == len(model.elements), (
        f"Expected {len(model.elements)} components, got {len(sd['components'])}"
    )

    # Build lookup from input elements for verification
    expected_components = {
        ce.element.name: {
            "name": ce.element.name,
            "type": ce.element.element_type,
            "leanix_type": ce.leanix_type,
        }
        for ce in model.elements
    }

    for comp in sd["components"]:
        # Each component must have name, type, and leanix_type fields
        assert "name" in comp, f"Component missing 'name' field: {comp}"
        assert "type" in comp, f"Component missing 'type' field: {comp}"
        assert "leanix_type" in comp, f"Component missing 'leanix_type' field: {comp}"

        # Values must match the input
        assert comp["name"] in expected_components, (
            f"Unexpected component name: {comp['name']}"
        )
        expected = expected_components[comp["name"]]
        assert comp["type"] == expected["type"], (
            f"Component '{comp['name']}' type mismatch: "
            f"expected {expected['type']!r}, got {comp['type']!r}"
        )
        assert comp["leanix_type"] == expected["leanix_type"], (
            f"Component '{comp['name']}' leanix_type mismatch: "
            f"expected {expected['leanix_type']!r}, got {comp['leanix_type']!r}"
        )

    # -- Connectors --
    assert len(sd["connectors"]) == len(model.relationships), (
        f"Expected {len(model.relationships)} connectors, got {len(sd['connectors'])}"
    )

    expected_connectors = [
        {
            "source": rel.source,
            "target": rel.target,
            "interface_type": rel.relationship_type,
        }
        for rel in model.relationships
    ]

    for conn in sd["connectors"]:
        # Each connector must have source, target, and interface_type fields
        assert "source" in conn, f"Connector missing 'source' field: {conn}"
        assert "target" in conn, f"Connector missing 'target' field: {conn}"
        assert "interface_type" in conn, f"Connector missing 'interface_type' field: {conn}"

    # Verify connectors match input relationships (order-preserving)
    for i, (actual, expected) in enumerate(zip(sd["connectors"], expected_connectors)):
        assert actual["source"] == expected["source"], (
            f"Connector {i} source mismatch: expected {expected['source']!r}, got {actual['source']!r}"
        )
        assert actual["target"] == expected["target"], (
            f"Connector {i} target mismatch: expected {expected['target']!r}, got {actual['target']!r}"
        )
        assert actual["interface_type"] == expected["interface_type"], (
            f"Connector {i} interface_type mismatch: "
            f"expected {expected['interface_type']!r}, got {actual['interface_type']!r}"
        )


# ---------------------------------------------------------------------------
# Strategies for UML class diagram tests
# ---------------------------------------------------------------------------

from app.diagram_generator import (
    generate_uml_class_diagram,
    generate_uml_sequence_diagram,
)

_oo_element_type = st.sampled_from(["class", "interface", "module"])
_class_rel_type = st.sampled_from(["inherits", "composition", "association", "implements"])


@st.composite
def oo_reconciled_models(draw: st.DrawFn) -> ReconciledModel:
    """Generate a ReconciledModel with OO structures (classes/interfaces/modules)
    and class-level relationships (inherits, composition, association, implements)."""
    names = draw(
        st.lists(_module_name, min_size=1, max_size=15, unique=True)
    )
    elements = [
        ClassifiedElement(
            element=Element(
                name=n,
                element_type=draw(_oo_element_type),
                metadata={},
            ),
            leanix_type=draw(st.sampled_from([
                "Organization", "Interface", "Data Object", "IT Component",
            ])),
            confidence=draw(st.floats(min_value=0.0, max_value=1.0)),
        )
        for n in names
    ]

    # Draw class-level relationships between OO elements
    possible_edges = [(s, t) for s in names for t in names if s != t]
    if possible_edges:
        edges = draw(
            st.lists(
                st.sampled_from(possible_edges),
                max_size=min(len(possible_edges), 20),
                unique=True,
            )
        )
    else:
        edges = []

    relationships = [
        Relationship(source=s, target=t, relationship_type=draw(_class_rel_type))
        for s, t in edges
    ]

    return ReconciledModel(elements=elements, relationships=relationships)


# ---------------------------------------------------------------------------
# Property 12: UML class diagram coverage
# ---------------------------------------------------------------------------


@settings(max_examples=100, deadline=None)
@given(model=oo_reconciled_models())
def test_uml_class_diagram_coverage(model: ReconciledModel):
    """For any reconciled analysis model containing OO structures, the Diagram
    Generator should produce a UML class diagram containing a class node for
    each identified OO structure.

    # Feature: architectural-reverse-engineer, Property 12: UML class diagram coverage
    **Validates: Requirements 6.1**
    """
    with _mock_graphviz(), \
         patch("app.diagram_generator._render_plantuml", return_value=b"fake-png"):
        result = generate_uml_class_diagram(model)

    sd = result.structured_data

    # All OO elements should appear as classes in the diagram
    oo_names = {
        ce.element.name for ce in model.elements
        if ce.element.element_type in ("class", "interface", "module")
    }
    actual_class_names = {c["name"] for c in sd["classes"]}
    assert actual_class_names == oo_names, (
        f"Class node mismatch: expected {oo_names}, got {actual_class_names}"
    )

    # Each class node should have name, type, and leanix_type
    for cls in sd["classes"]:
        assert "name" in cls
        assert "type" in cls
        assert "leanix_type" in cls


# ---------------------------------------------------------------------------
# Strategies for UML sequence diagram tests
# ---------------------------------------------------------------------------


@st.composite
def service_interaction_models(draw: st.DrawFn) -> ReconciledModel:
    """Generate a ReconciledModel with at least one 'calls' relationship."""
    names = draw(
        st.lists(_module_name, min_size=2, max_size=15, unique=True)
    )
    elements = [
        ClassifiedElement(
            element=Element(
                name=n,
                element_type=draw(st.sampled_from(["service", "class", "module"])),
                metadata={},
            ),
            leanix_type="IT Component",
            confidence=0.9,
        )
        for n in names
    ]

    # Ensure at least one "calls" relationship
    possible_edges = [(s, t) for s in names for t in names if s != t]
    # Draw at least 1 calls edge
    calls_edges = draw(
        st.lists(
            st.sampled_from(possible_edges),
            min_size=1,
            max_size=min(len(possible_edges), 20),
            unique=True,
        )
    )

    relationships = [
        Relationship(source=s, target=t, relationship_type="calls")
        for s, t in calls_edges
    ]

    # Optionally add some non-calls relationships
    remaining = [(s, t) for s, t in possible_edges if (s, t) not in calls_edges]
    if remaining:
        extra = draw(
            st.lists(
                st.sampled_from(remaining),
                max_size=min(len(remaining), 10),
                unique=True,
            )
        )
        for s, t in extra:
            relationships.append(
                Relationship(source=s, target=t, relationship_type=draw(
                    st.sampled_from(["depends_on", "implements", "inherits"])
                ))
            )

    return ReconciledModel(elements=elements, relationships=relationships)


# ---------------------------------------------------------------------------
# Property 13: UML sequence diagram coverage
# ---------------------------------------------------------------------------


@settings(max_examples=100, deadline=None)
@given(model=service_interaction_models())
def test_uml_sequence_diagram_coverage(model: ReconciledModel):
    """For any reconciled analysis model containing service interaction flows
    (calls relationships), the Diagram Generator should produce at least one
    UML sequence diagram representing those interactions.

    # Feature: architectural-reverse-engineer, Property 13: UML sequence diagram coverage
    **Validates: Requirements 6.2**
    """
    with patch("app.diagram_generator._render_plantuml", return_value=b"fake-png"):
        result = generate_uml_sequence_diagram(model)

    sd = result.structured_data

    # There must be at least one participant and one message
    assert len(sd["participants"]) >= 2, (
        f"Expected at least 2 participants, got {len(sd['participants'])}"
    )
    assert len(sd["messages"]) >= 1, (
        f"Expected at least 1 message, got {len(sd['messages'])}"
    )

    # All calls relationships should appear as messages
    calls_rels = [
        r for r in model.relationships if r.relationship_type == "calls"
    ]
    expected_messages = {(r.source, r.target) for r in calls_rels}
    actual_messages = {(m["from"], m["to"]) for m in sd["messages"]}
    assert actual_messages == expected_messages, (
        f"Message mismatch: expected {expected_messages}, got {actual_messages}"
    )

    # All participants in calls should appear
    expected_participants = set()
    for r in calls_rels:
        expected_participants.add(r.source)
        expected_participants.add(r.target)
    actual_participants = {p["name"] for p in sd["participants"]}
    assert expected_participants == actual_participants, (
        f"Participant mismatch: expected {expected_participants}, got {actual_participants}"
    )

    # Diagram type should be uml_sequence
    assert result.diagram_type == "uml_sequence"

    # Source file should contain PlantUML markers
    assert result.source_file is not None
    assert "@startuml" in result.source_file
    assert "@enduml" in result.source_file


# ---------------------------------------------------------------------------
# Strategies for LLD tests
# ---------------------------------------------------------------------------

from app.diagram_generator import generate_lld
from app.models import ComponentModel

_internal_name = st.text(alphabet=_name_alphabet, min_size=1, max_size=20)


@st.composite
def component_models_for_lld(draw: st.DrawFn) -> ComponentModel:
    """Generate a ComponentModel with internal classes, functions, and data transformations."""
    name = draw(_module_name)
    classes = draw(st.lists(_internal_name, min_size=0, max_size=5, unique=True))
    functions = draw(st.lists(
        _internal_name.filter(lambda x: x not in classes),
        min_size=0, max_size=5, unique=True,
    ))
    # Filter out names already used
    used = set(classes) | set(functions)
    data_transformations = draw(st.lists(
        _internal_name.filter(lambda x: x not in used),
        min_size=0, max_size=5, unique=True,
    ))

    all_ids = classes + functions + data_transformations
    if len(all_ids) >= 2:
        possible_flows = [(s, t) for s in all_ids for t in all_ids if s != t]
        data_flows = draw(
            st.lists(
                st.sampled_from(possible_flows),
                max_size=min(len(possible_flows), 10),
                unique=True,
            )
        )
    else:
        data_flows = []

    return ComponentModel(
        name=name,
        classes=classes,
        functions=functions,
        data_transformations=data_transformations,
        data_flows=data_flows,
    )


@st.composite
def nonempty_component_models(draw: st.DrawFn) -> ComponentModel:
    """Generate a ComponentModel guaranteed to have at least one internal element."""
    name = draw(_module_name)
    classes = draw(st.lists(_internal_name, min_size=1, max_size=5, unique=True))
    functions = draw(st.lists(
        _internal_name.filter(lambda x: x not in classes),
        min_size=1, max_size=5, unique=True,
    ))
    used = set(classes) | set(functions)
    data_transformations = draw(st.lists(
        _internal_name.filter(lambda x: x not in used),
        min_size=1, max_size=5, unique=True,
    ))

    all_ids = classes + functions + data_transformations
    possible_flows = [(s, t) for s in all_ids for t in all_ids if s != t]
    data_flows = draw(
        st.lists(
            st.sampled_from(possible_flows),
            max_size=min(len(possible_flows), 10),
            unique=True,
        )
    )

    return ComponentModel(
        name=name,
        classes=classes,
        functions=functions,
        data_transformations=data_transformations,
        data_flows=data_flows,
    )


# ---------------------------------------------------------------------------
# Property 14: LLD internal structure coverage
# ---------------------------------------------------------------------------


@settings(max_examples=100, deadline=None)
@given(component=nonempty_component_models())
def test_lld_internal_structure_coverage(component: ComponentModel):
    """For any analyzed component with internal classes, functions, and data
    transformations, the generated LLD should contain labeled nodes for each
    internal element.

    # Feature: architectural-reverse-engineer, Property 14: LLD internal structure coverage
    **Validates: Requirements 7.1, 7.2**
    """
    with _mock_graphviz():
        result = generate_lld(component)

    sd = result.structured_data

    # All classes should appear as nodes with type "class"
    class_nodes = [n for n in sd["nodes"] if n["type"] == "class"]
    assert {n["id"] for n in class_nodes} == set(component.classes), (
        f"Class node mismatch: expected {set(component.classes)}, "
        f"got {set(n['id'] for n in class_nodes)}"
    )

    # All functions should appear as nodes with type "function"
    fn_nodes = [n for n in sd["nodes"] if n["type"] == "function"]
    assert {n["id"] for n in fn_nodes} == set(component.functions), (
        f"Function node mismatch: expected {set(component.functions)}, "
        f"got {set(n['id'] for n in fn_nodes)}"
    )

    # All data transformations should appear as nodes with type "data_transformation"
    dt_nodes = [n for n in sd["nodes"] if n["type"] == "data_transformation"]
    assert {n["id"] for n in dt_nodes} == set(component.data_transformations), (
        f"Data transformation node mismatch: expected {set(component.data_transformations)}, "
        f"got {set(n['id'] for n in dt_nodes)}"
    )

    # Every node should have a non-empty label
    for node in sd["nodes"]:
        assert node["label"], f"Node {node['id']} has empty label"

    # Total node count should match
    expected_count = len(component.classes) + len(component.functions) + len(component.data_transformations)
    assert len(sd["nodes"]) == expected_count

    # Component name should be in structured data
    assert sd["component_name"] == component.name

    # Diagram type should be lld
    assert result.diagram_type == "lld"


# ---------------------------------------------------------------------------
# Property 10: Diagram dual output format
# ---------------------------------------------------------------------------

from app.diagram_generator import generate_dependency_graph as _gen_dep_graph


@st.composite
def any_diagram_input(draw: st.DrawFn):
    """Generate an input suitable for any diagram generator function.
    Returns a tuple of (generator_function, input, needs_plantuml_mock)."""
    choice = draw(st.sampled_from([
        "dependency_graph", "component_diagram",
        "uml_class", "uml_sequence", "lld",
    ]))

    if choice == "dependency_graph":
        model = draw(reconciled_models())
        return ("dependency_graph", model, False)
    elif choice == "component_diagram":
        model = draw(component_models())
        return ("component_diagram", model, False)
    elif choice == "uml_class":
        model = draw(oo_reconciled_models())
        return ("uml_class", model, True)
    elif choice == "uml_sequence":
        model = draw(service_interaction_models())
        return ("uml_sequence", model, True)
    else:  # lld
        comp = draw(component_models_for_lld())
        return ("lld", comp, False)


@settings(max_examples=100, deadline=None)
@given(diagram_input=any_diagram_input())
def test_diagram_dual_output_format(diagram_input):
    """For any diagram generation, the output should contain both a non-empty
    rendered image and a non-empty structured data file or source file.

    # Feature: architectural-reverse-engineer, Property 10: Diagram dual output format
    **Validates: Requirements 4.4, 5.4, 6.4, 7.3**
    """
    diagram_type, model_input, needs_plantuml = diagram_input

    with _mock_graphviz(), \
         patch("app.diagram_generator._render_plantuml", return_value=b"fake-png"):
        if diagram_type == "dependency_graph":
            result = _gen_dep_graph(model_input)
        elif diagram_type == "component_diagram":
            result = generate_component_diagram(model_input)
        elif diagram_type == "uml_class":
            result = generate_uml_class_diagram(model_input)
        elif diagram_type == "uml_sequence":
            result = generate_uml_sequence_diagram(model_input)
        else:  # lld
            result = generate_lld(model_input)

    # Rendered image must be non-empty bytes
    assert isinstance(result.rendered_image, bytes), (
        f"rendered_image should be bytes, got {type(result.rendered_image)}"
    )
    assert len(result.rendered_image) > 0, (
        f"rendered_image should be non-empty for {diagram_type}"
    )

    # Image format must be valid
    assert result.image_format in ("png", "svg"), (
        f"image_format should be 'png' or 'svg', got {result.image_format!r}"
    )

    # Must have non-empty structured data OR non-empty source file (or both)
    has_structured = bool(result.structured_data)
    has_source = result.source_file is not None and len(result.source_file) > 0
    assert has_structured or has_source, (
        f"Diagram {diagram_type} must have non-empty structured_data or source_file. "
        f"structured_data={result.structured_data}, source_file={result.source_file!r}"
    )
