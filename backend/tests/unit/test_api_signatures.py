"""Smoke tests verifying all public API signatures remain unchanged after refactoring.

Uses inspect.signature to check parameter names and return annotations
for every public function/method specified in Requirement 9.

Because the source modules use ``from __future__ import annotations``,
annotations are stored as strings. We compare against string representations.

Requirements: 9.1, 9.2, 9.3, 9.4, 9.5, 9.6, 9.7
"""

from __future__ import annotations

import inspect

import pytest

from app import code_ingester, document_ingester, diagram_generator, document_generator, serializer
from app.ai_engine import AIEngine
from app.api import app


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def _param_names(sig: inspect.Signature) -> list[str]:
    """Return parameter names from a signature (excluding 'self')."""
    return [name for name in sig.parameters if name != "self"]


def _ann(sig: inspect.Signature, param: str) -> str:
    """Return the string representation of a parameter's annotation."""
    a = sig.parameters[param].annotation
    return str(a) if a is not inspect.Parameter.empty else ""


def _ret(sig: inspect.Signature) -> str:
    """Return the string representation of the return annotation."""
    a = sig.return_annotation
    return str(a) if a is not inspect.Signature.empty else ""


# ---------------------------------------------------------------------------
# Requirement 9.1 – code_ingester.ingest
# ---------------------------------------------------------------------------

class TestCodeIngesterSignature:
    def test_params(self) -> None:
        sig = inspect.signature(code_ingester.ingest)
        assert _param_names(sig) == ["source"]

    def test_annotations(self) -> None:
        sig = inspect.signature(code_ingester.ingest)
        assert _ann(sig, "source") == "SourceInput"
        assert _ret(sig) == "CodebaseModel"


# ---------------------------------------------------------------------------
# Requirement 9.2 – document_ingester.ingest
# ---------------------------------------------------------------------------

class TestDocumentIngesterSignature:
    def test_params(self) -> None:
        sig = inspect.signature(document_ingester.ingest)
        assert _param_names(sig) == ["document"]

    def test_annotations(self) -> None:
        sig = inspect.signature(document_ingester.ingest)
        assert _ann(sig, "document") == "DocumentInput"
        assert _ret(sig) == "DocumentModel"


# ---------------------------------------------------------------------------
# Requirement 9.3 – diagram_generator (all five functions)
# ---------------------------------------------------------------------------

class TestDiagramGeneratorSignatures:
    @pytest.mark.parametrize(
        "fn_name, first_param, first_ann",
        [
            ("generate_dependency_graph", "analysis", "ReconciledModel"),
            ("generate_component_diagram", "analysis", "ReconciledModel"),
            ("generate_uml_class_diagram", "analysis", "ReconciledModel"),
            ("generate_uml_sequence_diagram", "analysis", "ReconciledModel"),
            ("generate_lld", "component", "ComponentModel"),
        ],
    )
    def test_params_and_first_annotation(self, fn_name: str, first_param: str, first_ann: str) -> None:
        fn = getattr(diagram_generator, fn_name)
        sig = inspect.signature(fn)
        names = _param_names(sig)
        assert names == [first_param, "image_format"]
        assert _ann(sig, first_param) == first_ann

    @pytest.mark.parametrize(
        "fn_name",
        [
            "generate_dependency_graph",
            "generate_component_diagram",
            "generate_uml_class_diagram",
            "generate_uml_sequence_diagram",
            "generate_lld",
        ],
    )
    def test_return_type(self, fn_name: str) -> None:
        fn = getattr(diagram_generator, fn_name)
        sig = inspect.signature(fn)
        assert _ret(sig) == "DiagramOutput"

    @pytest.mark.parametrize(
        "fn_name",
        [
            "generate_dependency_graph",
            "generate_component_diagram",
            "generate_uml_class_diagram",
            "generate_uml_sequence_diagram",
            "generate_lld",
        ],
    )
    def test_image_format_default(self, fn_name: str) -> None:
        fn = getattr(diagram_generator, fn_name)
        sig = inspect.signature(fn)
        assert sig.parameters["image_format"].default == "png"


# ---------------------------------------------------------------------------
# Requirement 9.4 – document_generator
# ---------------------------------------------------------------------------

class TestDocumentGeneratorSignatures:
    def test_generate_adrs_params(self) -> None:
        sig = inspect.signature(document_generator.generate_adrs)
        assert _param_names(sig) == ["analysis", "existing_adrs"]
        assert _ann(sig, "analysis") == "ReconciledModel"
        assert sig.parameters["existing_adrs"].default is None

    def test_generate_adrs_return(self) -> None:
        sig = inspect.signature(document_generator.generate_adrs)
        ret = _ret(sig)
        assert "list" in ret and "ADR" in ret

    def test_adr_to_markdown_params(self) -> None:
        sig = inspect.signature(document_generator.adr_to_markdown)
        assert _param_names(sig) == ["adr"]
        assert _ann(sig, "adr") == "ADR"
        assert _ret(sig) == "str"

    def test_generate_markdown_params(self) -> None:
        sig = inspect.signature(document_generator.generate_markdown)
        assert _param_names(sig) == ["analysis", "diagrams"]
        assert _ann(sig, "analysis") == "ReconciledModel"
        assert sig.parameters["diagrams"].default is None
        assert _ret(sig) == "str"


# ---------------------------------------------------------------------------
# Requirement 9.5 – serializer
# ---------------------------------------------------------------------------

class TestSerializerSignatures:
    def test_serialize(self) -> None:
        sig = inspect.signature(serializer.serialize)
        assert _param_names(sig) == ["data"]
        assert _ann(sig, "data") == "BaseModel"
        assert _ret(sig) == "str"

    def test_deserialize(self) -> None:
        sig = inspect.signature(serializer.deserialize)
        assert _param_names(sig) == ["json_str", "schema"]
        assert _ann(sig, "json_str") == "str"
        assert _ann(sig, "schema") == "type[T]"

    def test_validate(self) -> None:
        sig = inspect.signature(serializer.validate)
        assert _param_names(sig) == ["json_str", "schema_path"]
        assert _ann(sig, "json_str") == "str"
        assert _ann(sig, "schema_path") == "str"
        assert _ret(sig) == "ValidationResult"


# ---------------------------------------------------------------------------
# Requirement 9.7 – AIEngine methods
# ---------------------------------------------------------------------------

class TestAIEngineSignatures:
    def test_analyze_code(self) -> None:
        sig = inspect.signature(AIEngine.analyze_code)
        assert _param_names(sig) == ["codebase"]
        assert _ann(sig, "codebase") == "CodebaseModel"
        assert _ret(sig) == "AnalysisResult"

    def test_analyze_document(self) -> None:
        sig = inspect.signature(AIEngine.analyze_document)
        assert _param_names(sig) == ["document"]
        assert _ann(sig, "document") == "DocumentModel"
        assert _ret(sig) == "AnalysisResult"

    def test_reconcile(self) -> None:
        sig = inspect.signature(AIEngine.reconcile)
        assert _param_names(sig) == ["code_analysis", "doc_analysis"]
        assert _ann(sig, "code_analysis") == "AnalysisResult"
        assert _ann(sig, "doc_analysis") == "AnalysisResult"
        assert _ret(sig) == "ReconciledModel"

    def test_classify_elements(self) -> None:
        sig = inspect.signature(AIEngine.classify_elements)
        assert _param_names(sig) == ["elements"]
        ret = _ret(sig)
        assert "list" in ret and "ClassifiedElement" in ret


# ---------------------------------------------------------------------------
# Requirement 9.6 – FastAPI endpoint routes and methods
# ---------------------------------------------------------------------------

class TestAPIEndpoints:
    """Verify API endpoint routes and HTTP methods are unchanged."""

    @staticmethod
    def _get_routes() -> dict[str, list[str]]:
        routes: dict[str, list[str]] = {}
        for route in app.routes:
            if hasattr(route, "methods") and hasattr(route, "path"):
                routes[route.path] = sorted(route.methods)
        return routes

    def test_analyze_endpoint(self) -> None:
        routes = self._get_routes()
        assert "/analyze" in routes
        assert "POST" in routes["/analyze"]

    def test_status_endpoint(self) -> None:
        routes = self._get_routes()
        assert "/status/{job_id}" in routes
        assert "GET" in routes["/status/{job_id}"]

    def test_results_endpoint(self) -> None:
        routes = self._get_routes()
        assert "/results/{job_id}" in routes
        assert "GET" in routes["/results/{job_id}"]

    def test_download_endpoint(self) -> None:
        routes = self._get_routes()
        assert "/download/{job_id}/{artifact}" in routes
        assert "GET" in routes["/download/{job_id}/{artifact}"]
