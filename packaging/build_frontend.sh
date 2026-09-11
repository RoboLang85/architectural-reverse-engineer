#!/usr/bin/env bash
# Build the React frontend for production.
# The output goes to frontend/build/ and is served by the backend.
#
# Usage:
#   bash packaging/build_frontend.sh

set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT/frontend"

if [ ! -d "node_modules" ]; then
    echo "Installing npm dependencies..."
    npm install --silent
fi

# Ensure react-scripts is available
if ! npx react-scripts --version &>/dev/null 2>&1; then
    echo "Installing react-scripts..."
    npm install react-scripts --save-dev --silent
fi

# Set API base URL to empty so the frontend uses relative paths
# (the backend serves both API and static files)
echo "Building frontend for production..."
REACT_APP_API_BASE_URL="" npx react-scripts build

echo "Frontend build complete: frontend/build/"
