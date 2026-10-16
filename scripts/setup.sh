#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
python3 -c 'import sys; assert (3,10) <= sys.version_info < (3,13), "Python 3.10..3.12 required"'
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements-lock.txt
.venv/bin/python -m pip install --no-deps -e .
if [ -n "${HOLOOCEAN_CLIENT:-}" ]; then
    .venv/bin/python scripts/install_holoocean.py --client "$HOLOOCEAN_CLIENT"
fi
printf '%s\n' 'Ready. Run .venv/bin/holo-desert doctor'
