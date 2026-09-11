"""AI Engine for architectural analysis using OpenAI GPT-4."""

from __future__ import annotations

import json
import os
from typing import Any

import openai

from app.errors import AIServiceError
from app.models import (
    AnalysisResult,
    ClassifiedElement,
    CodebaseModel,
    DocumentModel,
    Element,
    ReconciledModel,
    Relationship,
)

# --- Confidence threshold ---
CONFIDENCE_THRESHOLD = 0.5

# --- Valid LeanIX types ---
VALID_LEANIX_TYPES = frozenset(
    ["Organization", "Interface", "Data Object", "IT Component"]
)

# --- Prompt Templates ---

CODE_ANALYSIS_PROMPT = """\
You are an expert software architect. Analyze the following codebase structure and identify:
1. Architectural elements (services, modules, classes, interfaces)
2. Relationships between elements (dependencies, implementations, calls)
3. Architectural patterns (e.g., microservices, layered, event-driven)
4. Architectural layers (e.g., presentation, business logic, data access)

Codebase root: {root_path}
Files:
{files_summary}

Module boundaries:
{module_summary}

Respond in JSON with this structure:
{{
  "elements": [{{"name": "...", "element_type": "...", "metadata": {{}}}}],
  "relationships": [{{"source": "...", "target": "...", "relationship_type": "..."}}],
  "patterns": ["..."],
  "layers": ["..."]
}}
"""

DOCUMENT_ANALYSIS_PROMPT = """\
You are an expert software architect. Analyze the following document content and identify:
1. Architectural elements (services, modules, classes, interfaces)
2. Relationships between elements (dependencies, implementations, calls)
3. Architectural patterns mentioned or implied
4. Architectural layers mentioned or implied

Document source: {source_path}
File type: {file_type}
Text content:
{text_content}

Respond in JSON with this structure:
{{
  "elements": [{{"name": "...", "element_type": "...", "metadata": {{}}}}],
  "relationships": [{{"source": "...", "target": "...", "relationship_type": "..."}}],
  "patterns": ["..."],
  "layers": ["..."]
}}
"""

RECONCILIATION_PROMPT = """\
You are an expert software architect. You have two analyses of the same system:

Code analysis:
{code_analysis}

Document analysis:
{doc_analysis}

Reconcile these analyses:
1. Merge elements, preferring code analysis for structural facts and document analysis for intent
2. Merge relationships from both sources
3. Combine detected patterns and layers
4. Identify discrepancies between code and documentation

For each element, classify it into a LeanIX type (Organization, Interface, Data Object, IT Component)
with a confidence score (0.0-1.0). If confidence is below 0.5, set leanix_type to "unclassified".

Respond in JSON with this structure:
{{
  "elements": [{{
    "element": {{"name": "...", "element_type": "...", "metadata": {{}}}},
    "leanix_type": "...",
    "confidence": 0.0,
    "alternative_types": [{{"type": "...", "confidence": 0.0}}],
    "evidence": ["..."]
  }}],
  "relationships": [{{"source": "...", "target": "...", "relationship_type": "..."}}],
  "patterns": ["..."],
  "layers": ["..."],
  "discrepancies": ["..."]
}}
"""

CLASSIFICATION_PROMPT = """\
You are an expert enterprise architect. Classify each of the following architectural elements
into LeanIX object types. Valid types: Organization, Interface, Data Object, IT Component.

For each element, provide:
- leanix_type: the best matching LeanIX type
- confidence: a score from 0.0 to 1.0
- alternative_types: other possible types with their confidence scores
- evidence: reasons supporting the classification

If confidence is below 0.5, set leanix_type to "unclassified".

Elements:
{elements}

Respond in JSON with this structure:
{{
  "classified": [{{
    "element": {{"name": "...", "element_type": "...", "metadata": {{}}}},
    "leanix_type": "...",
    "confidence": 0.0,
    "alternative_types": [{{"type": "...", "confidence": 0.0}}],
    "evidence": ["..."]
  }}]
}}
"""


class AIEngine:
    """AI-powered analysis engine using OpenAI GPT-4."""

    def __init__(self, api_key: str | None = None, model: str = "gpt-4") -> None:
        resolved_key = api_key or os.environ.get("OPENAI_API_KEY", "")
        if not resolved_key:
            raise AIServiceError(
                "OpenAI API key not provided. Set OPENAI_API_KEY or pass api_key.",
                details={"error_type": "auth"},
            )
        self._client = openai.OpenAI(api_key=resolved_key)
        self._model = model

    def analyze_code(self, codebase: CodebaseModel) -> AnalysisResult:
        """Analyze code structure using GPT-4.

        Args:
            codebase: Parsed codebase model.

        Returns:
            AnalysisResult with identified elements, relationships, patterns, layers.

        Raises:
            AIServiceError: On OpenAI API failures.
        """
        files_summary = "\n".join(
            f"  - {f.path} ({f.language}): imports={f.imports}, exports={f.exports}"
            for f in codebase.files
        )
        module_summary = "\n".join(
            f"  - {m.name}: files={m.files}, deps={m.dependencies}"
            for m in codebase.module_boundaries
        )
        prompt = CODE_ANALYSIS_PROMPT.format(
            root_path=codebase.root_path,
            files_summary=files_summary or "(none)",
            module_summary=module_summary or "(none)",
        )
        raw = self._call_openai(prompt)
        return _parse_analysis_result(raw)

    def analyze_document(self, document: DocumentModel) -> AnalysisResult:
        """Analyze document/diagram content using GPT-4.

        Args:
            document: Extracted document model.

        Returns:
            AnalysisResult with identified elements, relationships, patterns, layers.

        Raises:
            AIServiceError: On OpenAI API failures.
        """
        text_content = "\n".join(document.text_content) if document.text_content else "(no text)"

        messages: list[dict[str, Any]] = []

        if document.images:
            # Use vision model for image analysis
            content_parts: list[dict[str, Any]] = [
                {
                    "type": "text",
                    "text": DOCUMENT_ANALYSIS_PROMPT.format(
                        source_path=document.source_path,
                        file_type=document.file_type,
                        text_content=text_content,
                    ),
                }
            ]
            for img_bytes in document.images:
                import base64

                b64 = base64.b64encode(img_bytes).decode("utf-8")
                content_parts.append(
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:image/png;base64,{b64}"},
                    }
                )
            messages = [{"role": "user", "content": content_parts}]
            raw = self._call_openai_messages(messages)
        else:
            prompt = DOCUMENT_ANALYSIS_PROMPT.format(
                source_path=document.source_path,
                file_type=document.file_type,
                text_content=text_content,
            )
            raw = self._call_openai(prompt)

        return _parse_analysis_result(raw)

    def reconcile(
        self,
        code_analysis: AnalysisResult,
        doc_analysis: AnalysisResult,
    ) -> ReconciledModel:
        """Merge code and document analyses into a reconciled model.

        Args:
            code_analysis: Analysis from code.
            doc_analysis: Analysis from documents.

        Returns:
            ReconciledModel with merged elements, relationships, discrepancies.

        Raises:
            AIServiceError: On OpenAI API failures.
        """
        prompt = RECONCILIATION_PROMPT.format(
            code_analysis=code_analysis.model_dump_json(indent=2),
            doc_analysis=doc_analysis.model_dump_json(indent=2),
        )
        raw = self._call_openai(prompt)
        return _parse_reconciled_model(raw)

    def classify_elements(
        self, elements: list[Element]
    ) -> list[ClassifiedElement]:
        """Classify architectural elements into LeanIX types.

        Args:
            elements: List of discovered elements.

        Returns:
            List of ClassifiedElement with LeanIX types and confidence scores.

        Raises:
            AIServiceError: On OpenAI API failures.
        """
        if not elements:
            return []

        elements_json = json.dumps(
            [e.model_dump() for e in elements], indent=2
        )
        prompt = CLASSIFICATION_PROMPT.format(elements=elements_json)
        raw = self._call_openai(prompt)
        return _parse_classified_elements(raw, elements)

    # --- Internal helpers ---

    def _call_openai(self, prompt: str) -> str:
        """Make a simple text completion call to OpenAI."""
        messages = [{"role": "user", "content": prompt}]
        return self._call_openai_messages(messages)

    def _call_openai_messages(self, messages: list[dict[str, Any]]) -> str:
        """Make a chat completion call to OpenAI with arbitrary messages."""
        try:
            response = self._client.chat.completions.create(
                model=self._model,
                messages=messages,
                temperature=0.2,
            )
            content = response.choices[0].message.content
            return content or ""
        except openai.RateLimitError as exc:
            raise AIServiceError(
                "OpenAI rate limit exceeded. Please wait and retry.",
                details={"error_type": "rate_limit", "retry": True},
            ) from exc
        except openai.APITimeoutError as exc:
            raise AIServiceError(
                "OpenAI request timed out. Please retry.",
                details={"error_type": "timeout", "retry": True},
            ) from exc
        except openai.AuthenticationError as exc:
            raise AIServiceError(
                "OpenAI authentication failed. Check your API key.",
                details={"error_type": "auth", "retry": False},
            ) from exc
        except openai.APIError as exc:
            raise AIServiceError(
                f"OpenAI API error: {exc}",
                details={"error_type": "api_error", "retry": True},
            ) from exc


# --- Response parsing helpers ---


def _extract_json(raw: str) -> dict:
    """Extract JSON from a raw LLM response, handling markdown fences."""
    text = raw.strip()
    if text.startswith("```"):
        # Strip markdown code fences
        lines = text.split("\n")
        # Remove first and last fence lines
        lines = [l for l in lines if not l.strip().startswith("```")]
        text = "\n".join(lines)
    try:
        return json.loads(text)
    except json.JSONDecodeError as exc:
        raise AIServiceError(
            "Failed to parse AI response as JSON.",
            details={"raw_response": raw[:500], "error": str(exc)},
        ) from exc


def _extract_element(e: dict) -> Element:
    """Construct a single Element from a parsed JSON dict."""
    return Element(
        name=e.get("name", ""),
        element_type=e.get("element_type", ""),
        metadata=e.get("metadata", {}),
    )


def _extract_elements(items: list[dict]) -> list[Element]:
    """Construct Element objects from parsed JSON dicts."""
    return [_extract_element(e) for e in items]


def _extract_relationships(items: list[dict]) -> list[Relationship]:
    """Construct Relationship objects from parsed JSON dicts."""
    return [
        Relationship(
            source=r.get("source", ""),
            target=r.get("target", ""),
            relationship_type=r.get("relationship_type", ""),
        )
        for r in items
    ]


def _parse_analysis_result(raw: str) -> AnalysisResult:
    """Parse raw AI response into an AnalysisResult."""
    data = _extract_json(raw)
    return AnalysisResult(
        elements=_extract_elements(data.get("elements", [])),
        relationships=_extract_relationships(data.get("relationships", [])),
        patterns=data.get("patterns", []),
        layers=data.get("layers", []),
    )


def _parse_reconciled_model(raw: str) -> ReconciledModel:
    """Parse raw AI response into a ReconciledModel."""
    data = _extract_json(raw)
    elements = []
    for ce in data.get("elements", []):
        elem_data = ce.get("element", {})
        element = _extract_element(elem_data)
        confidence = float(ce.get("confidence", 0.0))
        leanix_type = ce.get("leanix_type", "unclassified")
        if confidence < CONFIDENCE_THRESHOLD:
            leanix_type = "unclassified"
        elements.append(
            ClassifiedElement(
                element=element,
                leanix_type=leanix_type,
                confidence=confidence,
                alternative_types=ce.get("alternative_types", []),
                evidence=ce.get("evidence", []),
            )
        )
    return ReconciledModel(
        elements=elements,
        relationships=_extract_relationships(data.get("relationships", [])),
        patterns=data.get("patterns", []),
        layers=data.get("layers", []),
        discrepancies=data.get("discrepancies", []),
    )


def _parse_classified_elements(
    raw: str, original_elements: list[Element]
) -> list[ClassifiedElement]:
    """Parse raw AI response into a list of ClassifiedElement."""
    data = _extract_json(raw)
    classified = []
    items = data.get("classified", [])

    # Build a lookup from original elements by name for fallback
    originals_by_name = {e.name: e for e in original_elements}

    for item in items:
        elem_data = item.get("element", {})
        name = elem_data.get("name", "")
        # Prefer original element data if available
        element = originals_by_name.get(
            name,
            _extract_element(elem_data),
        )
        confidence = float(item.get("confidence", 0.0))
        leanix_type = item.get("leanix_type", "unclassified")
        if confidence < CONFIDENCE_THRESHOLD:
            leanix_type = "unclassified"
        classified.append(
            ClassifiedElement(
                element=element,
                leanix_type=leanix_type,
                confidence=confidence,
                alternative_types=item.get("alternative_types", []),
                evidence=item.get("evidence", []),
            )
        )
    return classified
