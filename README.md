# Architectural Reverse Engineer

An AI-powered tool that analyzes codebases and existing architectural documents to produce comprehensive, up-to-date architectural documentation — dependency graphs, component diagrams, UML, ADRs, LeanIX mappings, and more.

## How It Works

```
Codebase (local path / GitHub URL)  ──┐
                                      ├──▶  AI Analysis  ──▶  Generated Artifacts
Existing Docs (PDF / Word / Images)  ──┘
```

You provide source code and optionally existing documentation. The tool runs a pipeline:

1. **Ingestion** — scans code, extracts text/images from documents
2. **Analysis** — GPT-4 identifies patterns, components, relationships; reconciles code vs. docs
3. **Generation** — produces diagrams, ADRs, LeanIX mappings, Markdown docs
4. **Serialization** — validates all JSON output against published schemas

## Generated Outputs

| Output | Format |
|--------|--------|
| Dependency graphs (with circular dependency highlighting) | PNG/SVG + JSON |
| Component diagrams (labeled with LeanIX types) | PNG/SVG + JSON |
| UML class diagrams | PNG/SVG + PlantUML |
| UML sequence diagrams | PNG/SVG + PlantUML |
| Lower-level design diagrams | PNG/SVG + JSON |
| Architectural Decision Records | Markdown |
| LeanIX mapping report | JSON |
| Architecture documentation | Markdown |

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Backend | Python 3.11+, FastAPI, Pydantic |
| AI | OpenAI GPT-4 (text + vision) |
| Diagrams | Graphviz, PlantUML |
| Document parsing | PyMuPDF, python-docx |
| Frontend | React 18, TypeScript |
| Testing | pytest, Hypothesis (property-based), Jest |

## Project Structure

```
backend/
  app/
    api.py                 # FastAPI endpoints
    models.py              # Pydantic data models
    errors.py              # Error hierarchy
    code_ingester.py       # Codebase scanning and parsing
    document_ingester.py   # PDF/Word/image ingestion
    pdf_processor.py       # PDF text and image extraction
    ai_engine.py           # OpenAI GPT-4 integration
    leanix_mapper.py       # LeanIX object type mapping
    diagram_generator.py   # Graphviz/PlantUML diagram generation
    document_generator.py  # ADR and Markdown generation
    serializer.py          # JSON serialization with schema validation
  schemas/                 # Published JSON Schemas
  tests/
    unit/                  # Unit tests (210 tests)
    property/              # Property-based tests (120 tests, 20 properties)
frontend/
  src/
    App.tsx
    api.ts                 # API client
    components/
      AnalyzeForm.tsx      # Input form
      ProgressIndicator.tsx # Pipeline progress display
      ResultsView.tsx      # Results and downloads
      ErrorDisplay.tsx     # Error messages
  __tests__/               # Frontend component tests (24 tests)
packaging/
  launcher.py              # Unified entry point (starts server, opens browser)
  pyinstaller.spec         # PyInstaller bundle configuration
  build_mac.sh             # macOS build script → .dmg
  build_windows.bat        # Windows build script → .exe
  installer.iss            # Inno Setup script for Windows installer
docs/
  PROBLEM_SUMMARY.md       # Problem space and motivation
  REQUIREMENTS.md          # Functional requirements
  INSTALL.md               # Installation guide (installer + from source)
  USER_GUIDE.md            # End-user walkthrough
  PACKAGING.md             # How to build DMG and EXE installers
```

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| POST | `/analyze` | Submit sources and documents, returns job ID |
| GET | `/status/{job_id}` | Current pipeline stage |
| GET | `/results/{job_id}` | All generated outputs |
| GET | `/download/{job_id}/{artifact}` | Download a specific file |

## Quick Start

See [INSTALL.md](docs/INSTALL.md) for detailed setup instructions, or download a pre-built installer from the releases page.

```bash
# Backend
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
export OPENAI_API_KEY="sk-..."
uvicorn app.api:app --reload

# Frontend (separate terminal)
cd frontend
npm install
npm start
```

Then open http://localhost:3000 in your browser.

## Building Installers

See [PACKAGING.md](docs/PACKAGING.md) for the full guide.

```bash
# macOS — produces dist/ArchitecturalReverseEngineer-0.1.0-mac.dmg
make build-mac

# Windows — produces dist/ArchitecturalReverseEngineer-Setup.exe
packaging\build_windows.bat
```

## Testing

```bash
# Backend — 330 tests (210 unit + 120 property-based)
cd backend && python -m pytest tests/ -v

# Frontend — 24 component tests
cd frontend && npm test
```

## License

This project is provided as-is for internal use.
