"""Unit tests for the FastAPI REST API endpoints.

Tests success and error responses for each endpoint, progress reporting
via the status endpoint, and error propagation from pipeline components.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.api import JobStage, JobState, AnalyzeRequest, app, get_job_store


@pytest.fixture(autouse=True)
def _clear_jobs():
    """Clear the in-memory job store before each test."""
    store = get_job_store()
    store.clear()
    yield
    store.clear()


@pytest.fixture
def client():
    return TestClient(app)


# ---------------------------------------------------------------------------
# POST /analyze
# ---------------------------------------------------------------------------


class TestPostAnalyze:
    """Tests for the POST /analyze endpoint."""

    def test_returns_job_id_with_source(self, client: TestClient):
        resp = client.post(
            "/analyze",
            json={"sources": [{"input_type": "local_path", "value": "/tmp/repo"}]},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "job_id" in data
        assert len(data["job_id"]) > 0

    def test_returns_job_id_with_document(self, client: TestClient):
        resp = client.post(
            "/analyze",
            json={"documents": [{"file_path": "/tmp/doc.pdf", "file_type": "pdf"}]},
        )
        assert resp.status_code == 200
        assert "job_id" in resp.json()

    def test_returns_job_id_with_both(self, client: TestClient):
        resp = client.post(
            "/analyze",
            json={
                "sources": [{"input_type": "github_url", "value": "https://github.com/user/repo"}],
                "documents": [{"file_path": "/tmp/arch.docx", "file_type": "docx"}],
            },
        )
        assert resp.status_code == 200
        assert "job_id" in resp.json()

    def test_empty_inputs_returns_422(self, client: TestClient):
        resp = client.post("/analyze", json={"sources": [], "documents": []})
        assert resp.status_code == 422
        detail = resp.json()["detail"]
        assert detail["error_type"] == "ValidationError"
        assert "At least one" in detail["message"]

    def test_no_body_fields_returns_422(self, client: TestClient):
        resp = client.post("/analyze", json={})
        assert resp.status_code == 422
        detail = resp.json()["detail"]
        assert "At least one" in detail["message"]

    def test_job_is_stored(self, client: TestClient):
        resp = client.post(
            "/analyze",
            json={"sources": [{"input_type": "local_path", "value": "/tmp/repo"}]},
        )
        job_id = resp.json()["job_id"]
        store = get_job_store()
        assert job_id in store


# ---------------------------------------------------------------------------
# GET /status/{job_id}
# ---------------------------------------------------------------------------


class TestGetStatus:
    """Tests for the GET /status/{job_id} endpoint."""

    def test_returns_stage_for_existing_job(self, client: TestClient):
        store = get_job_store()
        store["test-job-1"] = JobState(job_id="test-job-1", stage=JobStage.ingesting)

        resp = client.get("/status/test-job-1")
        assert resp.status_code == 200
        data = resp.json()
        assert data["job_id"] == "test-job-1"
        assert data["stage"] == "ingesting"

    def test_returns_404_for_unknown_job(self, client: TestClient):
        resp = client.get("/status/nonexistent-id")
        assert resp.status_code == 404
        detail = resp.json()["detail"]
        assert detail["error_type"] == "NotFoundError"

    def test_progress_through_stages(self, client: TestClient):
        """Verify that the status endpoint reflects stage transitions."""
        store = get_job_store()
        job = JobState(job_id="progress-job")
        store["progress-job"] = job

        for stage in [JobStage.queued, JobStage.ingesting, JobStage.analyzing,
                      JobStage.generating, JobStage.serializing, JobStage.complete]:
            job.stage = stage
            resp = client.get("/status/progress-job")
            assert resp.status_code == 200
            assert resp.json()["stage"] == stage.value

    def test_failed_stage(self, client: TestClient):
        store = get_job_store()
        store["fail-job"] = JobState(job_id="fail-job", stage=JobStage.failed)

        resp = client.get("/status/fail-job")
        assert resp.status_code == 200
        assert resp.json()["stage"] == "failed"


# ---------------------------------------------------------------------------
# GET /results/{job_id}
# ---------------------------------------------------------------------------


class TestGetResults:
    """Tests for the GET /results/{job_id} endpoint."""

    def test_returns_results_for_completed_job(self, client: TestClient):
        store = get_job_store()
        store["done-job"] = JobState(
            job_id="done-job",
            stage=JobStage.complete,
            results={"leanix_report": {"mappings": []}, "markdown": "# Doc"},
            errors=[],
            artifacts={"architecture.md": b"# Doc"},
        )

        resp = client.get("/results/done-job")
        assert resp.status_code == 200
        data = resp.json()
        assert data["job_id"] == "done-job"
        assert data["stage"] == "complete"
        assert "leanix_report" in data["results"]
        assert "markdown" in data["results"]
        assert "architecture.md" in data["available_artifacts"]
        assert data["errors"] == []

    def test_returns_partial_results_with_errors(self, client: TestClient):
        store = get_job_store()
        store["partial-job"] = JobState(
            job_id="partial-job",
            stage=JobStage.complete,
            results={"markdown": "# Partial"},
            errors=[{"error_type": "RenderError", "message": "Graphviz failed", "details": {}}],
        )

        resp = client.get("/results/partial-job")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["errors"]) == 1
        assert data["errors"][0]["error_type"] == "RenderError"

    def test_returns_404_for_unknown_job(self, client: TestClient):
        resp = client.get("/results/nonexistent-id")
        assert resp.status_code == 404

    def test_serialized_key_excluded_from_results(self, client: TestClient):
        store = get_job_store()
        store["ser-job"] = JobState(
            job_id="ser-job",
            stage=JobStage.complete,
            results={"markdown": "# Doc", "serialized": {"markdown": "{}"}},
        )

        resp = client.get("/results/ser-job")
        data = resp.json()
        assert "serialized" not in data["results"]
        assert "markdown" in data["results"]


# ---------------------------------------------------------------------------
# GET /download/{job_id}/{artifact}
# ---------------------------------------------------------------------------


class TestDownloadArtifact:
    """Tests for the GET /download/{job_id}/{artifact} endpoint."""

    def test_download_png_artifact(self, client: TestClient):
        store = get_job_store()
        png_data = b"\x89PNG\r\n\x1a\n" + b"\x00" * 10
        store["dl-job"] = JobState(
            job_id="dl-job",
            stage=JobStage.complete,
            artifacts={"dependency_graph.png": png_data},
        )

        resp = client.get("/download/dl-job/dependency_graph.png")
        assert resp.status_code == 200
        assert resp.headers["content-type"] == "image/png"
        assert b"PNG" in resp.content

    def test_download_md_artifact(self, client: TestClient):
        store = get_job_store()
        md_data = b"# Architecture\n\nOverview..."
        store["dl-job-md"] = JobState(
            job_id="dl-job-md",
            stage=JobStage.complete,
            artifacts={"architecture.md": md_data},
        )

        resp = client.get("/download/dl-job-md/architecture.md")
        assert resp.status_code == 200
        assert "text/markdown" in resp.headers["content-type"]
        assert b"Architecture" in resp.content

    def test_download_svg_artifact(self, client: TestClient):
        store = get_job_store()
        svg_data = b"<svg></svg>"
        store["dl-svg"] = JobState(
            job_id="dl-svg",
            stage=JobStage.complete,
            artifacts={"component.svg": svg_data},
        )

        resp = client.get("/download/dl-svg/component.svg")
        assert resp.status_code == 200
        assert resp.headers["content-type"] == "image/svg+xml"

    def test_returns_404_for_unknown_job(self, client: TestClient):
        resp = client.get("/download/nonexistent/file.png")
        assert resp.status_code == 404

    def test_returns_404_for_unknown_artifact(self, client: TestClient):
        store = get_job_store()
        store["dl-job-empty"] = JobState(
            job_id="dl-job-empty",
            stage=JobStage.complete,
            artifacts={},
        )

        resp = client.get("/download/dl-job-empty/missing.png")
        assert resp.status_code == 404
        detail = resp.json()["detail"]
        assert "missing.png" in detail["message"]

    def test_content_disposition_header(self, client: TestClient):
        store = get_job_store()
        store["dl-disp"] = JobState(
            job_id="dl-disp",
            stage=JobStage.complete,
            artifacts={"report.json": b'{"data": true}'},
        )

        resp = client.get("/download/dl-disp/report.json")
        assert resp.status_code == 200
        assert "report.json" in resp.headers.get("content-disposition", "")


# ---------------------------------------------------------------------------
# Error propagation from pipeline components
# ---------------------------------------------------------------------------


class TestErrorPropagation:
    """Tests that errors from pipeline components are properly captured."""

    def test_analyzer_error_handler(self, client: TestClient):
        """Test that AnalyzerError subclasses produce structured JSON responses."""
        from app.errors import InputError

        @app.get("/test-error-handler")
        async def _trigger_error():
            raise InputError("Test error", details={"key": "value"})

        resp = client.get("/test-error-handler")
        assert resp.status_code == 400
        data = resp.json()
        assert data["error_type"] == "InputError"
        assert data["message"] == "Test error"
        assert data["details"]["key"] == "value"

    def test_pipeline_collects_non_fatal_errors(self):
        """Verify that _run_pipeline collects non-fatal errors alongside results."""
        from app.api import _run_pipeline, _jobs, JobStage
        from app.errors import InputError

        job_id = "err-test"
        _jobs[job_id] = JobState(job_id=job_id)

        # Mock all pipeline components to simulate a non-fatal error in code ingestion
        with patch("app.code_ingester.ingest", side_effect=InputError("bad path")), \
             patch("app.document_ingester.ingest") as mock_doc, \
             patch("app.ai_engine.AIEngine") as MockAI, \
             patch("app.diagram_generator.generate_dependency_graph") as mock_dep, \
             patch("app.diagram_generator.generate_component_diagram") as mock_comp, \
             patch("app.diagram_generator.generate_uml_class_diagram") as mock_uml_c, \
             patch("app.diagram_generator.generate_uml_sequence_diagram") as mock_uml_s, \
             patch("app.document_generator.generate_adrs", return_value=[]), \
             patch("app.document_generator.generate_markdown", return_value="# Doc"), \
             patch("app.leanix_mapper.map") as mock_leanix, \
             patch("app.serializer.serialize", return_value="{}"):

            from app.models import (
                AnalysisResult, ReconciledModel, LeanIXReport,
                DiagramOutput,
            )

            # Setup AI engine mock
            ai_instance = MagicMock()
            MockAI.return_value = ai_instance
            ai_instance.analyze_code.return_value = AnalysisResult(
                elements=[], relationships=[], patterns=[], layers=[]
            )
            ai_instance.analyze_document.return_value = AnalysisResult(
                elements=[], relationships=[], patterns=[], layers=[]
            )
            ai_instance.reconcile.return_value = ReconciledModel(
                elements=[], relationships=[], patterns=[], layers=[], discrepancies=[]
            )

            mock_leanix.return_value = LeanIXReport(mappings=[])

            # Diagram mocks raise RenderError for some
            from app.errors import RenderError
            mock_dep.side_effect = RenderError("Graphviz not found")
            mock_comp.side_effect = RenderError("Graphviz not found")
            mock_uml_c.side_effect = RenderError("PlantUML not found")
            mock_uml_s.side_effect = RenderError("PlantUML not found")

            from app.models import SourceInput
            _run_pipeline(
                job_id,
                sources=[SourceInput(input_type="local_path", value="/bad/path")],
                documents=[],
            )

        job = _jobs[job_id]
        assert job.stage == JobStage.complete
        # Should have collected errors: 1 from code_ingester + 4 from diagram generators
        assert len(job.errors) >= 5
        error_types = [e["error_type"] for e in job.errors]
        assert "InputError" in error_types
        assert "RenderError" in error_types

    def test_pipeline_sets_failed_on_unexpected_error(self):
        """Verify that an unexpected exception sets the job to failed."""
        from app.api import _run_pipeline, _jobs, JobStage

        job_id = "crash-test"
        _jobs[job_id] = JobState(job_id=job_id)

        with patch("app.code_ingester.ingest", side_effect=RuntimeError("unexpected crash")):
            from app.models import SourceInput
            _run_pipeline(
                job_id,
                sources=[SourceInput(input_type="local_path", value="/tmp/x")],
                documents=[],
            )

        job = _jobs[job_id]
        assert job.stage == JobStage.failed
        assert len(job.errors) >= 1
        assert job.errors[-1]["error_type"] == "RuntimeError"
