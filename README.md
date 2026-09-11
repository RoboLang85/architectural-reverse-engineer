# Architectural Reverse Engineer

Architectural Reverse Engineer is an AI-assisted application for analyzing source code and existing architecture documentation, then producing structured architectural artifacts such as dependency graphs, component diagrams, UML, ADRs, and LeanIX-oriented mappings.

The project is intended for architects and engineers who need to reconstruct or refresh documentation for systems whose implementation and design artifacts have drifted apart.

## How it works

```text
Codebase (local path / GitHub URL) ----+
                                       +--> ingestion --> AI analysis --> reconciliation --> generated artifacts
Existing docs (PDF / Word / images) ---+
```

The pipeline separates deterministic processing from model-assisted interpretation:

1. **Ingestion** scans source files and extracts content from supported documents.
2. **Analysis** identifies components, relationships, layers, and architectural patterns.
3. **Reconciliation** compares code-derived and document-derived views.
4. **Generation** produces diagrams, ADRs, LeanIX mappings, and Markdown documentation.
5. **Serialization** validates structured outputs against the repository's JSON schemas.

## Generated outputs

| Output | Format |
| --- | --- |
| Dependency graphs | PNG/SVG + JSON |
| Component diagrams | PNG/SVG + JSON |
| UML class diagrams | PNG/SVG + PlantUML |
| UML sequence diagrams | PNG/SVG + PlantUML |
| Lower-level design diagrams | PNG/SVG + JSON |
| Architectural Decision Records | Markdown |
| LeanIX mapping report | JSON |
| Architecture documentation | Markdown |

## Tech stack

- **Backend:** Python 3.11+, FastAPI, Pydantic
- **AI:** OpenAI API via the official Python SDK
- **Diagrams:** Graphviz and PlantUML
- **Document parsing:** PyMuPDF and python-docx
- **Frontend:** React 18 and TypeScript
- **Testing:** pytest, Hypothesis, Jest, and React Testing Library

## Quick start

See [`docs/INSTALL.md`](docs/INSTALL.md) for the complete installation guide.

### Backend

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
export OPENAI_API_KEY="your-api-key"
uvicorn app.api:app --reload
```

### Frontend

In a second terminal:

```bash
cd frontend
npm install
npm start
```

Then open `http://localhost:3000`.

## API

| Method | Path | Description |
| --- | --- | --- |
| `POST` | `/analyze` | Submit sources/documents and receive a job ID |
| `GET` | `/status/{job_id}` | Inspect pipeline progress |
| `GET` | `/results/{job_id}` | Retrieve generated results |
| `GET` | `/download/{job_id}/{artifact}` | Download a generated artifact |

## Project structure

```text
backend/
  app/              Core ingestion, analysis, mapping, and generation logic
  schemas/          Published JSON schemas
  tests/            Unit and property-based tests
frontend/
  src/              React application
packaging/           macOS/Windows packaging and launcher tooling
docs/                Requirements, installation, user, and packaging guides
```

## Security and data handling

The application can send code-derived context and document content to the configured OpenAI model. **Do not analyze proprietary, regulated, customer, or otherwise sensitive material unless you are authorized to transmit that content to the configured model provider.**

Keep API keys in environment variables or an external secret store. The repository's `.gitignore` excludes `.env`, local virtual environments, generated builds, and common IDE/test artifacts. Never commit credentials or source material being analyzed.

GitHub URLs accepted by the analyzer should be treated as untrusted input. If you deploy this service beyond a trusted local environment, add authentication, authorization, request-size limits, network egress controls, and repository allowlisting appropriate to your threat model.

## Testing

```bash
cd backend
python -m pytest tests/ -v
```

For the frontend:

```bash
cd frontend
npm test
```

## Building installers

See [`docs/PACKAGING.md`](docs/PACKAGING.md).

```bash
make build-mac
```

On Windows, use the packaging scripts documented in the packaging guide.

## Current design notes

The existing AI engine defaults to the model configured in the source implementation. Model availability and API behavior can change over time, so verify the configured model against current provider documentation before deployment.

LeanIX classification uses confidence scoring and marks low-confidence mappings as unclassified rather than silently treating uncertain mappings as authoritative.

## Contributing

Issues and pull requests are welcome. Please keep changes testable, avoid committing generated/customer data, and preserve the separation between deterministic processing and model-assisted architectural interpretation.

## License

Released under the [MIT License](LICENSE).
