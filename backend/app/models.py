"""Pydantic data models for the Architectural Reverse Engineer."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


# --- Input Models ---


class SourceInput(BaseModel):
    """Input specification for a codebase source."""

    input_type: Literal["local_path", "github_url"]
    value: str  # file path or URL


class DocumentInput(BaseModel):
    """Input specification for an architectural document."""

    file_path: str
    file_type: Literal["pdf", "docx", "png", "jpg", "svg"]


# --- Codebase Models ---


class SourceFile(BaseModel):
    """Parsed representation of a single source file."""

    path: str
    language: str
    imports: list[str] = Field(default_factory=list)
    exports: list[str] = Field(default_factory=list)
    public_interfaces: list[str] = Field(default_factory=list)


class ModuleBoundary(BaseModel):
    """A logical module boundary within a codebase."""

    name: str
    files: list[str] = Field(default_factory=list)
    dependencies: list[str] = Field(default_factory=list)  # names of other modules


class CodebaseModel(BaseModel):
    """Complete parsed representation of a codebase."""

    root_path: str
    files: list[SourceFile] = Field(default_factory=list)
    module_boundaries: list[ModuleBoundary] = Field(default_factory=list)


# --- Document Models ---


class PdfContent(BaseModel):
    """Extracted content from a PDF file."""

    text_blocks: list[str] = Field(default_factory=list)
    images: list[bytes] = Field(default_factory=list)


class DocumentModel(BaseModel):
    """Extracted content from any supported document."""

    source_path: str
    file_type: str
    text_content: list[str] = Field(default_factory=list)
    images: list[bytes] = Field(default_factory=list)


# --- Analysis Models ---


class Element(BaseModel):
    """A discovered architectural element."""

    name: str
    element_type: str  # e.g., "service", "class", "module", "interface"
    metadata: dict = Field(default_factory=dict)


class Relationship(BaseModel):
    """A relationship between two architectural elements."""

    source: str
    target: str
    relationship_type: str  # e.g., "depends_on", "implements", "calls"


class AnalysisResult(BaseModel):
    """Result of AI-powered analysis of code or documents."""

    elements: list[Element] = Field(default_factory=list)
    relationships: list[Relationship] = Field(default_factory=list)
    patterns: list[str] = Field(default_factory=list)  # detected architectural patterns
    layers: list[str] = Field(default_factory=list)  # detected architectural layers


# --- Classification Models ---


class ClassifiedElement(BaseModel):
    """An element classified into LeanIX object types."""

    element: Element
    leanix_type: str  # "Organization", "Interface", "Data Object", "IT Component", or custom
    confidence: float = Field(ge=0.0, le=1.0)
    alternative_types: list[dict] = Field(default_factory=list)  # [{type: str, confidence: float}]
    evidence: list[str] = Field(default_factory=list)


class ReconciledModel(BaseModel):
    """Merged analysis from code and document sources."""

    elements: list[ClassifiedElement] = Field(default_factory=list)
    relationships: list[Relationship] = Field(default_factory=list)
    patterns: list[str] = Field(default_factory=list)
    layers: list[str] = Field(default_factory=list)
    discrepancies: list[str] = Field(default_factory=list)  # differences between code and docs


# --- LeanIX Models ---


class LeanIXMapping(BaseModel):
    """Mapping of a single element to LeanIX object types."""

    element_name: str
    leanix_types: list[dict] = Field(default_factory=list)  # [{type: str, confidence: float}]
    evidence: list[str] = Field(default_factory=list)
    relationships: list[dict] = Field(default_factory=list)  # [{target: str, relationship: str}]


class LeanIXReport(BaseModel):
    """Complete LeanIX mapping report."""

    mappings: list[LeanIXMapping] = Field(default_factory=list)


# --- Output Models ---


class DiagramOutput(BaseModel):
    """Output from diagram generation."""

    diagram_type: str  # "dependency_graph", "component", "uml_class", "uml_sequence", "lld"
    rendered_image: bytes  # PNG or SVG
    image_format: Literal["png", "svg"]
    structured_data: dict = Field(default_factory=dict)  # JSON-serializable graph data
    source_file: str | None = None  # PlantUML source for UML diagrams


class ADR(BaseModel):
    """Architectural Decision Record."""

    title: str
    status: str  # "Proposed", "Accepted", "Deprecated", "Superseded"
    context: str
    decision: str
    consequences: str


class StructuredOutput(BaseModel):
    """Union type for all JSON-serializable outputs."""

    output_type: str
    data: dict = Field(default_factory=dict)  # The actual structured data


class ValidationResult(BaseModel):
    """Result of JSON Schema validation."""

    valid: bool
    errors: list[str] = Field(default_factory=list)
