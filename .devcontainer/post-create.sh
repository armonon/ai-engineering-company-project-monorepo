#!/usr/bin/env bash
# Codespaces / dev container setup for the Milestone 1 snapshot.
set -euo pipefail

python -m pip install --upgrade --quiet pip uv

npm ci --no-audit --no-fund
if npm run | grep -q "^  bootstrap"; then npm run bootstrap; fi

if [ -f services/api/pyproject.toml ]; then
  uv sync --project services/api
fi

echo "Devcontainer setup complete. Public website: npx --yes http-server@14.1.1 uis/public-website -p 3000 -a 0.0.0.0 -c-1"
