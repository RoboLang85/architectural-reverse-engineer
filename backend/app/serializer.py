"""Serializer component for structured output JSON serialization, deserialization, and validation.

Handles:
- Serializing StructuredOutput (and related models) to JSON strings, with base64 encoding for bytes fields.
- Deserializing JSON strings back to Pydantic model instances, with base64 decoding for bytes fields.
- Validating JSON strings against published JSON Schemas.
"""

from __future__ import annotations

import base64
import json
import pathlib
from typing import Any, TypeVar

import jsonschema
from pydantic import BaseModel

from app.errors import SchemaValidationError
from app.models import ValidationResult

T = TypeVar("T", bound=BaseModel)

_SCHEMAS_DIR = pathlib.Path(__file__).resolve().parents[1] / "schemas"


def _encode_bytes(obj: Any) -> Any:
    """Recursively base64-encode bytes values for JSON transport."""
    if isinstance(obj, bytes):
        return {"__b64__": base64.b64encode(obj).decode("ascii")}
    if isinstance(obj, dict):
        return {k: _encode_bytes(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_encode_bytes(v) for v in obj]
    return obj


def _decode_bytes(obj: Any) -> Any:
    """Recursively decode base64-tagged values back to bytes."""
    if isinstance(obj, dict) and "__b64__" in obj and len(obj) == 1:
        return base64.b64decode(obj["__b64__"])
    if isinstance(obj, dict):
        return {k: _decode_bytes(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_decode_bytes(v) for v in obj]
    return obj


def _value_contains_bytes(obj: Any) -> bool:
    """Recursively check whether *obj* contains any ``bytes`` values.

    Traverses dicts, lists, tuples, and nested :class:`BaseModel` instances.
    """
    if isinstance(obj, bytes):
        return True
    if isinstance(obj, dict):
        return any(_value_contains_bytes(v) for v in obj.values())
    if isinstance(obj, (list, tuple)):
        return any(_value_contains_bytes(v) for v in obj)
    if isinstance(obj, BaseModel):
        return _value_contains_bytes(obj.__dict__)
    return False


def _has_bytes_fields(model: BaseModel) -> bool:
    """Check if a Pydantic model instance contains any bytes values at any nesting depth."""
    return _value_contains_bytes(model.__dict__)


def serialize(data: BaseModel) -> str:
    """Serialize a Pydantic model to a JSON string.

    For models containing bytes fields (e.g. DiagramOutput.rendered_image,
    DocumentModel.images), bytes are base64-encoded using a ``{"__b64__": "..."}``
    wrapper so the JSON is valid and round-trippable.

    For models without bytes fields, uses Pydantic's native ``model_dump_json()``.
    """
    if _has_bytes_fields(data):
        encoded = _encode_bytes(data.model_dump())
        return json.dumps(encoded)
    return data.model_dump_json()


def deserialize(json_str: str, schema: type[T]) -> T:
    """Deserialize a JSON string back into a Pydantic model instance.

    Handles base64-encoded bytes fields produced by :func:`serialize`.
    """
    raw = json.loads(json_str)
    decoded = _decode_bytes(raw)
    return schema.model_validate(decoded)


def validate(json_str: str, schema_path: str) -> ValidationResult:
    """Validate a JSON string against a published JSON Schema.

    Args:
        json_str: The JSON string to validate.
        schema_path: Filename of the schema inside the ``backend/schemas/`` directory
                     (e.g. ``"codebase_model.json"``).

    Returns:
        A :class:`ValidationResult` indicating whether validation passed and any errors.

    Raises:
        SchemaValidationError: If the schema file cannot be loaded.
    """
    full_path = _SCHEMAS_DIR / schema_path
    try:
        with open(full_path) as f:
            schema = json.load(f)
    except (OSError, json.JSONDecodeError) as exc:
        raise SchemaValidationError(
            f"Failed to load schema '{schema_path}': {exc}",
            validation_errors=[str(exc)],
        )

    data = json.loads(json_str)

    validator = jsonschema.Draft7Validator(schema)
    errors = sorted(validator.iter_errors(data), key=lambda e: list(e.absolute_path))
    if errors:
        error_messages = [_format_validation_error(e) for e in errors]
        return ValidationResult(valid=False, errors=error_messages)

    return ValidationResult(valid=True, errors=[])


def _format_validation_error(error: jsonschema.ValidationError) -> str:
    """Format a jsonschema ValidationError into a human-readable string."""
    path = ".".join(str(p) for p in error.absolute_path) if error.absolute_path else "(root)"
    return f"{path}: {error.message}"
