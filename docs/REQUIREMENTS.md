# Requirements Document

## 1. Codebase Ingestion

The system accepts local folder paths or GitHub URLs as input. It recursively scans directories to identify source code files across 30+ languages (Python, JavaScript, TypeScript, Java, Go, Rust, etc.), parses file structure, module boundaries, import/export relationships, and public interfaces. GitHub repositories are shallow-cloned via the git CLI. Invalid paths or unreachable URLs produce descriptive error messages.

## 2. Document and Diagram Ingestion

The system accepts existing architectural documents in the following formats:

| Format | Processing |
|--------|-----------|
| PDF | Text and embedded image extraction via PyMuPDF |
| Word (.docx) | Paragraph text and embedded image extraction via python-docx |
| PNG, JPG, SVG | Image pass-through for AI vision analysis |

Unsupported file types return an error listing all supported formats. Corrupted files are identified with descriptive error messages.

## 3. AI-Powered Analysis

Using GPT-4 (text and vision), the system:

- Identifies architectural patterns, layers, and component boundaries from code
- Extracts entities, relationships, and annotations from existing diagrams
- Reconciles differences between code structure and documented architecture
- Classifies elements into LeanIX object types (Organization, Interface, Data Object, IT Component) with confidence scores
- Flags low-confidence classifications as "unclassified"

## 4. Dependency Graph Generation

Produces module-level dependency graphs with directed edges. Circular dependencies are detected via DFS and visually highlighted in red. Output includes both rendered images (PNG/SVG) and structured JSON data.

## 5. Component Diagram Generation

Produces component diagrams where each node is labeled with name, element type, and LeanIX object type. Inter-component communication is represented with labeled connectors (REST, gRPC, event, etc.). Output includes rendered images and structured JSON.

## 6. UML Diagram Generation

Produces UML 2.5-compliant class diagrams (for OO structures) and sequence diagrams (for service interactions). Output includes rendered images and PlantUML source files.

## 7. Lower Level Design Diagrams

Produces LLD diagrams showing internal classes, functions, data flow, and data transformation steps within individual components. Output includes rendered images and structured JSON.

## 8. Architectural Decision Records

Generates ADRs in Markdown format with Title, Status, Context, Decision, and Consequences sections. When existing ADRs are provided, only new decisions not already covered are generated (deduplication).

## 9. LeanIX Object Mapping

Produces a JSON mapping report classifying each element with confidence scores, evidence, and relationship mappings. Elements mapping to multiple types list all applicable types ranked by confidence.

## 10. Markdown Documentation

Generates a comprehensive Markdown document containing system overview, component descriptions, dependency summary, interface catalog, table of contents with anchor links, and embedded diagram references. GitHub-compatible formatting.

## 11. Frontend User Interface

A React-based web interface providing:

- Input fields for local paths and GitHub URLs
- File upload controls for PDF, Word, and image files
- Progress indicator showing pipeline stages (queued → ingesting → analyzing → generating → serializing → complete)
- Navigable results layout with download controls for all output types
- Error message display for analysis failures

## 12. Output Serialization

All structured outputs are serialized to JSON, validated against published JSON Schemas, and support round-trip parsing (serialize → deserialize produces equivalent data).
