#!/usr/bin/env bash
# Optional validation inside a disposable Ubuntu 24.04 Docker container.
# Never run this helper directly on a host: it installs container prerequisites.
set -euo pipefail
if [ ! -f /.dockerenv ]; then
    printf '%s\n' 'Run only inside a disposable Docker container.' >&2
    exit 2
fi
apt-get update -qq
DEBIAN_FRONTEND=noninteractive apt-get install -y -qq python3-venv python3-dev build-essential
mkdir -p /tmp/holo-desert-check
cp /input/pyproject.toml /input/requirements-lock.txt /input/LICENSE /input/README.md /tmp/holo-desert-check/
cp -r /input/src /input/tests /input/scripts /input/examples /tmp/holo-desert-check/
cd /tmp/holo-desert-check
bash scripts/setup.sh
.venv/bin/python -m pip check
.venv/bin/python -m pytest -q -m 'not desert and not holoocean'
# Library-only install of the built wheel in a fresh venv, used as an external package.
.venv/bin/python -m pip wheel --no-deps -q -w /tmp/wheel .
python3 -m venv /tmp/clean
/tmp/clean/bin/pip install -q /tmp/wheel/*.whl
cd /tmp && /tmp/clean/bin/python -I /tmp/holo-desert-check/examples/external_app/check_install.py
/tmp/clean/bin/holo-desert doctor --library-only --json > /dev/null || true
