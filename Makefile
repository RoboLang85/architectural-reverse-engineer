# ============================================================================
# Makefile for Architectural Reverse Engineer
# ============================================================================

.PHONY: help install test build-frontend build-mac build-windows clean

VERSION := 0.1.0

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-20s\033[0m %s\n", $$1, $$2}'

install: ## Install all dependencies (backend + frontend)
	cd backend && pip install -e ".[dev]"
	cd frontend && npm install

test: ## Run all tests
	cd backend && python -m pytest tests/ -v --tb=short
	cd frontend && npm test 2>/dev/null || echo "Frontend tests require npm install first"

build-frontend: ## Build the React frontend for production
	bash packaging/build_frontend.sh

build-mac: ## Build macOS .dmg installer
	bash packaging/build_mac.sh

build-windows: ## Build Windows executable (run on Windows)
	packaging\build_windows.bat

run: ## Start the application (backend + frontend served together)
	python packaging/launcher.py

run-dev: ## Start backend and frontend separately for development
	@echo "Start backend:  cd backend && uvicorn app.api:app --reload"
	@echo "Start frontend: cd frontend && npm start"

clean: ## Remove build artifacts
	rm -rf build/ dist/ packaging/.build_venv/
	rm -rf frontend/build/
	rm -rf backend/__pycache__ backend/app/__pycache__
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .pytest_cache -exec rm -rf {} + 2>/dev/null || true
