# Requirements Document

## Introduction

The Architectural Reverse Engineer is a tool that analyzes existing codebases and architectural diagrams to produce updated, comprehensive architectural documentation. It targets architects responsible for maintaining and updating documentation for software systems. The tool ingests source code (via local paths or GitHub URLs) and existing diagrams/documents (images, PDFs, Word files), then uses AI to generate dependency graphs, design diagrams, architectural decision records, component diagrams, UML, and structured outputs aligned with LeanIX object types (Organizations, Interfaces, Data Objects, IT Components, etc.).

## Glossary

- **Analyzer**: The core backend service responsible for parsing and interpreting codebases and documents
- **Diagram_Generator**: The subsystem that produces visual architectural diagrams (dependency graphs, component diagrams, UML, lower-level design diagrams)
- **Document_Generator**: The subsystem that produces textual architectural documentation (ADRs, markdown documents)
- **AI_Engine**: The subsystem that interfaces with the OpenAI API to perform intelligent analysis, classification, and generation
- **PDF_Processor**: The subsystem that extracts text and images from PDF files using PyMuPDF or similar libraries
- **LeanIX_Mapper**: The subsystem that identifies and classifies discovered elements into LeanIX object types (Organizations, Interfaces, Data Objects, IT Components)
- **Source_Input**: A local folder path or GitHub URL pointing to a codebase to be analyzed
- **Document_Input**: An existing architectural document or diagram file (PDF, Word, image) provided for analysis
- **ADR**: Architectural Decision Record — a document capturing a significant architectural decision, its context, and consequences
- **Dependency_Graph**: A visual representation of dependencies between modules, packages, or services in a codebase
- **Component_Diagram**: A diagram showing the structural components of a system and their relationships
- **UML_Diagram**: A Unified Modeling Language diagram representing system structure or behavior
- **LLD**: Lower Level Design diagram — a detailed design diagram showing internal logic and data flow within components

## Requirements

### Requirement 1: Codebase Ingestion

**User Story:** As an architect, I want to provide a local folder path or GitHub URL so that the tool can analyze the codebase for architectural patterns.

#### Acceptance Criteria

1. WHEN a valid local folder path is provided, THE Analyzer SHALL recursively scan the folder and identify all source code files
2. WHEN a valid GitHub URL is provided, THE Analyzer SHALL clone or fetch the repository and identify all source code files
3. IF an invalid local folder path is provided, THEN THE Analyzer SHALL return a descriptive error indicating the path is invalid or inaccessible
4. IF an invalid GitHub URL is provided, THEN THE Analyzer SHALL return a descriptive error indicating the URL is unreachable or malformed
5. WHEN source code files are identified, THE Analyzer SHALL parse file structure, module boundaries, import/export relationships, and public interfaces

### Requirement 2: Document and Diagram Ingestion

**User Story:** As an architect, I want to upload existing architectural documents and diagrams so that the tool can incorporate them into its analysis.

#### Acceptance Criteria

1. WHEN a PDF file is provided, THE PDF_Processor SHALL extract text content and embedded images from the file
2. WHEN a Word document (.docx) is provided, THE Analyzer SHALL extract text content and embedded images from the document
3. WHEN an image file (PNG, JPG, SVG) is provided, THE AI_Engine SHALL analyze the image to identify architectural elements and relationships
4. IF an unsupported file type is provided, THEN THE Analyzer SHALL return a descriptive error listing the supported file types
5. IF a provided file is corrupted or unreadable, THEN THE Analyzer SHALL return a descriptive error identifying the problematic file

### Requirement 3: AI-Powered Architectural Analysis

**User Story:** As an architect, I want the tool to use AI to understand the codebase and existing documentation so that it can produce accurate architectural representations.

#### Acceptance Criteria

1. WHEN source code files have been parsed, THE AI_Engine SHALL identify architectural patterns, layers, and component boundaries
2. WHEN existing diagrams have been ingested, THE AI_Engine SHALL extract entities, relationships, and annotations from the diagrams
3. WHEN both code and existing documents are available, THE AI_Engine SHALL reconcile differences between the code structure and the documented architecture
4. THE AI_Engine SHALL classify discovered elements into LeanIX object types: Organizations, Interfaces, Data Objects, and IT Components
5. IF the AI_Engine cannot confidently classify an element, THEN THE AI_Engine SHALL flag the element as "unclassified" with a confidence score

### Requirement 4: Dependency Graph Generation

**User Story:** As an architect, I want to generate dependency graphs so that I can visualize how modules and services relate to each other.

#### Acceptance Criteria

1. WHEN analysis is complete, THE Diagram_Generator SHALL produce a dependency graph showing module-level and package-level dependencies
2. THE Diagram_Generator SHALL represent each dependency with a directed edge from the dependent module to the dependency
3. WHEN circular dependencies are detected, THE Diagram_Generator SHALL visually highlight the circular dependency paths
4. THE Diagram_Generator SHALL output the dependency graph as both a rendered image (PNG or SVG) and a structured data file (JSON)

### Requirement 5: Component Diagram Generation

**User Story:** As an architect, I want to generate component diagrams so that I can see the high-level structural decomposition of the system.

#### Acceptance Criteria

1. WHEN analysis is complete, THE Diagram_Generator SHALL produce a component diagram showing identified system components and their interfaces
2. THE Diagram_Generator SHALL label each component with its name, type, and associated LeanIX object type
3. THE Diagram_Generator SHALL represent inter-component communication with labeled connectors indicating the interface type (REST, gRPC, event, etc.)
4. THE Diagram_Generator SHALL output the component diagram as both a rendered image (PNG or SVG) and a structured data file (JSON)

### Requirement 6: UML Diagram Generation

**User Story:** As an architect, I want to generate UML diagrams so that I can document system structure and behavior in a standardized notation.

#### Acceptance Criteria

1. WHEN analysis is complete, THE Diagram_Generator SHALL produce UML class diagrams for identified object-oriented structures
2. WHEN service interactions are identified, THE Diagram_Generator SHALL produce UML sequence diagrams for key interaction flows
3. THE Diagram_Generator SHALL follow UML 2.5 notation standards
4. THE Diagram_Generator SHALL output UML diagrams as both rendered images (PNG or SVG) and PlantUML source files

### Requirement 7: Lower Level Design Diagram Generation

**User Story:** As an architect, I want to generate lower level design diagrams so that I can document internal component logic and data flows.

#### Acceptance Criteria

1. WHEN analysis of a component is complete, THE Diagram_Generator SHALL produce an LLD showing internal classes, functions, and data flow within the component
2. THE Diagram_Generator SHALL represent data transformations and processing steps as labeled nodes in the LLD
3. THE Diagram_Generator SHALL output the LLD as both a rendered image (PNG or SVG) and a structured data file (JSON)

### Requirement 8: Architectural Decision Record Generation

**User Story:** As an architect, I want the tool to generate Architectural Decision Records so that I can document the rationale behind detected architectural choices.

#### Acceptance Criteria

1. WHEN architectural patterns or significant design choices are detected, THE Document_Generator SHALL produce an ADR for each decision
2. THE Document_Generator SHALL structure each ADR with: Title, Status, Context, Decision, and Consequences sections
3. THE Document_Generator SHALL write ADRs in Markdown format
4. WHEN an existing ADR set is provided as input, THE Document_Generator SHALL identify new decisions not covered by existing ADRs and generate only the missing records

### Requirement 9: LeanIX Object Mapping

**User Story:** As an architect, I want discovered elements mapped to LeanIX object types so that I can integrate the output with our enterprise architecture tooling.

#### Acceptance Criteria

1. THE LeanIX_Mapper SHALL classify each discovered architectural element as one of: Organization, Interface, Data Object, IT Component, or a custom LeanIX type
2. THE LeanIX_Mapper SHALL produce a mapping report in JSON format listing each element, its classification, and the evidence supporting the classification
3. IF an element maps to multiple LeanIX types, THEN THE LeanIX_Mapper SHALL list all applicable types ranked by confidence score
4. THE LeanIX_Mapper SHALL include relationship mappings between LeanIX objects (e.g., IT Component provides Interface, Organization owns IT Component)

### Requirement 10: Markdown Documentation Generation

**User Story:** As an architect, I want the tool to produce comprehensive Markdown documentation so that I can share and version-control the architectural overview.

#### Acceptance Criteria

1. WHEN analysis is complete, THE Document_Generator SHALL produce a Markdown document containing: system overview, component descriptions, dependency summary, and interface catalog
2. THE Document_Generator SHALL embed or link to all generated diagrams within the Markdown document
3. THE Document_Generator SHALL include a table of contents with links to each section
4. THE Document_Generator SHALL format the Markdown document for compatibility with GitHub and standard Markdown renderers

### Requirement 11: Frontend User Interface

**User Story:** As an architect, I want a web-based interface so that I can configure inputs, trigger analysis, and view results interactively.

#### Acceptance Criteria

1. THE Frontend SHALL provide input fields for specifying local folder paths and GitHub URLs
2. THE Frontend SHALL provide file upload controls for PDF, Word, and image files
3. WHEN analysis is triggered, THE Frontend SHALL display a progress indicator showing the current analysis stage
4. WHEN analysis is complete, THE Frontend SHALL display all generated diagrams and documents in a navigable layout
5. THE Frontend SHALL provide download controls for all generated outputs (images, JSON, Markdown, PlantUML)
6. IF an error occurs during analysis, THEN THE Frontend SHALL display the error message returned by the Analyzer

### Requirement 12: Output Serialization and Round-Trip Integrity

**User Story:** As an architect, I want the structured output to be serializable and parseable so that I can programmatically consume and re-import results.

#### Acceptance Criteria

1. THE Analyzer SHALL serialize all structured outputs (dependency graphs, component maps, LeanIX mappings) to JSON format
2. THE Analyzer SHALL parse JSON output files back into internal data structures
3. FOR ALL valid structured outputs, serializing to JSON then parsing back SHALL produce an equivalent data structure (round-trip property)
4. THE Analyzer SHALL validate JSON output against a published JSON Schema before writing to disk
