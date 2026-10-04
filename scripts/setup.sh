#!/usr/bin/env bash
# Reproducible dev setup: clone -> ./scripts/setup.sh -> pytest
set -euo pipefail
cd "$(dirname "$0")/.."
python3 --version
command -v gcc >/dev/null || { echo "gcc is required (assembler/linker/runtime)"; exit 1; }
python3 -m pip install --quiet -r requirements-dev.txt
chmod +x devara
echo "setup complete. Try: pytest -m 'not slow'  |  ./devara run examples/example.tel"
