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
cp /input/pyproject.toml /input/requirements-lock.txt /input/LICENSE /tmp/holo-desert-check/
cp -r /input/src /input/tests /input/scripts /tmp/holo-desert-check/
cd /tmp/holo-desert-check
bash scripts/setup.sh
.venv/bin/python -m pip check
.venv/bin/python -m pytest -q -m 'not desert and not holoocean'
