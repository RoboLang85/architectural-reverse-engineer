"""Unit tests for the Diagram Generator – dependency graph generation.

Graphviz CLI is not guaranteed to be installed in CI, so rendering is
mocked where necessary.  Structural / cycle-detection logic is tested
without mocks.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from app.diagram_generator import (
    _cycle_edges_and_nodes,
    _detect_cycles,
    generate_component_diagram,
    generate_dependency_graph,
)
from app.errors import RenderError
from app.models import (
    ClassifiedElement,
    DiagramOutput,
    Element,
    ReconciledModel,
    Relationship,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _element(name: str) -> ClassifiedElement:
    return ClassifiedElement(
        element=Element(name=name, element_type="module", metadata={}),
        leanix_type="IT Component",
        confidence=0.9,
    )


def _dep(source: str, target: str) -> Relationship:
    return Relationship(source=source, target=target, relationship_type="depends_on")


def _model(
    names: list[str],
    deps: list[tuple[str, str]],
) -> ReconciledModel:
    return ReconciledModel(
        elements=[_element(n) for n in names],
        relationships=[_dep(s, t) for s, t in deps],
    )


# ---------------------------------------------------------------------------
# _detect_cycles
# ---------------------------------------------------------------------------


class TestDetectCycles:
    def test_no_cycles(self):
        adj = {"A": ["B"], "B": ["C"], "C": []}
        assert _detect_cycles(adj) == []

    def test_simple_cycle(self):
        adj = {"A": ["B"], "B": ["A"]}
        cycles = _detect_cycles(adj)
        assert len(cycles) == 1
        assert set(cycles[0]) == {"A", "B"}

    def test_self_loop(self):
        adj = {"A": ["A"]}
        cycles = _detect_cycles(adj)
        assert len(cycles) == 1
        assert cycles[0] == ["A"]

    def test_triangle_cycle(self):
        adj = {"A": ["B"], "B": ["C"], "C": ["A"]}
        cycles = _detect_cycles(adj)
        assert len(cycles) == 1
        assert set(cycles[0]) == {"A", "B", "C"}

    def test_disconnected_no_cycle(self):
        adj = {"A": [], "B": [], "C": []}
        assert _detect_cycles(adj) == []

    def test_multiple_cycles(self):
        adj = {"A": ["B"], "B": ["A", "C"], "C": ["D"], "D": ["C"]}
        cycles = _detect_cycles(adj)
        assert len(cycles) == 2


# ---------------------------------------------------------------------------
# _cycle_edges_and_nodes
# ---------------------------------------------------------------------------


class TestCycleEdgesAndNodes:
    def test_empty(self):
        nodes, edges = _cycle_edges_and_nodes({}, [])
        assert nodes == set()
        assert edges == set()

    def test_single_cycle(self):
        adj = {"A": ["B"], "B": ["C"], "C": ["A"]}
        all_edges = [("A", "B"), ("B", "C"), ("C", "A")]
        nodes, edges = _cycle_edges_and_nodes(adj, all_edges)
        assert nodes == {"A", "B", "C"}
        assert edges == {("A", "B"), ("B", "C"), ("C", "A")}


# ---------------------------------------------------------------------------
# generate_dependency_graph – structured data (mock rendering)
# ---------------------------------------------------------------------------


class TestGenerateDependencyGraphStructure:
    """Test structured_data correctness with mocked Graphviz rendering."""

    @patch("app.diagram_generator.graphviz.Digraph")
    def test_nodes_match_elements(self, mock_digraph_cls):
        mock_graph = MagicMock()
        mock_graph.pipe.return_value = b"fake-png"
        mock_graph.source = "digraph {}"
        mock_digraph_cls.return_value = mock_graph

        model = _model(["A", "B", "C"], [("A", "B")])
        result = generate_dependency_graph(model)

        assert isinstance(result, DiagramOutput)
        assert result.diagram_type == "dependency_graph"
        node_ids = [n["id"] for n in result.structured_data["nodes"]]
        assert node_ids == ["A", "B", "C"]

    @patch("app.diagram_generator.graphviz.Digraph")
    def test_edges_match_depends_on(self, mock_digraph_cls):
        mock_graph = MagicMock()
        mock_graph.pipe.return_value = b"fake-png"
        mock_graph.source = "digraph {}"
        mock_digraph_cls.return_value = mock_graph

        model = _model(["A", "B", "C"], [("A", "B"), ("B", "C")])
        result = generate_dependency_graph(model)

        edges = result.structured_data["edges"]
        assert len(edges) == 2
        assert edges[0]["source"] == "A"
        assert edges[0]["target"] == "B"
        assert edges[1]["source"] == "B"
        assert edges[1]["target"] == "C"

    @patch("app.diagram_generator.graphviz.Digraph")
    def test_non_depends_on_relationships_excluded(self, mock_digraph_cls):
        mock_graph = MagicMock()
        mock_graph.pipe.return_value = b"fake-png"
        mock_graph.source = "digraph {}"
        mock_digraph_cls.return_value = mock_graph

        model = ReconciledModel(
            elements=[_element("A"), _element("B")],
            relationships=[
                Relationship(source="A", target="B", relationship_type="calls"),
            ],
        )
        result = generate_dependency_graph(model)
        assert result.structured_data["edges"] == []

    @patch("app.diagram_generator.graphviz.Digraph")
    def test_circular_dependency_detected(self, mock_digraph_cls):
        mock_graph = MagicMock()
        mock_graph.pipe.return_value = b"fake-png"
        mock_graph.source = "digraph {}"
        mock_digraph_cls.return_value = mock_graph

        model = _model(["A", "B"], [("A", "B"), ("B", "A")])
        result = generate_dependency_graph(model)

        assert len(result.structured_data["circular_dependencies"]) >= 1
        # Nodes in cycle should be flagged
        for node in result.structured_data["nodes"]:
            assert node["in_cycle"] is True
        # Edges in cycle should be flagged
        for edge in result.structured_data["edges"]:
            assert edge["in_cycle"] is True

    @patch("app.diagram_generator.graphviz.Digraph")
    def test_no_circular_dependency(self, mock_digraph_cls):
        mock_graph = MagicMock()
        mock_graph.pipe.return_value = b"fake-png"
        mock_graph.source = "digraph {}"
        mock_digraph_cls.return_value = mock_graph

        model = _model(["A", "B", "C"], [("A", "B"), ("B", "C")])
        result = generate_dependency_graph(model)

        assert result.structured_data["circular_dependencies"] == []
        for node in result.structured_data["nodes"]:
            assert node["in_cycle"] is False
        for edge in result.structured_data["edges"]:
            assert edge["in_cycle"] is False

    @patch("app.diagram_generator.graphviz.Digraph")
    def test_empty_model(self, mock_digraph_cls):
        mock_graph = MagicMock()
        mock_graph.pipe.return_value = b"fake-png"
        mock_graph.source = "digraph {}"
        mock_digraph_cls.return_value = mock_graph

        model = ReconciledModel()
        result = generate_dependency_graph(model)

        assert result.structured_data["nodes"] == []
        assert result.structured_data["edges"] == []
        assert result.structured_data["circular_dependencies"] == []

    @patch("app.diagram_generator.graphviz.Digraph")
    def test_image_format_svg(self, mock_digraph_cls):
        mock_graph = MagicMock()
        mock_graph.pipe.return_value = b"<svg>fake</svg>"
        mock_graph.source = "digraph {}"
        mock_digraph_cls.return_value = mock_graph

        model = _model(["X"], [])
        result = generate_dependency_graph(model, image_format="svg")

        assert result.image_format == "svg"
        assert result.rendered_image == b"<svg>fake</svg>"
        mock_digraph_cls.assert_called_once()
        call_kwargs = mock_digraph_cls.call_args
        assert call_kwargs[1]["format"] == "svg"


# ---------------------------------------------------------------------------
# generate_dependency_graph – rendering error
# ---------------------------------------------------------------------------


class TestGenerateDependencyGraphRenderError:
    @patch("app.diagram_generator.graphviz.Digraph")
    def test_render_error_raised(self, mock_digraph_cls):
        mock_graph = MagicMock()
        mock_graph.pipe.side_effect = RuntimeError("dot not found")
        mock_graph.source = "digraph {}"
        mock_digraph_cls.return_value = mock_graph

        model = _model(["A"], [])
        with pytest.raises(RenderError, match="Graphviz rendering failed"):
            generate_dependency_graph(model)


# ---------------------------------------------------------------------------
# generate_dependency_graph – Graphviz API calls
# ---------------------------------------------------------------------------


class TestGraphvizAPICalls:
    @patch("app.diagram_generator.graphviz.Digraph")
    def test_cycle_nodes_highlighted_red(self, mock_digraph_cls):
        mock_graph = MagicMock()
        mock_graph.pipe.return_value = b"fake"
        mock_graph.source = "digraph {}"
        mock_digraph_cls.return_value = mock_graph

        model = _model(["A", "B"], [("A", "B"), ("B", "A")])
        generate_dependency_graph(model)

        # Collect all node() calls
        node_calls = {
            call.args[0]: call.kwargs
            for call in mock_graph.node.call_args_list
        }
        assert node_calls["A"]["fillcolor"] == "#ff6666"
        assert node_calls["B"]["fillcolor"] == "#ff6666"

    @patch("app.diagram_generator.graphviz.Digraph")
    def test_cycle_edges_highlighted_red(self, mock_digraph_cls):
        mock_graph = MagicMock()
        mock_graph.pipe.return_value = b"fake"
        mock_graph.source = "digraph {}"
        mock_digraph_cls.return_value = mock_graph

        model = _model(["A", "B"], [("A", "B"), ("B", "A")])
        generate_dependency_graph(model)

        edge_calls = [
            (call.args[0], call.args[1], call.kwargs)
            for call in mock_graph.edge.call_args_list
        ]
        for src, tgt, kwargs in edge_calls:
            assert kwargs["color"] == "red"
            assert kwargs["penwidth"] == "2.0"

    @patch("app.diagram_generator.graphviz.Digraph")
    def test_non_cycle_nodes_default_color(self, mock_digraph_cls):
        mock_graph = MagicMock()
        mock_graph.pipe.return_value = b"fake"
        mock_graph.source = "digraph {}"
        mock_digraph_cls.return_value = mock_graph

        model = _model(["A", "B"], [("A", "B")])
        generate_dependency_graph(model)

        node_calls = {
            call.args[0]: call.kwargs
            for call in mock_graph.node.call_args_list
        }
        assert node_calls["A"]["fillcolor"] == "#d0e8ff"
        assert node_calls["B"]["fillcolor"] == "#d0e8ff"

    @patch("app.diagram_generator.graphviz.Digraph")
    def test_source_file_populated(self, mock_digraph_cls):
        mock_graph = MagicMock()
        mock_graph.pipe.return_value = b"fake"
        mock_graph.source = "digraph { A -> B }"
        mock_digraph_cls.return_value = mock_graph

        model = _model(["A", "B"], [("A", "B")])
        result = generate_dependency_graph(model)
        assert result.source_file == "digraph { A -> B }"


# ---------------------------------------------------------------------------
# Helpers for component diagram tests
# ---------------------------------------------------------------------------


def _classified(name: str, element_type: str = "service", leanix_type: str = "IT Component") -> ClassifiedElement:
    return ClassifiedElement(
        element=Element(name=name, element_type=element_type, metadata={}),
        leanix_type=leanix_type,
        confidence=0.9,
    )


def _rel(source: str, target: str, rel_type: str = "REST") -> Relationship:
    return Relationship(source=source, target=target, relationship_type=rel_type)


def _component_model(
    elements: list[ClassifiedElement],
    relationships: list[Relationship] | None = None,
) -> ReconciledModel:
    return ReconciledModel(
        elements=elements,
        relationships=relationships or [],
    )


# ---------------------------------------------------------------------------
# generate_component_diagram – structured data
# ---------------------------------------------------------------------------


class TestComponentDiagramStructure:
    """Test structured_data correctness with mocked Graphviz rendering."""

    @patch("app.diagram_generator.graphviz.Digraph")
    def test_components_contain_name_type_leanix(self, mock_digraph_cls):
        mock_graph = MagicMock()
        mock_graph.pipe.return_value = b"fake-png"
        mock_graph.source = "digraph {}"
        mock_digraph_cls.return_value = mock_graph

        model = _component_model([
            _classified("OrderService", "service", "IT Component"),
            _classified("UserDB", "database", "Data Object"),
        ])
        result = generate_component_diagram(model)

        assert result.diagram_type == "component"
        comps = result.structured_data["components"]
        assert len(comps) == 2
        assert comps[0] == {"name": "OrderService", "type": "service", "leanix_type": "IT Component"}
        assert comps[1] == {"name": "UserDB", "type": "database", "leanix_type": "Data Object"}

    @patch("app.diagram_generator.graphviz.Digraph")
    def test_connectors_contain_source_target_interface(self, mock_digraph_cls):
        mock_graph = MagicMock()
        mock_graph.pipe.return_value = b"fake-png"
        mock_graph.source = "digraph {}"
        mock_digraph_cls.return_value = mock_graph

        model = _component_model(
            [_classified("A"), _classified("B")],
            [_rel("A", "B", "gRPC"), _rel("B", "A", "event")],
        )
        result = generate_component_diagram(model)

        conns = result.structured_data["connectors"]
        assert len(conns) == 2
        assert conns[0] == {"source": "A", "target": "B", "interface_type": "gRPC"}
        assert conns[1] == {"source": "B", "target": "A", "interface_type": "event"}

    @patch("app.diagram_generator.graphviz.Digraph")
    def test_empty_model(self, mock_digraph_cls):
        mock_graph = MagicMock()
        mock_graph.pipe.return_value = b"fake-png"
        mock_graph.source = "digraph {}"
        mock_digraph_cls.return_value = mock_graph

        model = ReconciledModel()
        result = generate_component_diagram(model)

        assert result.structured_data["components"] == []
        assert result.structured_data["connectors"] == []

    @patch("app.diagram_generator.graphviz.Digraph")
    def test_all_relationship_types_included(self, mock_digraph_cls):
        """All relationships (not just depends_on) become connectors."""
        mock_graph = MagicMock()
        mock_graph.pipe.return_value = b"fake-png"
        mock_graph.source = "digraph {}"
        mock_digraph_cls.return_value = mock_graph

        model = _component_model(
            [_classified("A"), _classified("B")],
            [
                _rel("A", "B", "REST"),
                Relationship(source="A", target="B", relationship_type="depends_on"),
                _rel("A", "B", "event"),
            ],
        )
        result = generate_component_diagram(model)

        conns = result.structured_data["connectors"]
        assert len(conns) == 3
        iface_types = [c["interface_type"] for c in conns]
        assert "REST" in iface_types
        assert "depends_on" in iface_types
        assert "event" in iface_types


# ---------------------------------------------------------------------------
# generate_component_diagram – output format
# ---------------------------------------------------------------------------


class TestComponentDiagramOutput:
    @patch("app.diagram_generator.graphviz.Digraph")
    def test_default_png_format(self, mock_digraph_cls):
        mock_graph = MagicMock()
        mock_graph.pipe.return_value = b"fake-png"
        mock_graph.source = "digraph {}"
        mock_digraph_cls.return_value = mock_graph

        result = generate_component_diagram(_component_model([_classified("X")]))

        assert result.image_format == "png"
        assert result.rendered_image == b"fake-png"

    @patch("app.diagram_generator.graphviz.Digraph")
    def test_svg_format(self, mock_digraph_cls):
        mock_graph = MagicMock()
        mock_graph.pipe.return_value = b"<svg>fake</svg>"
        mock_graph.source = "digraph {}"
        mock_digraph_cls.return_value = mock_graph

        result = generate_component_diagram(
            _component_model([_classified("X")]),
            image_format="svg",
        )

        assert result.image_format == "svg"
        assert result.rendered_image == b"<svg>fake</svg>"

    @patch("app.diagram_generator.graphviz.Digraph")
    def test_source_file_populated(self, mock_digraph_cls):
        mock_graph = MagicMock()
        mock_graph.pipe.return_value = b"fake"
        mock_graph.source = "digraph { component }"
        mock_digraph_cls.return_value = mock_graph

        result = generate_component_diagram(_component_model([_classified("A")]))
        assert result.source_file == "digraph { component }"


# ---------------------------------------------------------------------------
# generate_component_diagram – Graphviz API calls
# ---------------------------------------------------------------------------


class TestComponentDiagramGraphvizCalls:
    @patch("app.diagram_generator.graphviz.Digraph")
    def test_nodes_use_component_shape(self, mock_digraph_cls):
        mock_graph = MagicMock()
        mock_graph.pipe.return_value = b"fake"
        mock_graph.source = "digraph {}"
        mock_digraph_cls.return_value = mock_graph

        generate_component_diagram(_component_model([
            _classified("Svc", "service", "IT Component"),
        ]))

        node_calls = {
            call.args[0]: call.kwargs
            for call in mock_graph.node.call_args_list
        }
        assert "Svc" in node_calls
        assert node_calls["Svc"]["shape"] == "component"
        assert "service" in node_calls["Svc"]["label"]
        assert "IT Component" in node_calls["Svc"]["label"]
        assert "Svc" in node_calls["Svc"]["label"]

    @patch("app.diagram_generator.graphviz.Digraph")
    def test_edges_labeled_with_interface_type(self, mock_digraph_cls):
        mock_graph = MagicMock()
        mock_graph.pipe.return_value = b"fake"
        mock_graph.source = "digraph {}"
        mock_digraph_cls.return_value = mock_graph

        generate_component_diagram(_component_model(
            [_classified("A"), _classified("B")],
            [_rel("A", "B", "gRPC")],
        ))

        edge_calls = [
            (call.args[0], call.args[1], call.kwargs)
            for call in mock_graph.edge.call_args_list
        ]
        assert len(edge_calls) == 1
        src, tgt, kwargs = edge_calls[0]
        assert src == "A"
        assert tgt == "B"
        assert kwargs["label"] == "gRPC"


# ---------------------------------------------------------------------------
# generate_component_diagram – rendering error
# ---------------------------------------------------------------------------


class TestComponentDiagramRenderError:
    @patch("app.diagram_generator.graphviz.Digraph")
    def test_render_error_raised(self, mock_digraph_cls):
        mock_graph = MagicMock()
        mock_graph.pipe.side_effect = RuntimeError("dot not found")
        mock_graph.source = "digraph {}"
        mock_digraph_cls.return_value = mock_graph

        with pytest.raises(RenderError, match="Graphviz rendering failed"):
            generate_component_diagram(_component_model([_classified("A")]))


# ---------------------------------------------------------------------------
# Imports for UML tests
# ---------------------------------------------------------------------------

from app.diagram_generator import (
    _render_plantuml,
    generate_uml_class_diagram,
    generate_uml_sequence_diagram,
)


# ---------------------------------------------------------------------------
# Helpers for UML tests
# ---------------------------------------------------------------------------


def _class_element(name: str, element_type: str = "class", leanix_type: str = "IT Component") -> ClassifiedElement:
    return ClassifiedElement(
        element=Element(name=name, element_type=element_type, metadata={}),
        leanix_type=leanix_type,
        confidence=0.9,
    )


def _uml_model(
    elements: list[ClassifiedElement],
    relationships: list[Relationship] | None = None,
) -> ReconciledModel:
    return ReconciledModel(
        elements=elements,
        relationships=relationships or [],
    )


# ---------------------------------------------------------------------------
# _render_plantuml
# ---------------------------------------------------------------------------


class TestRenderPlantUML:
    @patch("app.diagram_generator.subprocess.run")
    def test_successful_render(self, mock_run):
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout=b"fake-png-data",
            stderr=b"",
        )
        result = _render_plantuml("@startuml\nclass A\n@enduml", "png")
        assert result == b"fake-png-data"
        mock_run.assert_called_once()
        call_args = mock_run.call_args
        assert call_args[0][0] == ["plantuml", "-tpng", "-pipe"]

    @patch("app.diagram_generator.subprocess.run")
    def test_svg_format_flag(self, mock_run):
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout=b"<svg>fake</svg>",
            stderr=b"",
        )
        _render_plantuml("@startuml\n@enduml", "svg")
        call_args = mock_run.call_args
        assert call_args[0][0] == ["plantuml", "-tsvg", "-pipe"]

    @patch("app.diagram_generator.subprocess.run", side_effect=FileNotFoundError("plantuml not found"))
    def test_plantuml_not_found_raises_render_error(self, mock_run):
        with pytest.raises(RenderError, match="PlantUML CLI not found"):
            _render_plantuml("@startuml\n@enduml")

    @patch("app.diagram_generator.subprocess.run")
    def test_nonzero_exit_raises_render_error(self, mock_run):
        mock_run.return_value = MagicMock(
            returncode=1,
            stdout=b"",
            stderr=b"Error: syntax error",
        )
        with pytest.raises(RenderError, match="PlantUML rendering failed"):
            _render_plantuml("@startuml\nbad syntax\n@enduml")


# ---------------------------------------------------------------------------
# generate_uml_class_diagram – structured data
# ---------------------------------------------------------------------------


class TestUMLClassDiagramStructure:
    @patch("app.diagram_generator._render_plantuml", return_value=b"fake-png")
    def test_classes_from_oo_elements(self, mock_render):
        model = _uml_model([
            _class_element("UserService", "class"),
            _class_element("IRepository", "interface"),
            _class_element("Utils", "module"),
        ])
        result = generate_uml_class_diagram(model)

        assert result.diagram_type == "uml_class"
        classes = result.structured_data["classes"]
        assert len(classes) == 3
        names = [c["name"] for c in classes]
        assert "UserService" in names
        assert "IRepository" in names
        assert "Utils" in names

    @patch("app.diagram_generator._render_plantuml", return_value=b"fake-png")
    def test_non_oo_elements_excluded(self, mock_render):
        model = _uml_model([
            _class_element("UserService", "class"),
            _class_element("OrderQueue", "service"),  # not OO
        ])
        result = generate_uml_class_diagram(model)

        classes = result.structured_data["classes"]
        assert len(classes) == 1
        assert classes[0]["name"] == "UserService"

    @patch("app.diagram_generator._render_plantuml", return_value=b"fake-png")
    def test_relationships_filtered_to_class_types(self, mock_render):
        model = _uml_model(
            [_class_element("A", "class"), _class_element("B", "class")],
            [
                Relationship(source="A", target="B", relationship_type="inherits"),
                Relationship(source="A", target="B", relationship_type="composition"),
                Relationship(source="A", target="B", relationship_type="association"),
                Relationship(source="A", target="B", relationship_type="calls"),  # excluded
            ],
        )
        result = generate_uml_class_diagram(model)

        rels = result.structured_data["relationships"]
        assert len(rels) == 3
        rel_types = {r["relationship_type"] for r in rels}
        assert rel_types == {"inherits", "composition", "association"}

    @patch("app.diagram_generator._render_plantuml", return_value=b"fake-png")
    def test_relationships_only_between_oo_elements(self, mock_render):
        """Relationships referencing non-OO elements are excluded."""
        model = _uml_model(
            [_class_element("A", "class"), _class_element("B", "service")],
            [Relationship(source="A", target="B", relationship_type="inherits")],
        )
        result = generate_uml_class_diagram(model)

        rels = result.structured_data["relationships"]
        assert len(rels) == 0  # B is "service", not OO

    @patch("app.diagram_generator._render_plantuml", return_value=b"fake-png")
    def test_empty_model(self, mock_render):
        model = ReconciledModel()
        result = generate_uml_class_diagram(model)

        assert result.structured_data["classes"] == []
        assert result.structured_data["relationships"] == []

    @patch("app.diagram_generator._render_plantuml", return_value=b"fake-png")
    def test_class_data_includes_type_and_leanix(self, mock_render):
        model = _uml_model([_class_element("Foo", "interface", "Interface")])
        result = generate_uml_class_diagram(model)

        cls = result.structured_data["classes"][0]
        assert cls["name"] == "Foo"
        assert cls["type"] == "interface"
        assert cls["leanix_type"] == "Interface"


# ---------------------------------------------------------------------------
# generate_uml_class_diagram – PlantUML source
# ---------------------------------------------------------------------------


class TestUMLClassDiagramSource:
    @patch("app.diagram_generator._render_plantuml", return_value=b"fake-png")
    def test_source_contains_startuml_enduml(self, mock_render):
        model = _uml_model([_class_element("A", "class")])
        result = generate_uml_class_diagram(model)

        assert result.source_file is not None
        assert result.source_file.startswith("@startuml")
        assert result.source_file.endswith("@enduml")

    @patch("app.diagram_generator._render_plantuml", return_value=b"fake-png")
    def test_source_uses_interface_keyword(self, mock_render):
        model = _uml_model([_class_element("IRepo", "interface")])
        result = generate_uml_class_diagram(model)

        assert "interface IRepo" in result.source_file

    @patch("app.diagram_generator._render_plantuml", return_value=b"fake-png")
    def test_source_uses_class_keyword_for_class(self, mock_render):
        model = _uml_model([_class_element("Foo", "class")])
        result = generate_uml_class_diagram(model)

        assert "class Foo" in result.source_file

    @patch("app.diagram_generator._render_plantuml", return_value=b"fake-png")
    def test_source_uses_class_keyword_for_module(self, mock_render):
        model = _uml_model([_class_element("Utils", "module")])
        result = generate_uml_class_diagram(model)

        assert "class Utils" in result.source_file

    @patch("app.diagram_generator._render_plantuml", return_value=b"fake-png")
    def test_source_contains_inheritance_arrow(self, mock_render):
        model = _uml_model(
            [_class_element("A", "class"), _class_element("B", "class")],
            [Relationship(source="A", target="B", relationship_type="inherits")],
        )
        result = generate_uml_class_diagram(model)

        assert "A --|> B" in result.source_file

    @patch("app.diagram_generator._render_plantuml", return_value=b"fake-png")
    def test_source_contains_composition_arrow(self, mock_render):
        model = _uml_model(
            [_class_element("A", "class"), _class_element("B", "class")],
            [Relationship(source="A", target="B", relationship_type="composition")],
        )
        result = generate_uml_class_diagram(model)

        assert "A *-- B" in result.source_file

    @patch("app.diagram_generator._render_plantuml", return_value=b"fake-png")
    def test_source_contains_implements_arrow(self, mock_render):
        model = _uml_model(
            [_class_element("A", "class"), _class_element("B", "interface")],
            [Relationship(source="A", target="B", relationship_type="implements")],
        )
        result = generate_uml_class_diagram(model)

        assert "A ..|> B" in result.source_file


# ---------------------------------------------------------------------------
# generate_uml_class_diagram – output format
# ---------------------------------------------------------------------------


class TestUMLClassDiagramOutput:
    @patch("app.diagram_generator._render_plantuml", return_value=b"fake-png")
    def test_default_png_format(self, mock_render):
        result = generate_uml_class_diagram(_uml_model([_class_element("X", "class")]))
        assert result.image_format == "png"
        assert result.rendered_image == b"fake-png"

    @patch("app.diagram_generator._render_plantuml", return_value=b"<svg>fake</svg>")
    def test_svg_format(self, mock_render):
        result = generate_uml_class_diagram(
            _uml_model([_class_element("X", "class")]),
            image_format="svg",
        )
        assert result.image_format == "svg"
        assert result.rendered_image == b"<svg>fake</svg>"


# ---------------------------------------------------------------------------
# generate_uml_class_diagram – render error
# ---------------------------------------------------------------------------


class TestUMLClassDiagramRenderError:
    @patch("app.diagram_generator._render_plantuml", side_effect=RenderError("PlantUML CLI not found"))
    def test_render_error_propagated(self, mock_render):
        model = _uml_model([_class_element("A", "class")])
        with pytest.raises(RenderError, match="PlantUML CLI not found"):
            generate_uml_class_diagram(model)


# ---------------------------------------------------------------------------
# generate_uml_sequence_diagram – structured data
# ---------------------------------------------------------------------------


class TestUMLSequenceDiagramStructure:
    @patch("app.diagram_generator._render_plantuml", return_value=b"fake-png")
    def test_participants_from_calls(self, mock_render):
        model = _uml_model(
            [_class_element("A", "service"), _class_element("B", "service")],
            [Relationship(source="A", target="B", relationship_type="calls")],
        )
        result = generate_uml_sequence_diagram(model)

        assert result.diagram_type == "uml_sequence"
        participants = result.structured_data["participants"]
        assert len(participants) == 2
        names = [p["name"] for p in participants]
        assert "A" in names
        assert "B" in names

    @patch("app.diagram_generator._render_plantuml", return_value=b"fake-png")
    def test_messages_from_calls(self, mock_render):
        model = _uml_model(
            [_class_element("A", "service"), _class_element("B", "service")],
            [
                Relationship(source="A", target="B", relationship_type="calls"),
                Relationship(source="B", target="A", relationship_type="calls"),
            ],
        )
        result = generate_uml_sequence_diagram(model)

        messages = result.structured_data["messages"]
        assert len(messages) == 2
        assert messages[0]["from"] == "A"
        assert messages[0]["to"] == "B"
        assert messages[1]["from"] == "B"
        assert messages[1]["to"] == "A"

    @patch("app.diagram_generator._render_plantuml", return_value=b"fake-png")
    def test_non_calls_excluded(self, mock_render):
        model = _uml_model(
            [_class_element("A", "class"), _class_element("B", "class")],
            [
                Relationship(source="A", target="B", relationship_type="calls"),
                Relationship(source="A", target="B", relationship_type="depends_on"),
            ],
        )
        result = generate_uml_sequence_diagram(model)

        messages = result.structured_data["messages"]
        assert len(messages) == 1
        assert messages[0]["label"] == "calls"

    @patch("app.diagram_generator._render_plantuml", return_value=b"fake-png")
    def test_empty_model_no_calls(self, mock_render):
        model = ReconciledModel()
        result = generate_uml_sequence_diagram(model)

        assert result.structured_data["participants"] == []
        assert result.structured_data["messages"] == []

    @patch("app.diagram_generator._render_plantuml", return_value=b"fake-png")
    def test_participant_order_preserved(self, mock_render):
        """Participants appear in order of first occurrence."""
        model = _uml_model(
            [],
            [
                Relationship(source="C", target="A", relationship_type="calls"),
                Relationship(source="A", target="B", relationship_type="calls"),
            ],
        )
        result = generate_uml_sequence_diagram(model)

        names = [p["name"] for p in result.structured_data["participants"]]
        assert names == ["C", "A", "B"]


# ---------------------------------------------------------------------------
# generate_uml_sequence_diagram – PlantUML source
# ---------------------------------------------------------------------------


class TestUMLSequenceDiagramSource:
    @patch("app.diagram_generator._render_plantuml", return_value=b"fake-png")
    def test_source_contains_startuml_enduml(self, mock_render):
        model = _uml_model(
            [],
            [Relationship(source="A", target="B", relationship_type="calls")],
        )
        result = generate_uml_sequence_diagram(model)

        assert result.source_file is not None
        assert result.source_file.startswith("@startuml")
        assert result.source_file.endswith("@enduml")

    @patch("app.diagram_generator._render_plantuml", return_value=b"fake-png")
    def test_source_contains_participants(self, mock_render):
        model = _uml_model(
            [],
            [Relationship(source="OrderSvc", target="PaymentSvc", relationship_type="calls")],
        )
        result = generate_uml_sequence_diagram(model)

        assert 'participant "OrderSvc" as OrderSvc' in result.source_file
        assert 'participant "PaymentSvc" as PaymentSvc' in result.source_file

    @patch("app.diagram_generator._render_plantuml", return_value=b"fake-png")
    def test_source_contains_messages(self, mock_render):
        model = _uml_model(
            [],
            [Relationship(source="A", target="B", relationship_type="calls")],
        )
        result = generate_uml_sequence_diagram(model)

        assert "A -> B : calls" in result.source_file


# ---------------------------------------------------------------------------
# generate_uml_sequence_diagram – output format
# ---------------------------------------------------------------------------


class TestUMLSequenceDiagramOutput:
    @patch("app.diagram_generator._render_plantuml", return_value=b"fake-png")
    def test_default_png_format(self, mock_render):
        model = _uml_model(
            [],
            [Relationship(source="A", target="B", relationship_type="calls")],
        )
        result = generate_uml_sequence_diagram(model)
        assert result.image_format == "png"

    @patch("app.diagram_generator._render_plantuml", return_value=b"<svg>fake</svg>")
    def test_svg_format(self, mock_render):
        model = _uml_model(
            [],
            [Relationship(source="A", target="B", relationship_type="calls")],
        )
        result = generate_uml_sequence_diagram(model, image_format="svg")
        assert result.image_format == "svg"
        assert result.rendered_image == b"<svg>fake</svg>"


# ---------------------------------------------------------------------------
# generate_uml_sequence_diagram – render error
# ---------------------------------------------------------------------------


class TestUMLSequenceDiagramRenderError:
    @patch("app.diagram_generator._render_plantuml", side_effect=RenderError("PlantUML CLI not found"))
    def test_render_error_propagated(self, mock_render):
        model = _uml_model(
            [],
            [Relationship(source="A", target="B", relationship_type="calls")],
        )
        with pytest.raises(RenderError, match="PlantUML CLI not found"):
            generate_uml_sequence_diagram(model)


# ---------------------------------------------------------------------------
# Imports for LLD tests
# ---------------------------------------------------------------------------

from app.diagram_generator import generate_lld
from app.models import ComponentModel


# ---------------------------------------------------------------------------
# Helpers for LLD tests
# ---------------------------------------------------------------------------


def _lld_component(
    name: str = "OrderProcessor",
    classes: list[str] | None = None,
    functions: list[str] | None = None,
    data_transformations: list[str] | None = None,
    data_flows: list[tuple[str, str]] | None = None,
) -> ComponentModel:
    return ComponentModel(
        name=name,
        classes=classes or [],
        functions=functions or [],
        data_transformations=data_transformations or [],
        data_flows=data_flows or [],
    )


# ---------------------------------------------------------------------------
# generate_lld – structured data
# ---------------------------------------------------------------------------


class TestLLDStructure:
    @patch("app.diagram_generator.graphviz.Digraph")
    def test_nodes_from_classes_functions_transforms(self, mock_digraph_cls):
        mock_graph = MagicMock()
        mock_graph.pipe.return_value = b"fake-png"
        mock_graph.source = "digraph {}"
        mock_digraph_cls.return_value = mock_graph

        comp = _lld_component(
            classes=["OrderEntity"],
            functions=["validate_order"],
            data_transformations=["normalize_prices"],
        )
        result = generate_lld(comp)

        assert result.diagram_type == "lld"
        nodes = result.structured_data["nodes"]
        assert len(nodes) == 3
        ids = {n["id"] for n in nodes}
        assert ids == {"OrderEntity", "validate_order", "normalize_prices"}

    @patch("app.diagram_generator.graphviz.Digraph")
    def test_node_types_correct(self, mock_digraph_cls):
        mock_graph = MagicMock()
        mock_graph.pipe.return_value = b"fake-png"
        mock_graph.source = "digraph {}"
        mock_digraph_cls.return_value = mock_graph

        comp = _lld_component(
            classes=["Cls"],
            functions=["fn"],
            data_transformations=["dt"],
        )
        result = generate_lld(comp)

        type_map = {n["id"]: n["type"] for n in result.structured_data["nodes"]}
        assert type_map["Cls"] == "class"
        assert type_map["fn"] == "function"
        assert type_map["dt"] == "data_transformation"

    @patch("app.diagram_generator.graphviz.Digraph")
    def test_edges_from_data_flows(self, mock_digraph_cls):
        mock_graph = MagicMock()
        mock_graph.pipe.return_value = b"fake-png"
        mock_graph.source = "digraph {}"
        mock_digraph_cls.return_value = mock_graph

        comp = _lld_component(
            functions=["parse", "transform", "emit"],
            data_flows=[("parse", "transform"), ("transform", "emit")],
        )
        result = generate_lld(comp)

        edges = result.structured_data["edges"]
        assert len(edges) == 2
        assert edges[0] == {"source": "parse", "target": "transform"}
        assert edges[1] == {"source": "transform", "target": "emit"}

    @patch("app.diagram_generator.graphviz.Digraph")
    def test_component_name_in_structured_data(self, mock_digraph_cls):
        mock_graph = MagicMock()
        mock_graph.pipe.return_value = b"fake-png"
        mock_graph.source = "digraph {}"
        mock_digraph_cls.return_value = mock_graph

        comp = _lld_component(name="PaymentGateway")
        result = generate_lld(comp)

        assert result.structured_data["component_name"] == "PaymentGateway"

    @patch("app.diagram_generator.graphviz.Digraph")
    def test_empty_component(self, mock_digraph_cls):
        mock_graph = MagicMock()
        mock_graph.pipe.return_value = b"fake-png"
        mock_graph.source = "digraph {}"
        mock_digraph_cls.return_value = mock_graph

        comp = _lld_component()
        result = generate_lld(comp)

        assert result.structured_data["nodes"] == []
        assert result.structured_data["edges"] == []


# ---------------------------------------------------------------------------
# generate_lld – output format
# ---------------------------------------------------------------------------


class TestLLDOutput:
    @patch("app.diagram_generator.graphviz.Digraph")
    def test_default_png_format(self, mock_digraph_cls):
        mock_graph = MagicMock()
        mock_graph.pipe.return_value = b"fake-png"
        mock_graph.source = "digraph {}"
        mock_digraph_cls.return_value = mock_graph

        result = generate_lld(_lld_component(functions=["f"]))
        assert result.image_format == "png"
        assert result.rendered_image == b"fake-png"

    @patch("app.diagram_generator.graphviz.Digraph")
    def test_svg_format(self, mock_digraph_cls):
        mock_graph = MagicMock()
        mock_graph.pipe.return_value = b"<svg>fake</svg>"
        mock_graph.source = "digraph {}"
        mock_digraph_cls.return_value = mock_graph

        result = generate_lld(_lld_component(functions=["f"]), image_format="svg")
        assert result.image_format == "svg"
        assert result.rendered_image == b"<svg>fake</svg>"

    @patch("app.diagram_generator.graphviz.Digraph")
    def test_source_file_populated(self, mock_digraph_cls):
        mock_graph = MagicMock()
        mock_graph.pipe.return_value = b"fake"
        mock_graph.source = "digraph { lld }"
        mock_digraph_cls.return_value = mock_graph

        result = generate_lld(_lld_component(classes=["A"]))
        assert result.source_file == "digraph { lld }"


# ---------------------------------------------------------------------------
# generate_lld – render error
# ---------------------------------------------------------------------------


class TestLLDRenderError:
    @patch("app.diagram_generator.graphviz.Digraph")
    def test_render_error_raised(self, mock_digraph_cls):
        mock_graph = MagicMock()
        mock_graph.pipe.side_effect = RuntimeError("dot not found")
        mock_graph.source = "digraph {}"
        mock_digraph_cls.return_value = mock_graph

        with pytest.raises(RenderError, match="Graphviz rendering failed"):
            generate_lld(_lld_component(classes=["A"]))
