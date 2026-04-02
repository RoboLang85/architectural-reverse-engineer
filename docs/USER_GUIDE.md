# User Guide

This guide walks you through using the Architectural Reverse Engineer to analyze a codebase and generate architectural documentation.

## Getting Started

Make sure both the backend and frontend are running (see [INSTALL.md](INSTALL.md)):

```bash
# Terminal 1 — Backend
cd backend && source .venv/bin/activate
uvicorn app.api:app --reload

# Terminal 2 — Frontend
cd frontend && npm start
```

Open http://localhost:3000 in your browser.

## Using the Web Interface

### Providing Inputs

The form has three input areas:

1. **Local Folder Path** — enter the absolute path to a codebase on your machine (e.g., `/Users/you/projects/my-app`). The tool will recursively scan for source files in Python, JavaScript, TypeScript, Java, Go, Rust, and 25+ other languages.

2. **GitHub URL** — enter a public GitHub repository URL (e.g., `https://github.com/owner/repo`). The tool will shallow-clone the repository and analyze it.

3. **Upload Documents** — click to upload existing architectural documents. Supported formats:
   - PDF files (text and embedded images are extracted)
   - Word documents (.docx — paragraphs and embedded images are extracted)
   - Images (PNG, JPG, SVG — analyzed by GPT-4 vision)

You can provide any combination of these inputs. At least one source or document is required.

### Running the Analysis

Click the **Analyze** button. The progress indicator shows the current pipeline stage:

| Stage | What's Happening |
|-------|-----------------|
| Queued | Job is queued for processing |
| Ingesting | Scanning code, extracting document content |
| Analyzing | GPT-4 is identifying patterns, components, and relationships |
| Generating | Producing diagrams, ADRs, LeanIX mappings, and documentation |
| Serializing | Validating and serializing all JSON outputs |
| Complete | All artifacts are ready |

A typical analysis takes 30 seconds to a few minutes depending on codebase size and the number of documents.

### Viewing Results

Once complete, the results page shows:

- **Generated Outputs** — structured data for each artifact (dependency graphs, component maps, LeanIX report, ADRs, Markdown documentation)
- **Warnings / Errors** — any non-fatal issues encountered during analysis (e.g., a file that couldn't be parsed, a diagram renderer that wasn't available). These don't prevent other outputs from being generated.
- **Downloads** — clickable links to download individual artifacts:
  - `dependency_graph.png` — module dependency visualization
  - `component.png` — component diagram with LeanIX labels
  - `uml_class.png` — UML class diagram
  - `uml_sequence.png` — UML sequence diagram
  - `architecture.md` — complete Markdown documentation
  - `adr_0.md`, `adr_1.md`, ... — individual ADR files
  - JSON structured data files

Click **New Analysis** to start over with different inputs.

## Using the API Directly

You can also interact with the backend API without the frontend. The API runs at http://localhost:8000.

### Submit an Analysis

```bash
curl -X POST http://localhost:8000/analyze \
  -H "Content-Type: application/json" \
  -d '{
    "sources": [
      {"input_type": "local_path", "value": "/path/to/your/project"}
    ],
    "documents": [
      {"file_path": "/path/to/architecture.pdf", "file_type": "pdf"}
    ]
  }'
```

Response:
```json
{"job_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890"}
```

### Check Status

```bash
curl http://localhost:8000/status/a1b2c3d4-e5f6-7890-abcd-ef1234567890
```

Response:
```json
{"job_id": "a1b2c3d4-...", "stage": "analyzing"}
```

### Get Results

```bash
curl http://localhost:8000/results/a1b2c3d4-e5f6-7890-abcd-ef1234567890
```

Response includes all generated data, error list, and available artifact filenames.

### Download an Artifact

```bash
curl -O http://localhost:8000/download/a1b2c3d4-e5f6-7890-abcd-ef1234567890/dependency_graph.png
curl -O http://localhost:8000/download/a1b2c3d4-e5f6-7890-abcd-ef1234567890/architecture.md
```

## Understanding the Outputs

### Dependency Graphs

Shows module-level dependencies as directed edges. Nodes and edges involved in circular dependencies are highlighted in red. The structured JSON includes `in_cycle` flags for programmatic detection.

### Component Diagrams

Each component node is labeled with three pieces of information:
- Component name
- Element type (service, database, gateway, etc.)
- LeanIX object type (IT Component, Data Object, Interface, Organization)

Connectors between components are labeled with the interface type (REST, gRPC, event, depends_on, etc.).

### UML Diagrams

Class diagrams show inheritance (`--|>`), composition (`*--`), association (`-->`), and implementation (`..|>`) relationships. Only elements with OO types (class, interface, module) are included.

Sequence diagrams show `calls` relationships as messages between participants, preserving the order of interactions.

### ADRs

Each ADR follows the standard format:
- **Title** — the architectural decision
- **Status** — always "Proposed" for auto-generated ADRs
- **Context** — why this decision was relevant
- **Decision** — what was decided
- **Consequences** — trade-offs and implications

If you provide existing ADRs, the tool will only generate records for decisions not already documented.

### LeanIX Mapping Report

A JSON report mapping each discovered element to LeanIX object types with:
- Confidence scores (0.0 to 1.0)
- Alternative type classifications ranked by confidence
- Evidence supporting each classification
- Relationship mappings between LeanIX objects

### Markdown Documentation

A complete architectural document with:
- Table of contents with anchor links
- System overview (detected patterns, layers, discrepancies)
- Component descriptions (name, type, LeanIX type, confidence)
- Dependency summary table
- Interface catalog table
- Embedded diagram references

## Tips

- Provide both code and existing documentation for the most accurate results — the AI reconciles discrepancies between the two.
- For large codebases, the analysis may take several minutes. The progress indicator updates in real time.
- If Graphviz or PlantUML aren't installed, diagram rendering will fail gracefully — you'll still get structured JSON data and all other outputs.
- The LeanIX mapping report is designed for direct import into LeanIX or similar enterprise architecture tools.
- All JSON outputs are validated against published schemas in `backend/schemas/` — you can use these schemas to validate your own tooling integrations.
