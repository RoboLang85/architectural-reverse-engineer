"""FastAPI REST API for the Architectural Reverse Engineer.

Exposes HTTP endpoints for triggering analysis, checking status,
retrieving results, and downloading specific artifacts.  Orchestrates
the full pipeline: Code Ingester → Document Ingester → AI Engine →
LeanIX Mapper → Diagram Generator → Document Generator → Serializer.
"""

from __future__ import annotations

import uuid
from enum import Enum
from typing import Any

from fastapi import BackgroundTasks, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel, Field

from app.errors import AnalyzerError
from app.models import DocumentInput, SourceInput

# ---------------------------------------------------------------------------
# Job state management
# ---------------------------------------------------------------------------


class JobStage(str, Enum):
    """Pipeline stages for progress reporting."""

    queued = "queued"
    ingesting = "ingesting"
    analyzing = "analyzing"
    generating = "generating"
    serializing = "serializing"
    complete = "complete"
    failed = "failed"


class JobState(BaseModel):
    """In-memory representation of a running/completed job."""

    job_id: str
    stage: JobStage = JobStage.queued
    results: dict[str, Any] = Field(default_factory=dict)
    errors: list[dict[str, Any]] = Field(default_factory=list)
    artifacts: dict[str, bytes] = Field(default_factory=dict)


# In-memory job store  (job_id → JobState)
_jobs: dict[str, JobState] = {}


# ---------------------------------------------------------------------------
# Request / Response schemas
# ---------------------------------------------------------------------------


class AnalyzeRequest(BaseModel):
    """Request body for POST /analyze."""

    sources: list[SourceInput] = Field(default_factory=list)
    documents: list[DocumentInput] = Field(default_factory=list)


class AnalyzeResponse(BaseModel):
    """Response body for POST /analyze."""

    job_id: str


class StatusResponse(BaseModel):
    """Response body for GET /status/{job_id}."""

    job_id: str
    stage: str


class ErrorDetail(BaseModel):
    """Structured error detail returned in JSON error responses."""

    error_type: str
    message: str
    details: dict[str, Any] = Field(default_factory=dict)



# ---------------------------------------------------------------------------
# Pipeline orchestration
# ---------------------------------------------------------------------------


def _run_pipeline(job_id: str, sources: list[SourceInput], documents: list[DocumentInput]) -> None:
    """Execute the full analysis pipeline in the background.

    Stages:
    1. Ingestion  – Code Ingester + Document Ingester
    2. Analysis   – AI Engine (analyze, reconcile, classify)
    3. Generation – LeanIX Mapper, Diagram Generator, Document Generator
    4. Serialization – Serializer
    """
    from app import code_ingester, document_ingester, serializer
    from app.ai_engine import AIEngine
    from app import diagram_generator, document_generator, leanix_mapper
    from app.models import (
        AnalysisResult,
        CodebaseModel,
        DocumentModel,
        ReconciledModel,
    )

    job = _jobs[job_id]
    non_fatal: list[dict[str, Any]] = []

    try:
        # ---- Stage 1: Ingestion ----
        job.stage = JobStage.ingesting

        codebase_models: list[CodebaseModel] = []
        for src in sources:
            try:
                codebase_models.append(code_ingester.ingest(src))
            except AnalyzerError as exc:
                non_fatal.append(_error_to_dict(exc))

        document_models: list[DocumentModel] = []
        for doc in documents:
            try:
                document_models.append(document_ingester.ingest(doc))
            except AnalyzerError as exc:
                non_fatal.append(_error_to_dict(exc))

        # ---- Stage 2: Analysis ----
        job.stage = JobStage.analyzing

        ai = AIEngine()

        code_analyses: list[AnalysisResult] = []
        for cb in codebase_models:
            try:
                code_analyses.append(ai.analyze_code(cb))
            except AnalyzerError as exc:
                non_fatal.append(_error_to_dict(exc))

        doc_analyses: list[AnalysisResult] = []
        for dm in document_models:
            try:
                doc_analyses.append(ai.analyze_document(dm))
            except AnalyzerError as exc:
                non_fatal.append(_error_to_dict(exc))

        # Merge code analyses into one
        merged_code = _merge_analyses(code_analyses)
        merged_doc = _merge_analyses(doc_analyses)

        # Reconcile
        try:
            reconciled: ReconciledModel = ai.reconcile(merged_code, merged_doc)
        except AnalyzerError as exc:
            non_fatal.append(_error_to_dict(exc))
            # Build a minimal reconciled model from what we have
            reconciled = ReconciledModel(
                elements=[],
                relationships=[],
                patterns=merged_code.patterns + merged_doc.patterns,
                layers=merged_code.layers + merged_doc.layers,
                discrepancies=[],
            )

        # ---- Stage 3: Generation ----
        job.stage = JobStage.generating

        # LeanIX mapping
        try:
            leanix_report = leanix_mapper.map(reconciled.elements)
            job.results["leanix_report"] = leanix_report.model_dump()
        except AnalyzerError as exc:
            non_fatal.append(_error_to_dict(exc))

        # Diagrams
        diagram_outputs = []
        diagram_generators = [
            ("dependency_graph", diagram_generator.generate_dependency_graph),
            ("component_diagram", diagram_generator.generate_component_diagram),
            ("uml_class", diagram_generator.generate_uml_class_diagram),
            ("uml_sequence", diagram_generator.generate_uml_sequence_diagram),
        ]
        for diag_name, gen_fn in diagram_generators:
            try:
                diag = gen_fn(reconciled)
                diagram_outputs.append(diag)
                # Store rendered image as downloadable artifact
                artifact_key = f"{diag.diagram_type}.{diag.image_format}"
                job.artifacts[artifact_key] = diag.rendered_image
                # Store structured data in results
                job.results[f"{diag.diagram_type}_structured"] = diag.structured_data
            except AnalyzerError as exc:
                non_fatal.append(_error_to_dict(exc))

        # ADRs
        try:
            adrs = document_generator.generate_adrs(reconciled)
            job.results["adrs"] = [adr.model_dump() for adr in adrs]
            # Store each ADR as downloadable markdown
            for i, adr in enumerate(adrs):
                md = document_generator.adr_to_markdown(adr)
                job.artifacts[f"adr_{i}.md"] = md.encode("utf-8")
        except AnalyzerError as exc:
            non_fatal.append(_error_to_dict(exc))

        # Markdown documentation
        try:
            markdown_doc = document_generator.generate_markdown(reconciled, diagram_outputs)
            job.results["markdown"] = markdown_doc
            job.artifacts["architecture.md"] = markdown_doc.encode("utf-8")
        except AnalyzerError as exc:
            non_fatal.append(_error_to_dict(exc))

        # ---- Stage 4: Serialization ----
        job.stage = JobStage.serializing

        try:
            serialized_results: dict[str, str] = {}
            for key, value in job.results.items():
                if isinstance(value, dict):
                    from app.models import StructuredOutput
                    so = StructuredOutput(output_type=key, data=value)
                    serialized_results[key] = serializer.serialize(so)
            job.results["serialized"] = serialized_results
        except AnalyzerError as exc:
            non_fatal.append(_error_to_dict(exc))

        # ---- Done ----
        job.errors = non_fatal
        job.stage = JobStage.complete

    except Exception as exc:
        job.errors = non_fatal + [_error_to_dict(exc)]
        job.stage = JobStage.failed


def _merge_analyses(analyses: list) -> Any:
    """Merge multiple AnalysisResult instances into one."""
    from app.models import AnalysisResult, Element, Relationship

    if not analyses:
        return AnalysisResult(elements=[], relationships=[], patterns=[], layers=[])
    if len(analyses) == 1:
        return analyses[0]

    elements: list[Element] = []
    relationships: list[Relationship] = []
    patterns: list[str] = []
    layers: list[str] = []
    for a in analyses:
        elements.extend(a.elements)
        relationships.extend(a.relationships)
        patterns.extend(a.patterns)
        layers.extend(a.layers)

    return AnalysisResult(
        elements=elements,
        relationships=relationships,
        patterns=list(dict.fromkeys(patterns)),
        layers=list(dict.fromkeys(layers)),
    )


def _error_to_dict(exc: Exception) -> dict[str, Any]:
    """Convert an exception to a structured error dict."""
    if isinstance(exc, AnalyzerError):
        return {
            "error_type": type(exc).__name__,
            "message": exc.message,
            "details": exc.details,
        }
    return {
        "error_type": type(exc).__name__,
        "message": str(exc),
        "details": {},
    }


# ---------------------------------------------------------------------------
# FastAPI application and endpoints
# ---------------------------------------------------------------------------

app = FastAPI(title="Architectural Reverse Engineer", version="0.1.0")

# Allow CORS for local development (frontend on :3000, backend on :8000)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(AnalyzerError)
async def analyzer_error_handler(request: Any, exc: AnalyzerError) -> JSONResponse:
    """Return structured JSON for any AnalyzerError."""
    return JSONResponse(
        status_code=400,
        content={
            "error_type": type(exc).__name__,
            "message": exc.message,
            "details": exc.details,
        },
    )


@app.post("/analyze", response_model=AnalyzeResponse)
async def analyze(request: AnalyzeRequest, background_tasks: BackgroundTasks) -> AnalyzeResponse:
    """Accept source and document inputs, start the analysis pipeline, return a job ID."""
    if not request.sources and not request.documents:
        raise HTTPException(
            status_code=422,
            detail={
                "error_type": "ValidationError",
                "message": "At least one source or document input is required.",
                "details": {},
            },
        )

    job_id = str(uuid.uuid4())
    _jobs[job_id] = JobState(job_id=job_id)
    background_tasks.add_task(_run_pipeline, job_id, request.sources, request.documents)
    return AnalyzeResponse(job_id=job_id)


@app.get("/status/{job_id}", response_model=StatusResponse)
async def get_status(job_id: str) -> StatusResponse:
    """Return the current analysis stage for a job."""
    job = _jobs.get(job_id)
    if job is None:
        raise HTTPException(
            status_code=404,
            detail={
                "error_type": "NotFoundError",
                "message": f"Job '{job_id}' not found.",
                "details": {"job_id": job_id},
            },
        )
    return StatusResponse(job_id=job_id, stage=job.stage.value)


@app.get("/results/{job_id}")
async def get_results(job_id: str) -> JSONResponse:
    """Return all generated outputs for a completed job."""
    job = _jobs.get(job_id)
    if job is None:
        raise HTTPException(
            status_code=404,
            detail={
                "error_type": "NotFoundError",
                "message": f"Job '{job_id}' not found.",
                "details": {"job_id": job_id},
            },
        )
    return JSONResponse(
        content={
            "job_id": job_id,
            "stage": job.stage.value,
            "results": {k: v for k, v in job.results.items() if k != "serialized"},
            "errors": job.errors,
            "available_artifacts": list(job.artifacts.keys()),
        }
    )


@app.get("/download/{job_id}/{artifact}")
async def download_artifact(job_id: str, artifact: str) -> Response:
    """Download a specific output file for a job."""
    job = _jobs.get(job_id)
    if job is None:
        raise HTTPException(
            status_code=404,
            detail={
                "error_type": "NotFoundError",
                "message": f"Job '{job_id}' not found.",
                "details": {"job_id": job_id},
            },
        )

    data = job.artifacts.get(artifact)
    if data is None:
        raise HTTPException(
            status_code=404,
            detail={
                "error_type": "NotFoundError",
                "message": f"Artifact '{artifact}' not found for job '{job_id}'.",
                "details": {"job_id": job_id, "artifact": artifact},
            },
        )

    # Determine content type
    if artifact.endswith(".png"):
        media_type = "image/png"
    elif artifact.endswith(".svg"):
        media_type = "image/svg+xml"
    elif artifact.endswith(".md"):
        media_type = "text/markdown"
    elif artifact.endswith(".json"):
        media_type = "application/json"
    else:
        media_type = "application/octet-stream"

    return Response(
        content=data,
        media_type=media_type,
        headers={"Content-Disposition": f'attachment; filename="{artifact}"'},
    )


def get_job_store() -> dict[str, JobState]:
    """Return the in-memory job store (for testing)."""
    return _jobs
