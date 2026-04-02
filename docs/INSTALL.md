# Installation Guide

There are two ways to install the Architectural Reverse Engineer:

1. **Pre-built installer** (recommended for end users) — download the DMG (macOS) or Setup EXE (Windows)
2. **From source** (for developers) — clone the repo and install dependencies manually

## Option A: Pre-Built Installer

### macOS

1. Download `ArchitecturalReverseEngineer-0.1.0-mac.dmg`
2. Double-click the DMG file
3. Drag "Architectural Reverse Engineer" to your Applications folder
4. Set your OpenAI API key: `export OPENAI_API_KEY="sk-..."` (add to `~/.zshrc` for persistence)
5. Open the app from Applications (right-click → Open on first launch to bypass Gatekeeper)
6. The app starts a local server and opens your browser to `http://127.0.0.1:8000`

For full diagram rendering, also install Graphviz and PlantUML:
```bash
brew install graphviz plantuml
```

### Windows

1. Download `ArchitecturalReverseEngineer-Setup.exe`
2. Run the installer and follow the prompts
3. Set your OpenAI API key as a system environment variable: `OPENAI_API_KEY=sk-...`
4. Launch from the Start Menu or Desktop shortcut
5. The app starts a local server and opens your browser to `http://127.0.0.1:8000`

For full diagram rendering, also install Graphviz and PlantUML and add them to your PATH.

## Option B: From Source

### Prerequisites

Before installing, ensure you have the following on your system:

| Requirement | Version | Check Command |
|-------------|---------|---------------|
| Python | 3.11 or higher | `python3 --version` |
| Node.js | 18 or higher | `node --version` |
| npm | 9 or higher | `npm --version` |
| Git | any recent version | `git --version` |
| Graphviz | any recent version | `dot -V` |
| PlantUML | any recent version | `plantuml -version` |
| OpenAI API key | — | — |

## Step 1: Install System Dependencies

### macOS (Homebrew)

```bash
brew install python@3.11 node graphviz plantuml
```

### Ubuntu / Debian

```bash
sudo apt update
sudo apt install python3.11 python3.11-venv nodejs npm graphviz plantuml
```

### Windows

- Python: download from https://www.python.org/downloads/
- Node.js: download from https://nodejs.org/
- Graphviz: download from https://graphviz.org/download/
- PlantUML: download the JAR from https://plantuml.com/download and ensure `plantuml` is on your PATH (or create a wrapper script)

## Step 2: Clone the Repository

```bash
git clone <repository-url>
cd architectural-reverse-engineer
```

## Step 3: Set Up the Backend

```bash
cd backend

# Create and activate a virtual environment
python3 -m venv .venv
source .venv/bin/activate    # macOS/Linux
# .venv\Scripts\activate     # Windows

# Install the package with all dependencies
pip install -e ".[dev]"
```

This installs:
- FastAPI, Uvicorn (web server)
- Pydantic (data validation)
- OpenAI SDK (AI analysis)
- PyMuPDF (PDF processing)
- python-docx (Word document processing)
- Graphviz Python bindings (diagram rendering)
- jsonschema (output validation)
- pytest, Hypothesis, pytest-cov (testing)

## Step 4: Configure the OpenAI API Key

The AI Engine requires an OpenAI API key with access to GPT-4.

```bash
export OPENAI_API_KEY="sk-your-key-here"
```

To make this persistent, add it to your shell profile (`~/.bashrc`, `~/.zshrc`, etc.).

## Step 5: Verify the Backend

```bash
cd backend

# Run the test suite (should report 330 passing tests)
python -m pytest tests/ -v --tb=short

# Start the API server
uvicorn app.api:app --reload --host 0.0.0.0 --port 8000
```

The API will be available at http://localhost:8000. You can verify it's running by visiting http://localhost:8000/docs for the auto-generated Swagger UI.

## Step 6: Set Up the Frontend

```bash
cd frontend

# Install Node.js dependencies
npm install

# Run frontend tests
npm test

# Start the development server
npm start
```

The frontend will be available at http://localhost:3000 and will proxy API requests to http://localhost:8000.

## Step 7: Verify End-to-End

1. Start the backend: `cd backend && uvicorn app.api:app --reload`
2. Start the frontend: `cd frontend && npm start`
3. Open http://localhost:3000
4. Enter a local folder path or GitHub URL
5. Click "Analyze" and watch the progress indicator

## Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `OPENAI_API_KEY` | Yes | — | OpenAI API key for GPT-4 access |
| `REACT_APP_API_BASE_URL` | No | `http://localhost:8000` | Backend API URL for the frontend |

## Troubleshooting

### "Graphviz rendering failed"

Graphviz CLI (`dot`) is not installed or not on your PATH. Install it:
```bash
# macOS
brew install graphviz

# Ubuntu
sudo apt install graphviz
```

### "PlantUML CLI not found"

PlantUML is not installed or not on your PATH. Install it:
```bash
# macOS
brew install plantuml

# Ubuntu
sudo apt install plantuml
```

### "OpenAI API key not provided"

Set the `OPENAI_API_KEY` environment variable before starting the backend.

### Backend tests fail with import errors

Make sure you're running tests from the `backend/` directory with the virtual environment activated:
```bash
cd backend
source .venv/bin/activate
python -m pytest tests/ -v
```

### Frontend tests fail

Make sure you've run `npm install` in the `frontend/` directory first:
```bash
cd frontend
npm install
npm test
```

### Git clone failures for GitHub URLs

Ensure `git` is installed and accessible from the command line. The tool uses `git clone --depth 1` for shallow cloning.
