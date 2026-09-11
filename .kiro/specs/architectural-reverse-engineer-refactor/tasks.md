# Implementation Plan: Architectural Reverse Engineer – KISS/DRY Refactoring

## Overview

Refactor the backend to eliminate code duplication and simplify complex abstractions using KISS/DRY principles. Each task is an independent, verifiable refactoring that preserves all public API signatures and existing test compatibility. Tasks are ordered so foundational/isolated changes come first, with checkpoints after each major module change.

## Tasks

- [x] 1. Refactor AI Response Parser helpers in `ai_engine.py`
  - [x] 1.1 Extract `_extract_elements` and `_extract_relationships` shared helpers
    - Add `_extract_elements(items: list[dict]) -> list[Element]` that constructs Element objects from parsed JSON dicts
    - Add `_extract_relationships(items: list[dict]) -> list[Relationship]` that constructs Relationship objects from parsed JSON dicts
    - Replace duplicated list comprehensions in `_parse_analysis_result`, `_parse_reconciled_model`, and `_parse_classified_elements` with calls to these helpers
    - Preserve all existing behavior: confidence thresholds, fallback to original elements, unclassified handling
    - _Requirements: 6.1, 6.2, 6.3, 6.4, 9.7_

  - [ ]* 1.2 Write property test for AI response parsing equivalence
    - **Property 7: AI response parsing equivalence**
    - Generate random valid AI response JSON dicts and verify refactored parse functions produce identical results
    - Create `backend/tests/property/test_ai_parse_equivalence_props.py`
    - **Validates: Requirements 6.4**

- [x] 2. Refactor recursive byte-field detection in `serializer.py`
  - [x] 2.1 Implement `_value_contains_bytes` recursive helper
    - Add `_value_contains_bytes(obj: Any) -> bool` that recursively checks for bytes in dicts, lists, tuples, and nested BaseModel instances
    - Refactor `_has_bytes_fields` to delegate to `_value_contains_bytes(model.__dict__)`
    - Preserve `serialize()`, `deserialize()`, and `validate()` public signatures unchanged
    - _Requirements: 7.1, 7.2, 9.5_

  - [ ]* 2.2 Write property test for nested bytes serialization
    - **Property 8: Nested bytes serialization correctness**
    - Generate random Pydantic model instances with bytes at arbitrary nesting depths and verify serialization produces valid base64 JSON
    - Create `backend/tests/property/test_serializer_props.py` (or extend existing `backend/tests/property/test_serialization_props.py`)
    - **Validates: Requirements 7.1, 7.2**

  - [ ]* 2.3 Write property test for serialization round-trip
    - **Property 9: Serialization round-trip**
    - Generate random StructuredOutput instances (including nested bytes) and verify `deserialize(serialize(x))` produces equivalent data
    - Add to `backend/tests/property/test_serializer_props.py`
    - **Validates: Requirements 7.3**

- [x] 3. Checkpoint – Verify isolated helper refactorings
  - Ensure all existing tests pass after AI engine and serializer changes, ask the user if questions arise.

- [x] 4. Consolidate language-specific parsers in `code_ingester.py`
  - [x] 4.1 Create typed `_PARSER_REGISTRY` with callable parser functions
    - Define `ParserFn = Callable[[str], tuple[list[str], list[str], list[str]]]` type alias
    - Build `_PARSER_REGISTRY: dict[str, ParserFn]` with entries for Python, JavaScript, TypeScript, and Java, mapping to the existing `_parse_python`, `_parse_js_ts`, and `_parse_java` callables
    - Refactor `_parse_file` to look up the registry and return `([], [], [])` when no entry exists, removing the fallback to `_parse_generic`
    - Remove `_parse_generic` function entirely (its behavior is now inline in `_parse_file`)
    - Remove the old untyped `_PARSERS: dict[str, object]` dict
    - Preserve all existing parser functions unchanged (they retain their stateful logic: Python's `__all__` check, Java's `;` stripping, JS/TS substring matching)
    - Preserve `ingest(source: SourceInput) -> CodebaseModel` public signature unchanged
    - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5, 1.6, 9.1_

  - [ ]* 4.2 Write property test for parser behavioral equivalence
    - **Property 1: Parser behavioral equivalence for supported languages**
    - Generate random source file content per language and compare old vs new parser output
    - Create `backend/tests/property/test_parser_equivalence_props.py`
    - **Validates: Requirements 1.4**

  - [ ]* 4.3 Write property test for unsupported language fallback
    - **Property 2: Unsupported language returns empty results**
    - Generate random non-registry language strings and verify empty results
    - Add to `backend/tests/property/test_parser_equivalence_props.py`
    - **Validates: Requirements 1.3**

- [x] 5. Unify document ingestion error handling in `document_ingester.py`
  - [x] 5.1 Implement `_safe_ingest` wrapper function
    - Add `_safe_ingest(fn, file_path, *args) -> DocumentModel` that catches exceptions and raises `FileReadError` with consistent `{file_path, reason}` detail structure
    - Refactor `_ingest_pdf`, `_ingest_docx`, `_ingest_image` to focus only on extraction logic, removing their individual try/except blocks
    - Wire `ingest()` to call each handler through `_safe_ingest`
    - Preserve `ingest(document: DocumentInput) -> DocumentModel` public signature unchanged
    - _Requirements: 2.1, 2.2, 2.3, 2.4, 9.2_

  - [ ]* 5.2 Write property test for document ingestion equivalence
    - **Property 3: Document ingestion behavioral equivalence**
    - Generate random DocumentInput with valid/invalid paths and compare ingestion output/errors
    - Create `backend/tests/property/test_ingestion_equivalence_props.py`
    - **Validates: Requirements 2.2, 2.4**

- [x] 6. Checkpoint – Verify ingester refactorings
  - Ensure all existing tests pass after code_ingester and document_ingester changes, ask the user if questions arise.

- [x] 7. Extract shared diagram rendering helpers in `diagram_generator.py`
  - [x] 7.1 Implement `_render_graphviz_diagram` and `_render_plantuml_diagram` helpers
    - Add `_render_graphviz_diagram(dot, diagram_type, image_format, structured_data) -> DiagramOutput` that calls `dot.pipe()`, catches exceptions as `RenderError`, and wraps in `DiagramOutput`
    - Add `_render_plantuml_diagram(source, diagram_type, image_format, structured_data) -> DiagramOutput` that calls `_render_plantuml()`, catches exceptions, and wraps in `DiagramOutput`
    - Refactor `generate_dependency_graph`, `generate_component_diagram`, and `generate_lld` to build their Graphviz graph then delegate to `_render_graphviz_diagram`
    - Refactor `generate_uml_class_diagram` and `generate_uml_sequence_diagram` to build PlantUML source then delegate to `_render_plantuml_diagram`
    - Preserve all five public function signatures unchanged
    - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5, 3.6, 9.3_

  - [ ]* 7.2 Write property test for diagram structured data equivalence
    - **Property 4: Diagram structured data equivalence**
    - Generate random ReconciledModel instances and compare structured_data from diagram generators before/after
    - Create `backend/tests/property/test_diagram_equivalence_props.py`
    - **Validates: Requirements 3.6**

- [x] 8. Simplify cycle detection in `diagram_generator.py`
  - [x] 8.1 Replace `_can_reach` and `_cycle_edges_and_nodes` with SCC-based approach
    - Implement Tarjan's SCC algorithm (or enhanced DFS) that collects cycle nodes directly during traversal
    - Derive cycle edges as edges where both endpoints are in the same SCC of size > 1
    - Remove `_can_reach` function entirely
    - Replace `_cycle_edges_and_nodes` with the new implementation
    - Ensure `generate_dependency_graph` produces identical cycle_nodes and cycle_edges sets
    - _Requirements: 8.1, 8.2, 8.3_

  - [ ]* 8.2 Write property test for cycle detection equivalence
    - **Property 10: Cycle detection equivalence**
    - Retain a copy of the original `_can_reach` and `_cycle_edges_and_nodes` functions in the test file as a reference oracle
    - Generate random directed graphs and compare cycle detection outputs (nodes and edges) from the oracle vs the new SCC-based implementation
    - Create `backend/tests/property/test_cycle_detection_props.py`
    - **Validates: Requirements 8.2, 8.3**

- [x] 9. Checkpoint – Verify diagram generator refactorings
  - Ensure all existing tests pass after diagram rendering and cycle detection changes, ask the user if questions arise.

- [x] 10. Consolidate ADR template mappings in `document_generator.py`
  - [x] 10.1 Merge three ADR dicts into `_ADR_TEMPLATE_REGISTRY`
    - Create `_ADR_TEMPLATE_REGISTRY: dict[tuple[str, str], dict[str, str]]` combining all entries from `_PATTERN_ADR_MAP`, `_ELEMENT_TYPE_ADR_MAP`, and `_LAYER_ADR_MAP`
    - Refactor `generate_adrs` to use a single loop over `(category, source_values)` pairs instead of three separate loops
    - For `"pattern"` and `"layer"` categories: use substring matching (`key in value_lower`) with `break` on first match per source value
    - For `"element_type"` category: use exact key matching (`value_lower == key`) with deduplication via `seen_element_types` set (matching current behavior)
    - Remove the three separate mapping dicts
    - Preserve `generate_adrs()`, `adr_to_markdown()`, and `generate_markdown()` public signatures unchanged
    - _Requirements: 4.1, 4.2, 4.3, 4.4, 9.4_

  - [ ]* 10.2 Write property test for ADR generation equivalence
    - **Property 5: ADR generation equivalence**
    - Generate random ReconciledModel with patterns/layers/elements and compare ADR output before/after
    - Create `backend/tests/property/test_adr_equivalence_props.py`
    - **Validates: Requirements 4.3**

- [x] 11. Simplify pipeline orchestration in `api.py`
  - [x] 11.1 Extract `_run_stage` and `_run_stage_map` helpers and refactor `_run_pipeline`
    - Add `_run_stage(fn, non_fatal, default=None)` that executes a callable, catches `AnalyzerError`, appends to error list, and returns default on failure
    - Add `_run_stage_map(items, fn, non_fatal)` that iterates over items, applies fn to each, catches `AnalyzerError` per item, appends errors, and returns list of successful results
    - Replace all inline try/except blocks in `_run_pipeline`: use `_run_stage_map` for list-iteration stages (source ingestion, document ingestion, code analysis, document analysis, diagram generation) and `_run_stage` for single-callable stages (reconciliation, ADR generation, markdown generation, serialization)
    - Preserve all HTTP endpoint signatures and response schemas unchanged
    - _Requirements: 5.1, 5.2, 5.3, 5.4, 9.6_

  - [ ]* 11.2 Write property test for pipeline stage runner
    - **Property 6: Pipeline stage runner error collection**
    - Generate random callables (success/AnalyzerError) and verify `_run_stage` behavior (return value, error list mutation)
    - Generate random lists of items with mixed success/failure callables and verify `_run_stage_map` returns correct results list and error list
    - Create `backend/tests/property/test_pipeline_runner_props.py`
    - **Validates: Requirements 5.1, 5.2**

- [x] 12. Checkpoint – Verify document generator and API refactorings
  - Ensure all existing tests pass after ADR registry and pipeline runner changes, ask the user if questions arise.

- [x] 13. Verify public API signature preservation
  - [x] 13.1 Add public API signature smoke tests
    - Create `backend/tests/unit/test_api_signatures.py`
    - Use `inspect.signature` to verify all public function signatures match the originals specified in Requirement 9
    - Cover: `code_ingester.ingest`, `document_ingester.ingest`, all five diagram generator functions, `document_generator.generate_adrs/adr_to_markdown/generate_markdown`, `serializer.serialize/deserialize/validate`, `AIEngine.analyze_code/analyze_document/reconcile/classify_elements`
    - Verify API endpoint routes and methods are unchanged
    - _Requirements: 9.1, 9.2, 9.3, 9.4, 9.5, 9.6, 9.7_

- [x] 14. Final checkpoint – Full test suite verification
  - Ensure all existing and new tests pass, ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP
- Each task references specific requirements for traceability
- Checkpoints ensure incremental validation after each major module change
- Property tests validate universal correctness properties from the design document
- The design uses Python throughout — all implementation is in Python
- All refactorings are internal; no public API changes
