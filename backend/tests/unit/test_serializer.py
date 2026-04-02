"""Unit tests for the Serializer component.

Tests serialize(), deserialize(), and validate() covering:
- Round-trip for models without bytes fields
- Round-trip for models with bytes fields (base64 encoding)
- JSON Schema validation (valid and invalid data)
- Error handling for missing/invalid schemas
"""

from __future__ import annotations

import json

import pytest

from app.errors import SchemaValidationError
from app.models import (
    ADR,
    AnalysisResult,
    ClassifiedElement,
    CodebaseModel,
    DiagramOutput,
    DocumentModel,
    Element,
    LeanIXMapping,
    LeanIXReport,
    ModuleBoundary,
    Relationship,
    ReconciledModel,
    SourceFile,
    StructuredOutput,
    ValidationResult,
)
from app.serializer import deserialize, serialize, validate


# ---------------------------------------------------------------------------
# serialize / deserialize round-trip — models WITHOUT bytes
# ---------------------------------------------------------------------------


class TestSerializeDeserializeNonBytes:
    def test_structured_output_round_trip(self):
        original = StructuredOutput(output_type="analysis", data={"key": "value", "count": 42})
        json_str = serialize(original)
        restored = deserialize(json_str, StructuredOutput)
        assert restored == original

    def test_codebase_model_round_trip(self):
        original = CodebaseModel(
            root_path="/repo",
            files=[SourceFile(path="main.py", language="python", imports=["os"], exports=["main"], public_interfaces=["run"])],
            module_boundaries=[ModuleBoundary(name="core", files=["main.py"], dependencies=["utils"])],
        )
        json_str = serialize(original)
        restored = deserialize(json_str, CodebaseModel)
        assert restored == original

    def test_analysis_result_round_trip(self):
        original = AnalysisResult(
            elements=[Element(name="Svc", element_type="service", metadata={"port": 8080})],
            relationships=[Relationship(source="A", target="B", relationship_type="depends_on")],
            patterns=["microservices"],
            layers=["presentation", "data"],
        )
        json_str = serialize(original)
        restored = deserialize(json_str, AnalysisResult)
        assert restored == original

    def test_reconciled_model_round_trip(self):
        elem = Element(name="Auth", element_type="service", metadata={})
        ce = ClassifiedElement(element=elem, leanix_type="IT Component", confidence=0.85, alternative_types=[], evidence=["code"])
        original = ReconciledModel(
            elements=[ce],
            relationships=[Relationship(source="A", target="B", relationship_type="calls")],
            patterns=["layered"],
            layers=["api"],
            discrepancies=["doc says monolith, code is microservices"],
        )
        json_str = serialize(original)
        restored = deserialize(json_str, ReconciledModel)
        assert restored == original

    def test_leanix_report_round_trip(self):
        original = LeanIXReport(
            mappings=[
                LeanIXMapping(
                    element_name="AuthService",
                    leanix_types=[{"type": "IT Component", "confidence": 0.95}],
                    evidence=["provides REST API"],
                    relationships=[{"target": "UserDB", "relationship": "uses"}],
                )
            ]
        )
        json_str = serialize(original)
        restored = deserialize(json_str, LeanIXReport)
        assert restored == original

    def test_adr_round_trip(self):
        original = ADR(
            title="Use FastAPI",
            status="Accepted",
            context="Need async web framework",
            decision="FastAPI chosen",
            consequences="Good async support, smaller community than Django",
        )
        json_str = serialize(original)
        restored = deserialize(json_str, ADR)
        assert restored == original

    def test_validation_result_round_trip(self):
        original = ValidationResult(valid=False, errors=["missing field 'name'"])
        json_str = serialize(original)
        restored = deserialize(json_str, ValidationResult)
        assert restored == original

    def test_empty_structured_output(self):
        original = StructuredOutput(output_type="empty")
        json_str = serialize(original)
        restored = deserialize(json_str, StructuredOutput)
        assert restored == original
        assert restored.data == {}


# ---------------------------------------------------------------------------
# serialize / deserialize round-trip — models WITH bytes fields
# ---------------------------------------------------------------------------


class TestSerializeDeserializeBytes:
    def test_diagram_output_round_trip(self):
        original = DiagramOutput(
            diagram_type="dependency_graph",
            rendered_image=b"\x89PNG\r\n\x1a\nfake",
            image_format="png",
            structured_data={"nodes": ["A", "B"], "edges": [{"from": "A", "to": "B"}]},
            source_file=None,
        )
        json_str = serialize(original)
        # Verify the JSON is valid and contains base64 marker
        parsed = json.loads(json_str)
        assert "__b64__" in parsed["rendered_image"]
        # Round-trip
        restored = deserialize(json_str, DiagramOutput)
        assert restored == original

    def test_document_model_round_trip(self):
        original = DocumentModel(
            source_path="/docs/arch.pdf",
            file_type="pdf",
            text_content=["Introduction", "Architecture overview"],
            images=[b"\x89PNG\r\nimage1", b"\xff\xd8\xffjpeg"],
        )
        json_str = serialize(original)
        restored = deserialize(json_str, DocumentModel)
        assert restored == original

    def test_diagram_output_with_source_file(self):
        original = DiagramOutput(
            diagram_type="uml_class",
            rendered_image=b"svg-content",
            image_format="svg",
            structured_data={},
            source_file="@startuml\nclass Foo\n@enduml",
        )
        json_str = serialize(original)
        restored = deserialize(json_str, DiagramOutput)
        assert restored == original

    def test_document_model_empty_images(self):
        original = DocumentModel(
            source_path="/doc.docx",
            file_type="docx",
            text_content=["Hello"],
            images=[],
        )
        json_str = serialize(original)
        restored = deserialize(json_str, DocumentModel)
        assert restored == original


# ---------------------------------------------------------------------------
# validate() — JSON Schema validation
# ---------------------------------------------------------------------------


class TestValidate:
    def test_valid_structured_output(self):
        data = StructuredOutput(output_type="analysis", data={"key": "value"})
        json_str = serialize(data)
        result = validate(json_str, "structured_output.json")
        assert result.valid is True
        assert result.errors == []

    def test_valid_codebase_model(self):
        data = CodebaseModel(
            root_path="/repo",
            files=[SourceFile(path="a.py", language="python", imports=[], exports=[], public_interfaces=[])],
            module_boundaries=[],
        )
        json_str = serialize(data)
        result = validate(json_str, "codebase_model.json")
        assert result.valid is True

    def test_valid_adr(self):
        data = ADR(title="T", status="Proposed", context="C", decision="D", consequences="X")
        json_str = serialize(data)
        result = validate(json_str, "adr.json")
        assert result.valid is True

    def test_invalid_missing_required_field(self):
        # StructuredOutput schema requires "output_type" and "data"
        json_str = json.dumps({"output_type": "test"})
        result = validate(json_str, "structured_output.json")
        assert result.valid is False
        assert any("data" in e for e in result.errors)

    def test_invalid_extra_field(self):
        # structured_output.json has additionalProperties: false
        json_str = json.dumps({"output_type": "test", "data": {}, "extra": "nope"})
        result = validate(json_str, "structured_output.json")
        assert result.valid is False

    def test_invalid_wrong_type(self):
        # output_type should be string, not int
        json_str = json.dumps({"output_type": 123, "data": {}})
        result = validate(json_str, "structured_output.json")
        assert result.valid is False

    def test_missing_schema_file_raises(self):
        with pytest.raises(SchemaValidationError, match="Failed to load schema"):
            validate("{}", "nonexistent_schema.json")

    def test_valid_validation_result(self):
        data = ValidationResult(valid=True, errors=[])
        json_str = serialize(data)
        result = validate(json_str, "validation_result.json")
        assert result.valid is True

    def test_valid_analysis_result(self):
        data = AnalysisResult(
            elements=[Element(name="Svc", element_type="service", metadata={})],
            relationships=[],
            patterns=[],
            layers=[],
        )
        json_str = serialize(data)
        result = validate(json_str, "analysis_result.json")
        assert result.valid is True
