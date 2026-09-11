# Requirements Document

## Introduction

The Architectural Reverse Engineer project has accumulated code duplication and unnecessary complexity across its backend modules. This refactoring effort applies KISS (Keep It Simple, Stupid) and DRY (Don't Repeat Yourself) principles to eliminate duplicated logic, simplify overly complex abstractions, and extract shared patterns into reusable utilities. The refactoring preserves all existing functionality, public API interfaces, and test compatibility.

## Glossary

- **Parser_Registry**: A registry mapping language identifier strings to callable parser functions, replacing the ad-hoc `_PARSERS` dict with a typed, authoritative lookup
- **Ingestion_Wrapper**: A shared error-handling decorator or context manager that standardizes file ingestion error handling across document types (PDF, Word, image)
- **Diagram_Renderer**: A unified rendering abstraction that encapsulates the common pattern of building structured data, rendering via Graphviz or PlantUML, and wrapping results in DiagramOutput
- **ADR_Template_Registry**: A single consolidated mapping from source keys (patterns, layers, element types) to ADR template data, replacing three separate mapping dictionaries with identical value structure
- **Pipeline_Stage_Runner**: A utility that encapsulates the repeated try/except/append-to-non-fatal pattern used across all pipeline stages in the API orchestrator
- **AI_Response_Parser**: A shared utility for extracting JSON from AI responses and constructing Element and Relationship lists, eliminating duplicated construction logic across parse functions
- **Code_Ingester**: The module responsible for scanning local paths or cloning GitHub repositories and parsing source files
- **Document_Ingester**: The module responsible for extracting content from PDF, Word, and image files
- **Diagram_Generator**: The module responsible for producing visual architectural diagrams
- **Document_Generator**: The module responsible for producing ADRs and Markdown documentation
- **API_Orchestrator**: The FastAPI REST API module that orchestrates the full analysis pipeline
- **Serializer**: The module responsible for JSON serialization, deserialization, and schema validation

## Requirements

### Requirement 1: Consolidate Language-Specific Parsers into a Registry

**User Story:** As a developer, I want language-specific parsing logic consolidated into a registry-based lookup, so that adding new language support requires only registering a callable rather than modifying dispatch logic.

#### Acceptance Criteria

1. THE Parser_Registry SHALL map language identifier strings to callable parser functions, replacing the current `_PARSERS` dict and separate per-language function definitions with a single authoritative registry
2. THE Code_Ingester SHALL use a single dispatch function that accepts a language key and file content, looks up the corresponding callable in the Parser_Registry, and invokes it
3. WHEN a language has no entry in the Parser_Registry, THE Code_Ingester SHALL return empty lists for imports, exports, and public interfaces
4. FOR ALL supported languages (Python, JavaScript, TypeScript, Java), THE Code_Ingester SHALL produce identical parsing results before and after the refactoring
5. THE Parser_Registry SHALL support adding a new language by registering a single callable entry without modifying the dispatch function
6. THE Parser_Registry SHALL allow parser callables to use stateful logic (e.g., Python's `__all__`-conditional export behavior) and language-specific line matching (e.g., whitespace-sensitive vs whitespace-insensitive checks), since these behaviors cannot be captured by pure regex configuration

### Requirement 2: Unify Document Ingestion Error Handling

**User Story:** As a developer, I want document ingestion functions to share a common error-handling pattern, so that error reporting is consistent and new document types can be added without duplicating error-handling boilerplate.

#### Acceptance Criteria

1. THE Ingestion_Wrapper SHALL provide a reusable mechanism (decorator, context manager, or wrapper function) that catches exceptions during file ingestion and raises FileReadError with a consistent detail structure containing file_path and reason
2. WHEN a PDF file ingestion fails, THE Document_Ingester SHALL raise a FileReadError with the same detail structure as when a Word document or image ingestion fails
3. WHEN a new document type handler is added, THE Document_Ingester SHALL require only the handler function and the Ingestion_Wrapper to produce consistent error handling
4. FOR ALL supported document types (PDF, Word, image), THE Document_Ingester SHALL produce identical ingestion results and error behavior before and after the refactoring

### Requirement 3: Extract Shared Diagram Rendering Logic

**User Story:** As a developer, I want diagram rendering logic consolidated into a shared abstraction, so that each diagram type only defines its unique data-building and graph-construction logic.

#### Acceptance Criteria

1. THE Diagram_Renderer SHALL encapsulate the common pattern of: building structured data, rendering via Graphviz or PlantUML, catching render exceptions, and wrapping results in a DiagramOutput
2. WHEN generating a dependency graph, THE Diagram_Generator SHALL delegate rendering to the Diagram_Renderer, providing only the graph-specific node and edge construction logic
3. WHEN generating a component diagram, THE Diagram_Generator SHALL delegate rendering to the Diagram_Renderer, providing only the component-specific node and edge construction logic
4. WHEN generating a UML class diagram, THE Diagram_Generator SHALL delegate PlantUML source construction and rendering to the Diagram_Renderer
5. WHEN generating a UML sequence diagram, THE Diagram_Generator SHALL delegate PlantUML source construction and rendering to the Diagram_Renderer
6. FOR ALL diagram types, THE Diagram_Generator SHALL produce identical DiagramOutput results (structured_data, rendered_image, source_file) before and after the refactoring

### Requirement 4: Consolidate ADR Template Mappings

**User Story:** As a developer, I want the three separate ADR mapping dictionaries merged into a single registry, so that ADR template data is defined once and the generation loop is not repeated.

#### Acceptance Criteria

1. THE ADR_Template_Registry SHALL store all ADR templates in a single data structure, with each entry keyed by a source category (pattern, layer, or element_type) and a match key
2. THE Document_Generator SHALL use a single loop over the ADR_Template_Registry to generate ADR candidates from patterns, layers, and element types
3. FOR ALL inputs, THE Document_Generator SHALL produce identical ADR output (same titles, content, deduplication behavior) before and after the refactoring
4. THE ADR_Template_Registry SHALL support adding a new ADR template by adding a single entry without modifying the generation loop

### Requirement 5: Simplify Pipeline Orchestration Error Collection

**User Story:** As a developer, I want the repeated try/except/append-to-non-fatal pattern in the pipeline orchestrator extracted into reusable utilities, so that each pipeline stage is expressed concisely.

#### Acceptance Criteria

1. THE Pipeline_Stage_Runner SHALL provide a reusable mechanism that executes a callable, catches AnalyzerError exceptions, and appends structured error details to a shared error collection list
2. THE Pipeline_Stage_Runner SHALL provide a list-mapping variant that iterates over a collection of items, applies a callable to each item individually, catches AnalyzerError per item, appends errors to the shared error list, and returns the list of successful results
3. THE API_Orchestrator SHALL use the Pipeline_Stage_Runner for all pipeline stages (ingestion, analysis, reconciliation, generation, serialization) instead of inline try/except blocks
4. FOR ALL pipeline execution scenarios (success, partial failure, complete failure), THE API_Orchestrator SHALL produce identical job results, error lists, and stage transitions before and after the refactoring

### Requirement 6: Deduplicate AI Response Parsing Logic

**User Story:** As a developer, I want the shared JSON extraction and element/relationship construction logic extracted into reusable helpers, so that each AI response parser only defines its unique mapping logic.

#### Acceptance Criteria

1. THE AI_Response_Parser SHALL provide a shared helper that extracts a list of Element objects from a parsed JSON dictionary using a consistent field mapping
2. THE AI_Response_Parser SHALL provide a shared helper that extracts a list of Relationship objects from a parsed JSON dictionary using a consistent field mapping
3. WHEN parsing an analysis result, a reconciled model, or classified elements, THE AI_Engine SHALL use the shared helpers for Element and Relationship construction
4. FOR ALL AI response formats, THE AI_Engine SHALL produce identical parsed results before and after the refactoring

### Requirement 7: Simplify Serializer Byte-Field Handling

**User Story:** As a developer, I want the serializer's byte-field detection to handle arbitrarily nested structures, so that the shallow-plus-one-level check is replaced with a consistent recursive approach.

#### Acceptance Criteria

1. THE Serializer SHALL detect bytes fields at any nesting depth (not just shallow and one level of list nesting) when deciding whether to apply base64 encoding
2. FOR ALL Pydantic models containing bytes fields at any nesting depth, THE Serializer SHALL correctly base64-encode those fields during serialization
3. FOR ALL valid StructuredOutput instances, serializing to JSON then deserializing back SHALL produce an equivalent data structure (round-trip property preserved)

### Requirement 8: Eliminate Redundant Reachability Checks in Cycle Detection

**User Story:** As a developer, I want the cycle detection logic in the diagram generator simplified to avoid redundant graph traversals, so that the code is easier to understand and maintain.

#### Acceptance Criteria

1. THE Diagram_Generator SHALL determine cycle membership (nodes and edges on cycles) without performing redundant reachability checks that duplicate work already done during DFS-based cycle detection
2. WHEN circular dependencies are detected, THE Diagram_Generator SHALL produce the same set of highlighted cycle nodes and cycle edges as the current implementation
3. FOR ALL dependency graphs (acyclic, single cycle, multiple overlapping cycles), THE Diagram_Generator SHALL produce identical cycle detection results before and after the refactoring

### Requirement 9: Preserve Public API Interfaces

**User Story:** As a developer, I want all public function signatures and module-level interfaces to remain unchanged, so that existing tests and consumers continue to work without modification.

#### Acceptance Criteria

1. THE Code_Ingester SHALL maintain the same public function signature: `ingest(source: SourceInput) -> CodebaseModel`
2. THE Document_Ingester SHALL maintain the same public function signature: `ingest(document: DocumentInput) -> DocumentModel`
3. THE Diagram_Generator SHALL maintain the same public function signatures for all five diagram generation functions
4. THE Document_Generator SHALL maintain the same public function signatures for `generate_adrs()`, `adr_to_markdown()`, and `generate_markdown()`
5. THE Serializer SHALL maintain the same public function signatures for `serialize()`, `deserialize()`, and `validate()`
6. THE API_Orchestrator SHALL maintain the same HTTP endpoint signatures and response schemas
7. THE AI_Engine SHALL maintain the same public method signatures for `analyze_code()`, `analyze_document()`, `reconcile()`, and `classify_elements()`
