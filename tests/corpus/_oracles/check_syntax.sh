#!/bin/sh
# Sanity-parse every corpus program with the legacy parser (syntax only; not a correctness oracle).
cd "$(dirname "$0")/../../.."
for f in tests/corpus/*/*.tel; do python3 main.py parse "$f" >/dev/null 2>/tmp/syn.err || { echo "SYNTAX FAIL $f"; head -3 /tmp/syn.err; }; done
