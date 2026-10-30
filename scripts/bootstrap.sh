#!/usr/bin/env bash
# Recreate both isolated environments from pinned requirements.
set -euo pipefail
python3 -m venv .venv-prod
.venv-prod/bin/pip install --upgrade pip >/dev/null
.venv-prod/bin/pip install -r requirements-prod.txt
python3 -m venv .venv-legacy
.venv-legacy/bin/pip install --upgrade pip >/dev/null
.venv-legacy/bin/pip install -r requirements-legacy.txt
echo "Environments ready. Run:"
echo "  make check PROD=.venv-prod/bin/python LEGACY=.venv-legacy/bin/python"
echo "  make smoke PROD=.venv-prod/bin/python"
