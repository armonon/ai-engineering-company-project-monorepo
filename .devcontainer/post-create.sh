#!/usr/bin/env bash
# Codespaces / dev container setup. Mirrors .github/workflows/ci.yml so a
# fresh Codespace can run every documented command (npm, uv, npx).
set -euo pipefail

python -m pip install --upgrade --quiet pip uv

# JavaScript workspaces (website, backoffice, public-website, packages).
npm ci --no-audit --no-fund
npm run bootstrap

# FastAPI service and the Python pipeline packages it depends on.
uv sync --project services/api --locked

echo "Devcontainer setup complete. Public website: npx --yes http-server@14.1.1 uis/public-website -p 3000 -a 0.0.0.0 -c-1"
