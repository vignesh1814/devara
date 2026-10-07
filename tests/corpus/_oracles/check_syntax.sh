#!/bin/sh
# Sanity-parse every corpus program (syntax only; not a correctness oracle).
cd "$(dirname "$0")/../../.." || exit 1
err=$(mktemp)
trap 'rm -f "$err"' EXIT
for f in tests/corpus/*/*.tel; do
    ./devara parse "$f" >/dev/null 2>"$err" || { echo "SYNTAX FAIL $f"; head -3 "$err"; }
done
