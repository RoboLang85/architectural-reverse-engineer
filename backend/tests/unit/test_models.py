"""Unit tests for Pydantic data models."""

import json
from pathlib import Path

import jsonschema
import pytest
from pydantic import ValidationError

from app.models import (
    ADR,
    AnalysisResult,
    ClassifiedElement,
    CodebaseModel,
    DiagramOutput,
    DocumentInput,
    DocumentModel,
    Element,
    LeanIXMapping,
    LeanIXReport,
    ModuleBoundary,
    PdfContent,
    Relationship,
    ReconciledModel,
    SourceFile,
    SourceInput,
    StructuredOutput,
    ValidationResult,
)

SCHEMAS_DIR = Path(__file__).resolve().parent.parent.parent / "schemas"


# --- SourceInput ---


class TestSourceInput:
    def test_local_path(self):
        si = SourceInput(input_type="local_path", value="/tmp/repo")
        assert si.input_type == "local_path"
        assert si.value == "/tmp/repo"

    def test_github_url(self):
        si = SourceInput(input_type="github_url", value="https://github.com/org/repo")
        assert si.input_type == "github_url"

    def test_invalid_input_type(self):
        with pytest.raises(ValidationError):
            SourceInput(input_type="ftp", value="ftp://example.com")


# --- DocumentInput ---


class TestDocumentInput:
    def test_pdf(self):
        di = DocumentInput(file_path="/tmp/doc.pdf", file_type="pdf")
        assert di.file_type == "pdf"

    def test_all_supported_types(self):
        for ft in ("pdf", "docx", "png", "jpg", "svg"):
            di = DocumentInput(file_path=f"/tmp/file.{ft}", file_type=ft)
            assert di.file_type == ft

    def test_unsupported_type(self):
        with pytest.raises(ValidationError):
            DocumentInput(file_path="/tmp/file.txt", file_type="txt")


# --- SourceFile ---


class TestSourceFile:
    def test_defaults(self):
        sf = SourceFile(path="main.py", language="python")
        assert sf.imports == []
        assert sf.exports == []
        assert sf.public_interfaces == []

    def test_with_data(self):
        sf = SourceFile(
            path="main.py",
            language="python",
            imports=["os", "sys"],
            exports=["main"],
            public_interfaces=["run"],
        )
        assert len(sf.imports) == 2


# --- ModuleBoundary ---


class TestModuleBoundary:
    def test_defaults(self):
        mb = ModuleBoundary(name="core")
        assert mb.files == []
        assert mb.dependencies == []

    def test_with_data(self):
        mb = ModuleBoundary(name="core", files=["a.py"], dependencies=["utils"])
        assert mb.name == "core"
        assert mb.dependencies == ["utils"]


# --- CodebaseModel ---


class TestCodebaseModel:
    def test_defaults(self):
        cm = CodebaseModel(root_path="/repo")
        assert cm.files == []
        assert cm.module_boundaries == []

    def test_with_nested(self):
        cm = CodebaseModel(
            root_path="/repo",
            files=[SourceFile(path="a.py", language="python")],
            module_boundaries=[ModuleBoundary(name="core")],
        )
        assert len(cm.files) == 1
        assert len(cm.module_boundaries) == 1


# --- PdfContent ---


class TestPdfContent:
    def test_defaults(self):
        pc = PdfContent()
        assert pc.text_blocks == []
        assert pc.images == []

    def test_with_data(self):
        pc = PdfContent(text_blocks=["hello"], images=[b"\x89PNG"])
        assert pc.text_blocks == ["hello"]
        assert len(pc.images) == 1


# --- DocumentModel ---


class TestDocumentModel:
    def test_defaults(self):
        dm = DocumentModel(source_path="/doc.pdf", file_type="pdf")
        assert dm.text_content == []
        assert dm.images == []


# --- Element ---


class TestElement:
    def test_defaults(self):
        e = Element(name="AuthService", element_type="service")
        assert e.metadata == {}

    def test_with_metadata(self):
        e = Element(name="AuthService", element_type="service", metadata={"port": 8080})
        assert e.metadata["port"] == 8080


# --- Relationship ---


class TestRelationship:
    def test_basic(self):
        r = Relationship(source="A", target="B", relationship_type="depends_on")
        assert r.source == "A"
        assert r.target == "B"


# --- AnalysisResult ---


class TestAnalysisResult:
    def test_defaults(self):
        ar = AnalysisResult()
        assert ar.elements == []
        assert ar.relationships == []
        assert ar.patterns == []
        assert ar.layers == []


# --- ClassifiedElement ---


class TestClassifiedElement:
    def test_valid(self):
        elem = Element(name="Svc", element_type="service")
        ce = ClassifiedElement(element=elem, leanix_type="IT Component", confidence=0.9)
        assert ce.confidence == 0.9

    def test_confidence_bounds(self):
        elem = Element(name="Svc", element_type="service")
        with pytest.raises(ValidationError):
            ClassifiedElement(element=elem, leanix_type="IT Component", confidence=1.5)
        with pytest.raises(ValidationError):
            ClassifiedElement(element=elem, leanix_type="IT Component", confidence=-0.1)


# --- ReconciledModel ---


class TestReconciledModel:
    def test_defaults(self):
        rm = ReconciledModel()
        assert rm.discrepancies == []


# --- LeanIXMapping ---


class TestLeanIXMapping:
    def test_defaults(self):
        lm = LeanIXMapping(element_name="AuthService")
        assert lm.leanix_types == []
        assert lm.evidence == []
        assert lm.relationships == []


# --- LeanIXReport ---


class TestLeanIXReport:
    def test_defaults(self):
        lr = LeanIXReport()
        assert lr.mappings == []


# --- DiagramOutput ---


class TestDiagramOutput:
    def test_valid(self):
        do = DiagramOutput(
            diagram_type="dependency_graph",
            rendered_image=b"\x89PNG",
            image_format="png",
        )
        assert do.source_file is None
        assert do.structured_data == {}

    def test_invalid_format(self):
        with pytest.raises(ValidationError):
            DiagramOutput(
                diagram_type="dependency_graph",
                rendered_image=b"\x89PNG",
                image_format="gif",
            )


# --- ADR ---


class TestADR:
    def test_valid(self):
        adr = ADR(
            title="Use FastAPI",
            status="Accepted",
            context="Need a web framework",
            decision="Use FastAPI",
            consequences="Async support",
        )
        assert adr.title == "Use FastAPI"


# --- StructuredOutput ---


class TestStructuredOutput:
    def test_defaults(self):
        so = StructuredOutput(output_type="analysis")
        assert so.data == {}


# --- ValidationResult ---


class TestValidationResult:
    def test_valid(self):
        vr = ValidationResult(valid=True)
        assert vr.errors == []

    def test_invalid(self):
        vr = ValidationResult(valid=False, errors=["missing field"])
        assert len(vr.errors) == 1


# --- JSON Schema validation tests ---


class TestJsonSchemas:
    """Verify JSON schemas validate data produced by models."""

    def _load_schema(self, name: str) -> dict:
        schema_path = SCHEMAS_DIR / f"{name}.json"
        return json.loads(schema_path.read_text())

    def _validate(self, data: dict, schema_name: str):
        schema = self._load_schema(schema_name)
        jsonschema.validate(instance=data, schema=schema)

    def test_codebase_model_schema(self):
        cm = CodebaseModel(
            root_path="/repo",
            files=[SourceFile(path="a.py", language="python", imports=["os"], exports=["main"], public_interfaces=["run"])],
            module_boundaries=[ModuleBoundary(name="core", files=["a.py"], dependencies=["utils"])],
        )
        self._validate(cm.model_dump(), "codebase_model")

    def test_document_model_schema(self):
        dm = DocumentModel(source_path="/doc.pdf", file_type="pdf", text_content=["hello"], images=[b"img"])
        data = dm.model_dump()
        # images are bytes in model but base64 strings in schema — convert for validation
        import base64
        data["images"] = [base64.b64encode(img).decode() for img in data["images"]]
        self._validate(data, "document_model")

    def test_analysis_result_schema(self):
        ar = AnalysisResult(
            elements=[Element(name="Svc", element_type="service", metadata={"k": "v"})],
            relationships=[Relationship(source="A", target="B", relationship_type="depends_on")],
            patterns=["microservices"],
            layers=["presentation"],
        )
        self._validate(ar.model_dump(), "analysis_result")

    def test_reconciled_model_schema(self):
        elem = Element(name="Svc", element_type="service", metadata={})
        ce = ClassifiedElement(element=elem, leanix_type="IT Component", confidence=0.9, alternative_types=[], evidence=["code"])
        rm = ReconciledModel(
            elements=[ce],
            relationships=[Relationship(source="A", target="B", relationship_type="calls")],
            patterns=["layered"],
            layers=["data"],
            discrepancies=["mismatch"],
        )
        self._validate(rm.model_dump(), "reconciled_model")

    def test_leanix_report_schema(self):
        lr = LeanIXReport(
            mappings=[
                LeanIXMapping(
                    element_name="AuthService",
                    leanix_types=[{"type": "IT Component", "confidence": 0.95}],
                    evidence=["provides REST API"],
                    relationships=[{"target": "UserDB", "relationship": "uses"}],
                )
            ]
        )
        self._validate(lr.model_dump(), "leanix_report")

    def test_diagram_output_schema(self):
        do = DiagramOutput(
            diagram_type="dependency_graph",
            rendered_image=b"\x89PNG",
            image_format="png",
            structured_data={"nodes": [], "edges": []},
            source_file=None,
        )
        data = do.model_dump()
        import base64
        data["rendered_image"] = base64.b64encode(data["rendered_image"]).decode()
        self._validate(data, "diagram_output")

    def test_adr_schema(self):
        adr = ADR(
            title="Use FastAPI",
            status="Accepted",
            context="Need framework",
            decision="FastAPI chosen",
            consequences="Async support",
        )
        self._validate(adr.model_dump(), "adr")

    def test_structured_output_schema(self):
        so = StructuredOutput(output_type="analysis", data={"key": "value"})
        self._validate(so.model_dump(), "structured_output")

    def test_validation_result_schema(self):
        vr = ValidationResult(valid=False, errors=["missing field"])
        self._validate(vr.model_dump(), "validation_result")
