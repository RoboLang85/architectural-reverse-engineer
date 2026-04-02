"""Unit tests for the AI Engine component."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest

from app.ai_engine import (
    AIEngine,
    CONFIDENCE_THRESHOLD,
    VALID_LEANIX_TYPES,
    _extract_json,
    _parse_analysis_result,
    _parse_classified_elements,
    _parse_reconciled_model,
)
from app.errors import AIServiceError
from app.models import (
    AnalysisResult,
    ClassifiedElement,
    CodebaseModel,
    DocumentModel,
    Element,
    ModuleBoundary,
    ReconciledModel,
    Relationship,
    SourceFile,
)


# --- Fixtures ---


@pytest.fixture
def mock_openai_client():
    """Patch openai.OpenAI so AIEngine can be constructed without a real key."""
    with patch("app.ai_engine.openai.OpenAI") as mock_cls:
        mock_client = MagicMock()
        mock_cls.return_value = mock_client
        yield mock_client


def _make_engine(mock_openai_client) -> AIEngine:
    """Create an AIEngine with a mocked OpenAI client."""
    engine = AIEngine(api_key="test-key")
    engine._client = mock_openai_client
    return engine


def _mock_completion(mock_client: MagicMock, content: str) -> None:
    """Configure the mock client to return a specific completion content."""
    mock_response = MagicMock()
    mock_response.choices = [MagicMock()]
    mock_response.choices[0].message.content = content
    mock_client.chat.completions.create.return_value = mock_response


# --- Constructor tests ---


class TestAIEngineInit:
    def test_raises_without_api_key(self):
        with patch.dict("os.environ", {}, clear=True):
            with pytest.raises(AIServiceError, match="API key not provided"):
                AIEngine()

    def test_accepts_explicit_api_key(self, mock_openai_client):
        engine = AIEngine(api_key="sk-test")
        assert engine._model == "gpt-4"

    def test_accepts_env_api_key(self, mock_openai_client):
        with patch.dict("os.environ", {"OPENAI_API_KEY": "sk-env"}):
            engine = AIEngine()
            assert engine._model == "gpt-4"

    def test_custom_model(self, mock_openai_client):
        engine = AIEngine(api_key="sk-test", model="gpt-4-turbo")
        assert engine._model == "gpt-4-turbo"


# --- analyze_code tests ---


class TestAnalyzeCode:
    def test_returns_analysis_result(self, mock_openai_client):
        engine = _make_engine(mock_openai_client)
        response_data = {
            "elements": [
                {"name": "AuthService", "element_type": "service", "metadata": {"lang": "python"}}
            ],
            "relationships": [
                {"source": "AuthService", "target": "UserDB", "relationship_type": "depends_on"}
            ],
            "patterns": ["layered"],
            "layers": ["presentation", "business"],
        }
        _mock_completion(mock_openai_client, json.dumps(response_data))

        codebase = CodebaseModel(
            root_path="/project",
            files=[
                SourceFile(path="auth.py", language="python", imports=["db"], exports=["AuthService"])
            ],
            module_boundaries=[ModuleBoundary(name="auth", files=["auth.py"], dependencies=["db"])],
        )
        result = engine.analyze_code(codebase)

        assert isinstance(result, AnalysisResult)
        assert len(result.elements) == 1
        assert result.elements[0].name == "AuthService"
        assert len(result.relationships) == 1
        assert result.patterns == ["layered"]
        assert result.layers == ["presentation", "business"]

    def test_handles_empty_codebase(self, mock_openai_client):
        engine = _make_engine(mock_openai_client)
        _mock_completion(
            mock_openai_client,
            json.dumps({"elements": [], "relationships": [], "patterns": [], "layers": []}),
        )
        codebase = CodebaseModel(root_path="/empty")
        result = engine.analyze_code(codebase)
        assert result.elements == []
        assert result.relationships == []


# --- analyze_document tests ---


class TestAnalyzeDocument:
    def test_text_only_document(self, mock_openai_client):
        engine = _make_engine(mock_openai_client)
        response_data = {
            "elements": [{"name": "Gateway", "element_type": "module", "metadata": {}}],
            "relationships": [],
            "patterns": ["microservices"],
            "layers": [],
        }
        _mock_completion(mock_openai_client, json.dumps(response_data))

        doc = DocumentModel(
            source_path="arch.pdf",
            file_type="pdf",
            text_content=["System uses a gateway pattern"],
            images=[],
        )
        result = engine.analyze_document(doc)

        assert isinstance(result, AnalysisResult)
        assert result.elements[0].name == "Gateway"
        assert result.patterns == ["microservices"]

    def test_document_with_images_uses_vision(self, mock_openai_client):
        engine = _make_engine(mock_openai_client)
        response_data = {
            "elements": [{"name": "Diagram", "element_type": "component", "metadata": {}}],
            "relationships": [],
            "patterns": [],
            "layers": [],
        }
        _mock_completion(mock_openai_client, json.dumps(response_data))

        doc = DocumentModel(
            source_path="diagram.png",
            file_type="png",
            text_content=[],
            images=[b"\x89PNG\r\n\x1a\n"],
        )
        result = engine.analyze_document(doc)

        assert isinstance(result, AnalysisResult)
        # Verify vision-style messages were used (content is a list)
        call_args = mock_openai_client.chat.completions.create.call_args
        messages = call_args.kwargs.get("messages") or call_args[1].get("messages")
        assert isinstance(messages[0]["content"], list)

    def test_empty_document(self, mock_openai_client):
        engine = _make_engine(mock_openai_client)
        _mock_completion(
            mock_openai_client,
            json.dumps({"elements": [], "relationships": [], "patterns": [], "layers": []}),
        )
        doc = DocumentModel(source_path="empty.pdf", file_type="pdf")
        result = engine.analyze_document(doc)
        assert result.elements == []


# --- reconcile tests ---


class TestReconcile:
    def test_merges_analyses(self, mock_openai_client):
        engine = _make_engine(mock_openai_client)
        response_data = {
            "elements": [
                {
                    "element": {"name": "UserService", "element_type": "service", "metadata": {}},
                    "leanix_type": "IT Component",
                    "confidence": 0.9,
                    "alternative_types": [{"type": "Interface", "confidence": 0.3}],
                    "evidence": ["Handles user CRUD"],
                }
            ],
            "relationships": [
                {"source": "UserService", "target": "DB", "relationship_type": "depends_on"}
            ],
            "patterns": ["layered", "microservices"],
            "layers": ["api", "data"],
            "discrepancies": ["DB not documented"],
        }
        _mock_completion(mock_openai_client, json.dumps(response_data))

        code_analysis = AnalysisResult(
            elements=[Element(name="UserService", element_type="service")],
            relationships=[],
            patterns=["layered"],
            layers=["api"],
        )
        doc_analysis = AnalysisResult(
            elements=[Element(name="UserService", element_type="component")],
            relationships=[],
            patterns=["microservices"],
            layers=["data"],
        )
        result = engine.reconcile(code_analysis, doc_analysis)

        assert isinstance(result, ReconciledModel)
        assert len(result.elements) == 1
        assert result.elements[0].leanix_type == "IT Component"
        assert result.elements[0].confidence == 0.9
        assert result.discrepancies == ["DB not documented"]

    def test_low_confidence_becomes_unclassified(self, mock_openai_client):
        engine = _make_engine(mock_openai_client)
        response_data = {
            "elements": [
                {
                    "element": {"name": "Unknown", "element_type": "module", "metadata": {}},
                    "leanix_type": "IT Component",
                    "confidence": 0.3,
                    "alternative_types": [],
                    "evidence": [],
                }
            ],
            "relationships": [],
            "patterns": [],
            "layers": [],
            "discrepancies": [],
        }
        _mock_completion(mock_openai_client, json.dumps(response_data))

        result = engine.reconcile(
            AnalysisResult(), AnalysisResult()
        )
        assert result.elements[0].leanix_type == "unclassified"
        assert result.elements[0].confidence == 0.3


# --- classify_elements tests ---


class TestClassifyElements:
    def test_classifies_elements(self, mock_openai_client):
        engine = _make_engine(mock_openai_client)
        response_data = {
            "classified": [
                {
                    "element": {"name": "PaymentAPI", "element_type": "interface", "metadata": {}},
                    "leanix_type": "Interface",
                    "confidence": 0.85,
                    "alternative_types": [{"type": "IT Component", "confidence": 0.4}],
                    "evidence": ["Exposes REST endpoints"],
                },
                {
                    "element": {"name": "OrderDB", "element_type": "database", "metadata": {}},
                    "leanix_type": "Data Object",
                    "confidence": 0.7,
                    "alternative_types": [],
                    "evidence": ["Stores order data"],
                },
            ]
        }
        _mock_completion(mock_openai_client, json.dumps(response_data))

        elements = [
            Element(name="PaymentAPI", element_type="interface"),
            Element(name="OrderDB", element_type="database"),
        ]
        result = engine.classify_elements(elements)

        assert len(result) == 2
        assert all(isinstance(ce, ClassifiedElement) for ce in result)
        assert result[0].leanix_type == "Interface"
        assert result[0].confidence == 0.85
        assert result[1].leanix_type == "Data Object"

    def test_empty_elements_returns_empty(self, mock_openai_client):
        engine = _make_engine(mock_openai_client)
        result = engine.classify_elements([])
        assert result == []
        # Should not call OpenAI
        mock_openai_client.chat.completions.create.assert_not_called()

    def test_low_confidence_flagged_unclassified(self, mock_openai_client):
        engine = _make_engine(mock_openai_client)
        response_data = {
            "classified": [
                {
                    "element": {"name": "Misc", "element_type": "unknown", "metadata": {}},
                    "leanix_type": "Organization",
                    "confidence": 0.2,
                    "alternative_types": [],
                    "evidence": [],
                }
            ]
        }
        _mock_completion(mock_openai_client, json.dumps(response_data))

        elements = [Element(name="Misc", element_type="unknown")]
        result = engine.classify_elements(elements)

        assert result[0].leanix_type == "unclassified"
        assert result[0].confidence == 0.2

    def test_preserves_original_element_data(self, mock_openai_client):
        engine = _make_engine(mock_openai_client)
        response_data = {
            "classified": [
                {
                    "element": {"name": "Svc", "element_type": "service", "metadata": {}},
                    "leanix_type": "IT Component",
                    "confidence": 0.9,
                    "alternative_types": [],
                    "evidence": ["runs as container"],
                }
            ]
        }
        _mock_completion(mock_openai_client, json.dumps(response_data))

        original = Element(name="Svc", element_type="service", metadata={"port": 8080})
        result = engine.classify_elements([original])

        # Should use the original element with its metadata
        assert result[0].element.metadata == {"port": 8080}


# --- Error handling tests ---


class TestErrorHandling:
    def test_rate_limit_error(self, mock_openai_client):
        import openai as openai_mod

        engine = _make_engine(mock_openai_client)
        mock_openai_client.chat.completions.create.side_effect = openai_mod.RateLimitError(
            message="rate limit",
            response=MagicMock(status_code=429),
            body=None,
        )
        codebase = CodebaseModel(root_path="/test")
        with pytest.raises(AIServiceError, match="rate limit") as exc_info:
            engine.analyze_code(codebase)
        assert exc_info.value.details["error_type"] == "rate_limit"
        assert exc_info.value.details["retry"] is True

    def test_timeout_error(self, mock_openai_client):
        import openai as openai_mod

        engine = _make_engine(mock_openai_client)
        mock_openai_client.chat.completions.create.side_effect = openai_mod.APITimeoutError(
            request=MagicMock(),
        )
        codebase = CodebaseModel(root_path="/test")
        with pytest.raises(AIServiceError, match="timed out") as exc_info:
            engine.analyze_code(codebase)
        assert exc_info.value.details["error_type"] == "timeout"
        assert exc_info.value.details["retry"] is True

    def test_auth_error(self, mock_openai_client):
        import openai as openai_mod

        engine = _make_engine(mock_openai_client)
        mock_openai_client.chat.completions.create.side_effect = openai_mod.AuthenticationError(
            message="invalid key",
            response=MagicMock(status_code=401),
            body=None,
        )
        codebase = CodebaseModel(root_path="/test")
        with pytest.raises(AIServiceError, match="authentication failed") as exc_info:
            engine.analyze_code(codebase)
        assert exc_info.value.details["error_type"] == "auth"
        assert exc_info.value.details["retry"] is False

    def test_generic_api_error(self, mock_openai_client):
        import openai as openai_mod

        engine = _make_engine(mock_openai_client)
        mock_openai_client.chat.completions.create.side_effect = openai_mod.APIError(
            message="server error",
            request=MagicMock(),
            body=None,
        )
        codebase = CodebaseModel(root_path="/test")
        with pytest.raises(AIServiceError, match="API error") as exc_info:
            engine.analyze_code(codebase)
        assert exc_info.value.details["error_type"] == "api_error"

    def test_invalid_json_response(self, mock_openai_client):
        engine = _make_engine(mock_openai_client)
        _mock_completion(mock_openai_client, "this is not json")
        codebase = CodebaseModel(root_path="/test")
        with pytest.raises(AIServiceError, match="parse AI response"):
            engine.analyze_code(codebase)


# --- JSON extraction helper tests ---


class TestExtractJson:
    def test_plain_json(self):
        data = _extract_json('{"key": "value"}')
        assert data == {"key": "value"}

    def test_markdown_fenced_json(self):
        raw = '```json\n{"key": "value"}\n```'
        data = _extract_json(raw)
        assert data == {"key": "value"}

    def test_markdown_fenced_no_lang(self):
        raw = '```\n{"items": [1, 2]}\n```'
        data = _extract_json(raw)
        assert data == {"items": [1, 2]}

    def test_invalid_json_raises(self):
        with pytest.raises(AIServiceError, match="parse AI response"):
            _extract_json("not json at all")


# --- Parse helpers tests ---


class TestParseHelpers:
    def test_parse_analysis_result(self):
        raw = json.dumps(
            {
                "elements": [{"name": "A", "element_type": "service", "metadata": {}}],
                "relationships": [{"source": "A", "target": "B", "relationship_type": "calls"}],
                "patterns": ["event-driven"],
                "layers": ["api"],
            }
        )
        result = _parse_analysis_result(raw)
        assert isinstance(result, AnalysisResult)
        assert result.elements[0].name == "A"
        assert result.relationships[0].relationship_type == "calls"

    def test_parse_reconciled_model(self):
        raw = json.dumps(
            {
                "elements": [
                    {
                        "element": {"name": "X", "element_type": "class", "metadata": {}},
                        "leanix_type": "Data Object",
                        "confidence": 0.8,
                        "alternative_types": [],
                        "evidence": ["stores data"],
                    }
                ],
                "relationships": [],
                "patterns": [],
                "layers": [],
                "discrepancies": ["missing docs"],
            }
        )
        result = _parse_reconciled_model(raw)
        assert isinstance(result, ReconciledModel)
        assert result.elements[0].leanix_type == "Data Object"
        assert result.discrepancies == ["missing docs"]

    def test_parse_classified_elements(self):
        raw = json.dumps(
            {
                "classified": [
                    {
                        "element": {"name": "Svc", "element_type": "service", "metadata": {}},
                        "leanix_type": "IT Component",
                        "confidence": 0.95,
                        "alternative_types": [],
                        "evidence": ["runs independently"],
                    }
                ]
            }
        )
        originals = [Element(name="Svc", element_type="service", metadata={"version": "2"})]
        result = _parse_classified_elements(raw, originals)
        assert len(result) == 1
        assert result[0].leanix_type == "IT Component"
        # Should use original element
        assert result[0].element.metadata == {"version": "2"}
