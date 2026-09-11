"""Property-based tests for JSON serialization round-trip.

# Feature: architectural-reverse-engineer, Property 19: JSON serialization round-trip

Validates: Requirements 12.1, 12.2, 12.3

For any valid structured output (dependency graph, component map, LeanIX mapping,
or any StructuredOutput), serializing to JSON and then deserializing back should
produce a data structure equivalent to the original.
"""

from __future__ import annotations

import base64
import json
from typing import Any

from hypothesis import given, settings
from hypothesis import strategies as st

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
    PdfContent,
    Relationship,
    ReconciledModel,
    SourceFile,
    StructuredOutput,
    ValidationResult,
)


def _encode_bytes(obj: Any) -> Any:
    """Recursively base64-encode bytes values in a nested structure."""
    if isinstance(obj, bytes):
        return {"__b64__": base64.b64encode(obj).decode("ascii")}
    if isinstance(obj, dict):
        return {k: _encode_bytes(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_encode_bytes(v) for v in obj]
    return obj


def _decode_bytes(obj: Any) -> Any:
    """Recursively base64-decode tagged values back to bytes."""
    if isinstance(obj, dict) and "__b64__" in obj and len(obj) == 1:
        return base64.b64decode(obj["__b64__"])
    if isinstance(obj, dict):
        return {k: _decode_bytes(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_decode_bytes(v) for v in obj]
    return obj


def _round_trip_via_dict(model_cls: type, instance: Any) -> Any:
    """Round-trip a Pydantic model through JSON using dict serialization.

    Uses model_dump() -> encode bytes as base64 -> json.dumps -> json.loads
    -> decode base64 back to bytes -> model_validate().
    This handles models with bytes fields that can't use model_dump_json() directly.
    """
    data = _encode_bytes(instance.model_dump())
    json_str = json.dumps(data)
    raw = _decode_bytes(json.loads(json_str))
    return model_cls.model_validate(raw)

# ---------------------------------------------------------------------------
# Hypothesis strategies for each Pydantic model
# ---------------------------------------------------------------------------

# Reusable text strategy – printable, reasonably short
_text = st.text(
    alphabet=st.characters(whitelist_categories=("L", "N", "P", "Z")),
    min_size=1,
    max_size=30,
)

_short_list_of_text = st.lists(_text, max_size=5)


def _st_element() -> st.SearchStrategy[Element]:
    return st.builds(
        Element,
        name=_text,
        element_type=st.sampled_from(["service", "class", "module", "interface", "function"]),
        metadata=st.fixed_dictionaries({}, optional={"key": _text}),
    )


def _st_relationship() -> st.SearchStrategy[Relationship]:
    return st.builds(
        Relationship,
        source=_text,
        target=_text,
        relationship_type=st.sampled_from(["depends_on", "implements", "calls", "uses"]),
    )


def _st_source_file() -> st.SearchStrategy[SourceFile]:
    return st.builds(
        SourceFile,
        path=_text,
        language=st.sampled_from(["python", "java", "typescript", "go", "rust"]),
        imports=_short_list_of_text,
        exports=_short_list_of_text,
        public_interfaces=_short_list_of_text,
    )


def _st_module_boundary() -> st.SearchStrategy[ModuleBoundary]:
    return st.builds(
        ModuleBoundary,
        name=_text,
        files=_short_list_of_text,
        dependencies=_short_list_of_text,
    )


def _st_codebase_model() -> st.SearchStrategy[CodebaseModel]:
    return st.builds(
        CodebaseModel,
        root_path=_text,
        files=st.lists(_st_source_file(), max_size=3),
        module_boundaries=st.lists(_st_module_boundary(), max_size=3),
    )


def _st_pdf_content() -> st.SearchStrategy[PdfContent]:
    return st.builds(
        PdfContent,
        text_blocks=_short_list_of_text,
        images=st.lists(st.binary(min_size=0, max_size=50), max_size=3),
    )


def _st_document_model() -> st.SearchStrategy[DocumentModel]:
    return st.builds(
        DocumentModel,
        source_path=_text,
        file_type=st.sampled_from(["pdf", "docx", "png", "jpg", "svg"]),
        text_content=_short_list_of_text,
        images=st.lists(st.binary(min_size=0, max_size=50), max_size=3),
    )


def _st_analysis_result() -> st.SearchStrategy[AnalysisResult]:
    return st.builds(
        AnalysisResult,
        elements=st.lists(_st_element(), max_size=3),
        relationships=st.lists(_st_relationship(), max_size=3),
        patterns=_short_list_of_text,
        layers=_short_list_of_text,
    )


def _st_classified_element() -> st.SearchStrategy[ClassifiedElement]:
    return st.builds(
        ClassifiedElement,
        element=_st_element(),
        leanix_type=st.sampled_from(
            ["Organization", "Interface", "Data Object", "IT Component", "unclassified"]
        ),
        confidence=st.floats(min_value=0.0, max_value=1.0, allow_nan=False),
        alternative_types=st.just([]),
        evidence=_short_list_of_text,
    )


def _st_reconciled_model() -> st.SearchStrategy[ReconciledModel]:
    return st.builds(
        ReconciledModel,
        elements=st.lists(_st_classified_element(), max_size=3),
        relationships=st.lists(_st_relationship(), max_size=3),
        patterns=_short_list_of_text,
        layers=_short_list_of_text,
        discrepancies=_short_list_of_text,
    )


def _st_leanix_mapping() -> st.SearchStrategy[LeanIXMapping]:
    return st.builds(
        LeanIXMapping,
        element_name=_text,
        leanix_types=st.lists(
            st.fixed_dictionaries({"type": _text, "confidence": st.floats(min_value=0.0, max_value=1.0, allow_nan=False)}),
            max_size=3,
        ),
        evidence=_short_list_of_text,
        relationships=st.lists(
            st.fixed_dictionaries({"target": _text, "relationship": _text}),
            max_size=3,
        ),
    )


def _st_leanix_report() -> st.SearchStrategy[LeanIXReport]:
    return st.builds(
        LeanIXReport,
        mappings=st.lists(_st_leanix_mapping(), max_size=3),
    )


def _st_diagram_output() -> st.SearchStrategy[DiagramOutput]:
    return st.builds(
        DiagramOutput,
        diagram_type=st.sampled_from(
            ["dependency_graph", "component", "uml_class", "uml_sequence", "lld"]
        ),
        rendered_image=st.binary(min_size=1, max_size=100),
        image_format=st.sampled_from(["png", "svg"]),
        structured_data=st.fixed_dictionaries({}, optional={"nodes": st.just([]), "edges": st.just([])}),
        source_file=st.one_of(st.none(), _text),
    )


def _st_adr() -> st.SearchStrategy[ADR]:
    return st.builds(
        ADR,
        title=_text,
        status=st.sampled_from(["Proposed", "Accepted", "Deprecated", "Superseded"]),
        context=_text,
        decision=_text,
        consequences=_text,
    )


def _st_structured_output() -> st.SearchStrategy[StructuredOutput]:
    return st.builds(
        StructuredOutput,
        output_type=st.sampled_from(["analysis", "dependency_graph", "component_map", "leanix_mapping"]),
        data=st.fixed_dictionaries({}, optional={"key": _text, "count": st.integers(min_value=0, max_value=1000)}),
    )


def _st_validation_result() -> st.SearchStrategy[ValidationResult]:
    return st.builds(
        ValidationResult,
        valid=st.booleans(),
        errors=_short_list_of_text,
    )


# ---------------------------------------------------------------------------
# Property 19: JSON serialization round-trip
# ---------------------------------------------------------------------------
# **Validates: Requirements 12.1, 12.2, 12.3**


# --- Models WITHOUT bytes fields: use model_dump_json / model_validate_json ---


@settings(max_examples=100)
@given(model=_st_structured_output())
def test_structured_output_round_trip(model: StructuredOutput) -> None:
    """StructuredOutput survives JSON round-trip."""
    json_str = model.model_dump_json()
    restored = StructuredOutput.model_validate_json(json_str)
    assert restored == model


@settings(max_examples=100)
@given(model=_st_analysis_result())
def test_analysis_result_round_trip(model: AnalysisResult) -> None:
    """AnalysisResult survives JSON round-trip."""
    json_str = model.model_dump_json()
    restored = AnalysisResult.model_validate_json(json_str)
    assert restored == model


@settings(max_examples=100)
@given(model=_st_reconciled_model())
def test_reconciled_model_round_trip(model: ReconciledModel) -> None:
    """ReconciledModel survives JSON round-trip."""
    json_str = model.model_dump_json()
    restored = ReconciledModel.model_validate_json(json_str)
    assert restored == model


@settings(max_examples=100)
@given(model=_st_leanix_report())
def test_leanix_report_round_trip(model: LeanIXReport) -> None:
    """LeanIXReport survives JSON round-trip."""
    json_str = model.model_dump_json()
    restored = LeanIXReport.model_validate_json(json_str)
    assert restored == model


@settings(max_examples=100)
@given(model=_st_codebase_model())
def test_codebase_model_round_trip(model: CodebaseModel) -> None:
    """CodebaseModel survives JSON round-trip."""
    json_str = model.model_dump_json()
    restored = CodebaseModel.model_validate_json(json_str)
    assert restored == model


@settings(max_examples=100)
@given(model=_st_adr())
def test_adr_round_trip(model: ADR) -> None:
    """ADR survives JSON round-trip."""
    json_str = model.model_dump_json()
    restored = ADR.model_validate_json(json_str)
    assert restored == model


@settings(max_examples=100)
@given(model=_st_validation_result())
def test_validation_result_round_trip(model: ValidationResult) -> None:
    """ValidationResult survives JSON round-trip."""
    json_str = model.model_dump_json()
    restored = ValidationResult.model_validate_json(json_str)
    assert restored == model


# --- Models WITH bytes fields: use dict-based round-trip with base64 encoding ---
# Pydantic's model_dump_json() cannot serialize arbitrary bytes (non-UTF-8).
# The standard approach is to base64-encode bytes for JSON transport, which
# Pydantic's model_validate() accepts for bytes fields.


@settings(max_examples=100)
@given(model=_st_document_model())
def test_document_model_round_trip(model: DocumentModel) -> None:
    """DocumentModel survives JSON round-trip (bytes via base64)."""
    restored = _round_trip_via_dict(DocumentModel, model)
    assert restored == model


@settings(max_examples=100)
@given(model=_st_diagram_output())
def test_diagram_output_round_trip(model: DiagramOutput) -> None:
    """DiagramOutput survives JSON round-trip (bytes via base64)."""
    restored = _round_trip_via_dict(DiagramOutput, model)
    assert restored == model


@settings(max_examples=100)
@given(model=_st_pdf_content())
def test_pdf_content_round_trip(model: PdfContent) -> None:
    """PdfContent survives JSON round-trip (bytes via base64)."""
    restored = _round_trip_via_dict(PdfContent, model)
    assert restored == model


# ---------------------------------------------------------------------------
# Property 20: JSON Schema validation before write
# ---------------------------------------------------------------------------
# Feature: architectural-reverse-engineer, Property 20: JSON Schema validation before write
# **Validates: Requirements 12.4**
#
# For any structured output serialized to JSON, the output should pass
# validation against the published JSON Schema for its output type before
# being written to disk.

import os
import pathlib

import jsonschema

_SCHEMAS_DIR = pathlib.Path(__file__).resolve().parents[2] / "schemas"


def _load_schema(name: str) -> dict:
    """Load a JSON Schema file from the schemas directory."""
    schema_path = _SCHEMAS_DIR / name
    with open(schema_path) as f:
        return json.load(f)


def _prepare_for_schema(instance: Any) -> dict:
    """Convert a Pydantic model to a dict suitable for JSON Schema validation.

    Bytes fields are converted to base64 strings (matching the JSON Schema
    expectation that binary data is represented as base64-encoded strings).
    """
    data = instance.model_dump()
    return _bytes_to_base64(data)


def _bytes_to_base64(obj: Any) -> Any:
    """Recursively convert bytes values to base64 strings."""
    if isinstance(obj, bytes):
        return base64.b64encode(obj).decode("ascii")
    if isinstance(obj, dict):
        return {k: _bytes_to_base64(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_bytes_to_base64(v) for v in obj]
    return obj


@settings(max_examples=100)
@given(model=_st_codebase_model())
def test_codebase_model_schema_validation(model: CodebaseModel) -> None:
    """CodebaseModel serialized dict validates against its JSON Schema."""
    schema = _load_schema("codebase_model.json")
    data = _prepare_for_schema(model)
    jsonschema.validate(instance=data, schema=schema)


@settings(max_examples=100)
@given(model=_st_document_model())
def test_document_model_schema_validation(model: DocumentModel) -> None:
    """DocumentModel serialized dict validates against its JSON Schema."""
    schema = _load_schema("document_model.json")
    data = _prepare_for_schema(model)
    jsonschema.validate(instance=data, schema=schema)


@settings(max_examples=100)
@given(model=_st_analysis_result())
def test_analysis_result_schema_validation(model: AnalysisResult) -> None:
    """AnalysisResult serialized dict validates against its JSON Schema."""
    schema = _load_schema("analysis_result.json")
    data = _prepare_for_schema(model)
    jsonschema.validate(instance=data, schema=schema)


@settings(max_examples=100)
@given(model=_st_reconciled_model())
def test_reconciled_model_schema_validation(model: ReconciledModel) -> None:
    """ReconciledModel serialized dict validates against its JSON Schema."""
    schema = _load_schema("reconciled_model.json")
    data = _prepare_for_schema(model)
    jsonschema.validate(instance=data, schema=schema)


@settings(max_examples=100)
@given(model=_st_leanix_report())
def test_leanix_report_schema_validation(model: LeanIXReport) -> None:
    """LeanIXReport serialized dict validates against its JSON Schema."""
    schema = _load_schema("leanix_report.json")
    data = _prepare_for_schema(model)
    jsonschema.validate(instance=data, schema=schema)


@settings(max_examples=100)
@given(model=_st_diagram_output())
def test_diagram_output_schema_validation(model: DiagramOutput) -> None:
    """DiagramOutput serialized dict validates against its JSON Schema."""
    schema = _load_schema("diagram_output.json")
    data = _prepare_for_schema(model)
    jsonschema.validate(instance=data, schema=schema)


@settings(max_examples=100)
@given(model=_st_adr())
def test_adr_schema_validation(model: ADR) -> None:
    """ADR serialized dict validates against its JSON Schema."""
    schema = _load_schema("adr.json")
    data = _prepare_for_schema(model)
    jsonschema.validate(instance=data, schema=schema)


@settings(max_examples=100)
@given(model=_st_structured_output())
def test_structured_output_schema_validation(model: StructuredOutput) -> None:
    """StructuredOutput serialized dict validates against its JSON Schema."""
    schema = _load_schema("structured_output.json")
    data = _prepare_for_schema(model)
    jsonschema.validate(instance=data, schema=schema)


@settings(max_examples=100)
@given(model=_st_validation_result())
def test_validation_result_schema_validation(model: ValidationResult) -> None:
    """ValidationResult serialized dict validates against its JSON Schema."""
    schema = _load_schema("validation_result.json")
    data = _prepare_for_schema(model)
    jsonschema.validate(instance=data, schema=schema)
