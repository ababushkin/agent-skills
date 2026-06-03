#!/usr/bin/env bash
# Regression: make_ics.py against a golden .ics. Run from anywhere.
set -euo pipefail

DIR="$(cd "$(dirname "$0")" && pwd)"
SKILL_ROOT="$(cd "$DIR/.." && pwd)"
cd "$SKILL_ROOT"

got="$(python3 scripts/make_ics.py tests/fixtures/events.json)"
want="$(cat tests/fixtures/pickups.golden.ics)"

if [ "$got" = "$want" ]; then
  echo "PASS make_ics: output matches golden"
else
  echo "FAIL make_ics: output differs from tests/fixtures/pickups.golden.ics" >&2
  diff <(printf '%s' "$want") <(printf '%s' "$got") >&2 || true
  exit 1
fi
