# Implementation Plan: Architectural Reverse Engineer

## Overview

Implement a web-based architectural reverse engineering tool with a Python/FastAPI backend and React frontend. The backend follows a pipeline architecture: ingestion → AI analysis → generation → serialization. Each task builds incrementally, starting with data models and core components, then wiring them together through the API and frontend.

## Tasks

- [ ] 1. Set up project structure, dependencies, and data models
  - [x] 1.1 Create project directory structure and install dependencies
    - Create `backend/`, `backend/app/`, `backend/tests/unit/`, `backend/tests/property/`, `frontend/` directories
    - Create `pyproject.toml` or `requirements.txt` with: fastapi, uvicorn, pydantic, openai, pymupdf, python-docx, graphviz, plantuml, jsonschema, hypothesis, pytest, pytest-cov
    - Create `frontend/package.json` with: react, react-dom, typescript, jest, @testing-library/react
    - _Requirements: 11.1_

  - [-] 1.2 Define all Pydantic data models and JSON Schemas
    - Create `backend/app/models.py` with all data models: SourceInput, DocumentInput, CodebaseModel, SourceFile, ModuleBoundary, PdfContent, DocumentModel, AnalysisResult, Element, Relationship, ClassifiedElement, ReconciledModel, LeanIXMapping, LeanIXReport, DiagramOutput, ADR, StructuredOutput, ValidationResult
    - Create JSON Schema files in `backend/schemas/` for each structured output type
    - _Requirements: 1.5, 2.1, 3.4, 4.4, 9.2, 12.1, 12.4_

  - [~] 1.3 Write property test for JSON serialization round-trip
    - **Property 19: JSON serialization round-trip**
    - **Validates: Requirements 12.1, 12.2, 12.3**

  - [~] 1.4 Write property test for JSON Schema validation before write
    - **Property 20: JSON Schema validation before write**
    - **Validates: Requirements 12.4**

- [ ] 2. Implement Serializer and Code Ingester
  - [~] 2.1 Implement Serializer component
    - Create `backend/app/serializer.py` with `serialize()`, `deserialize()`, and `validate()` methods
    - Implement JSON Schema validation using `jsonschema` library
    - Ensure round-trip consistency for all StructuredOutput types
    - _Requirements: 12.1, 12.2, 12.3, 12.4_

  - [~] 2.2 Implement Code Ingester component
    - Create `backend/app/code_ingester.py` with `ingest(source: SourceInput) -> CodebaseModel`
    - Implement recursive file scanning for local paths with language detection
    - Implement GitHub URL cloning via `git` CLI subprocess
    - Parse file structure, module boundaries, imports/exports, and public interfaces
    - Implement error handling: InputError for invalid paths, GitError for clone failures
    - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5_

  - [~] 2.3 Write property test for recursive file discovery completeness
    - **Property 1: Recursive file discovery completeness**
    - **Validates: Requirements 1.1**

  - [~] 2.4 Write property test for invalid source input error reporting
    - **Property 2: Invalid source input error reporting**
    - **Validates: Requirements 1.3, 1.4**

  - [~] 2.5 Write property test for source file parsing completeness
    - **Property 3: Source file parsing completeness**
    - **Validates: Requirements 1.5**

- [ ] 3. Implement Document Ingester and PDF Processor
  - [~] 3.1 Implement PDF Processor component
    - Create `backend/app/pdf_processor.py` with `extract(pdf_path: str) -> PdfContent`
    - Use PyMuPDF (fitz) to extract text blocks and embedded images
    - Implement error handling: ExtractionError for corrupted/unreadable PDFs
    - _Requirements: 2.1, 2.5_

  - [~] 3.2 Implement Document Ingester component
    - Create `backend/app/document_ingester.py` with `ingest(document: DocumentInput) -> DocumentModel`
    - Implement Word document extraction using python-docx (text paragraphs and images)
    - Implement image file pass-through for PNG, JPG, SVG
    - Delegate PDF processing to PDF Processor
    - Implement error handling: UnsupportedFileError listing supported types, FileReadError for corrupted files
    - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.5_

  - [~] 3.3 Write property test for PDF text and image extraction round-trip
    - **Property 4: PDF text and image extraction round-trip**
    - **Validates: Requirements 2.1**

  - [~] 3.4 Write property test for Word document text and image extraction round-trip
    - **Property 5: Word document text and image extraction round-trip**
    - **Validates: Requirements 2.2**

  - [~] 3.5 Write property test for unsupported file type error
    - **Property 6: Unsupported file type error includes supported types list**
    - **Validates: Requirements 2.4**

- [~] 4. Checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [ ] 5. Implement AI Engine and LeanIX Mapper
  - [~] 5.1 Implement AI Engine component
    - Create `backend/app/ai_engine.py` with `analyze_code()`, `analyze_document()`, `reconcile()`, and `classify_elements()` methods
    - Integrate OpenAI API client for GPT-4 text and vision analysis
    - Implement prompt templates for code analysis, document/diagram analysis, reconciliation, and LeanIX classification
    - Implement confidence scoring for element classification
    - Implement error handling: AIServiceError with retry guidance for rate limits, timeouts, auth failures
    - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5_

  - [~] 5.2 Implement LeanIX Mapper component
    - Create `backend/app/leanix_mapper.py` with `map(elements: list[ClassifiedElement]) -> LeanIXReport`
    - Map classified elements to LeanIX object types with confidence scores
    - Include relationship mappings between LeanIX objects
    - Rank multiple applicable types by confidence score in descending order
    - _Requirements: 9.1, 9.2, 9.3, 9.4_

  - [~] 5.3 Write property test for LeanIX classification validity
    - **Property 7: LeanIX classification validity**
    - **Validates: Requirements 3.4, 3.5, 9.1**

  - [~] 5.4 Write property test for LeanIX mapping report completeness
    - **Property 17: LeanIX mapping report completeness**
    - **Validates: Requirements 9.2, 9.3, 9.4**

- [ ] 6. Implement Diagram Generator
  - [~] 6.1 Implement dependency graph generation
    - Create `backend/app/diagram_generator.py` with `generate_dependency_graph(analysis: ReconciledModel) -> DiagramOutput`
    - Use Graphviz to render dependency graphs as PNG/SVG
    - Produce structured JSON data with nodes and directed edges
    - Implement circular dependency detection and visual highlighting
    - _Requirements: 4.1, 4.2, 4.3, 4.4_

  - [~] 6.2 Write property test for dependency graph structural correctness
    - **Property 8: Dependency graph structural correctness**
    - **Validates: Requirements 4.1, 4.2**

  - [~] 6.3 Write property test for circular dependency highlighting
    - **Property 9: Circular dependency highlighting**
    - **Validates: Requirements 4.3**

  - [~] 6.4 Implement component diagram generation
    - Add `generate_component_diagram(analysis: ReconciledModel) -> DiagramOutput` to diagram_generator.py
    - Label components with name, type, and LeanIX object type
    - Represent inter-component communication with labeled connectors (REST, gRPC, event, etc.)
    - Output as rendered image and structured JSON
    - _Requirements: 5.1, 5.2, 5.3, 5.4_

  - [~] 6.5 Write property test for component diagram labeling completeness
    - **Property 11: Component diagram labeling completeness**
    - **Validates: Requirements 5.1, 5.2, 5.3**

  - [~] 6.6 Implement UML diagram generation
    - Add `generate_uml_class_diagram()` and `generate_uml_sequence_diagram()` to diagram_generator.py
    - Use PlantUML for UML rendering following UML 2.5 notation
    - Output as rendered images and PlantUML source files
    - _Requirements: 6.1, 6.2, 6.3, 6.4_

  - [~] 6.7 Write property test for UML class diagram coverage
    - **Property 12: UML class diagram coverage**
    - **Validates: Requirements 6.1**

  - [~] 6.8 Write property test for UML sequence diagram coverage
    - **Property 13: UML sequence diagram coverage**
    - **Validates: Requirements 6.2**

  - [~] 6.9 Implement LLD generation
    - Add `generate_lld(component: ComponentModel) -> DiagramOutput` to diagram_generator.py
    - Show internal classes, functions, data flow, and data transformation steps as labeled nodes
    - Output as rendered image and structured JSON
    - _Requirements: 7.1, 7.2, 7.3_

  - [~] 6.10 Write property test for LLD internal structure coverage
    - **Property 14: LLD internal structure coverage**
    - **Validates: Requirements 7.1, 7.2**

  - [~] 6.11 Write property test for diagram dual output format
    - **Property 10: Diagram dual output format**
    - **Validates: Requirements 4.4, 5.4, 6.4, 7.3**

- [~] 7. Checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [ ] 8. Implement Document Generator
  - [~] 8.1 Implement ADR generation
    - Create `backend/app/document_generator.py` with `generate_adrs(analysis: ReconciledModel, existing_adrs: list[ADR] | None) -> list[ADR]`
    - Generate ADRs in Markdown format with Title, Status, Context, Decision, and Consequences sections
    - Implement deduplication against existing ADR sets
    - _Requirements: 8.1, 8.2, 8.3, 8.4_

  - [~] 8.2 Write property test for ADR structural completeness
    - **Property 15: ADR structural completeness**
    - **Validates: Requirements 8.1, 8.2, 8.3**

  - [~] 8.3 Write property test for ADR deduplication against existing set
    - **Property 16: ADR deduplication against existing set**
    - **Validates: Requirements 8.4**

  - [~] 8.4 Implement Markdown documentation generation
    - Add `generate_markdown(analysis: ReconciledModel, diagrams: list[DiagramOutput]) -> str` to document_generator.py
    - Include system overview, component descriptions, dependency summary, and interface catalog sections
    - Generate table of contents with links to each section
    - Embed or link all generated diagrams
    - Format for GitHub/standard Markdown renderer compatibility
    - _Requirements: 10.1, 10.2, 10.3, 10.4_

  - [~] 8.5 Write property test for Markdown documentation section completeness
    - **Property 18: Markdown documentation section completeness**
    - **Validates: Requirements 10.1, 10.2, 10.3**

- [ ] 9. Implement FastAPI REST API
  - [~] 9.1 Create API endpoints and pipeline orchestration
    - Create `backend/app/api.py` with FastAPI application
    - Implement `POST /analyze` endpoint: accept SourceInput and DocumentInput lists, trigger pipeline, return job ID
    - Implement `GET /status/{job_id}` endpoint: return current analysis stage
    - Implement `GET /results/{job_id}` endpoint: return all generated outputs
    - Implement `GET /download/{job_id}/{artifact}` endpoint: download specific output files
    - Wire together all pipeline components: Code Ingester → Document Ingester → AI Engine → LeanIX Mapper → Diagram Generator → Document Generator → Serializer
    - Implement typed error hierarchy (AnalyzerError base class) with structured JSON error responses
    - Collect non-fatal errors and report alongside partial results
    - _Requirements: 1.1, 1.2, 2.1, 2.2, 2.3, 3.1, 3.2, 3.3, 4.1, 5.1, 6.1, 7.1, 8.1, 9.1, 10.1, 11.1, 12.1_

  - [~] 9.2 Write unit tests for API endpoints
    - Test success and error responses for each endpoint
    - Test progress reporting via status endpoint
    - Test error propagation from pipeline components
    - _Requirements: 11.3, 11.6_

- [ ] 10. Implement React Frontend
  - [~] 10.1 Create frontend project and input components
    - Set up React + TypeScript project with Create React App or Vite
    - Create input fields for local folder paths and GitHub URLs
    - Create file upload controls for PDF, Word, and image files
    - Create "Analyze" trigger button
    - _Requirements: 11.1, 11.2_

  - [~] 10.2 Implement progress display and results view
    - Create progress indicator component showing current analysis stage (polls `GET /status/{job_id}`)
    - Create navigable results layout displaying all generated diagrams and documents
    - Create download controls for all output types (images, JSON, Markdown, PlantUML)
    - Implement error message display for analysis failures
    - _Requirements: 11.3, 11.4, 11.5, 11.6_

  - [~] 10.3 Write frontend component tests
    - Test input field rendering and validation
    - Test progress indicator state changes
    - Test results display and download controls
    - Test error message display
    - _Requirements: 11.1, 11.2, 11.3, 11.4, 11.5, 11.6_

- [~] 11. Final checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP
- Each task references specific requirements for traceability
- Checkpoints ensure incremental validation
- Property tests use Hypothesis and validate universal correctness properties from the design document
- Unit tests validate specific examples and edge cases
- The OpenAI API calls in the AI Engine should be mocked in tests using unittest.mock
