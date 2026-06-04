#!/usr/bin/env bash
# Regression check for password_audit.py dedup / merge logic.
#
# Pure unit tests over the subdomain-collapse dedup key, the
# stays-separate guards (different user / password / registrable domain),
# reuse keying, and the title-only review matcher. All data is synthetic.
#
# Python is pinned via the repo .mise.toml; this wrapper runs the suite
# through `mise exec` so it uses that version regardless of the caller's
# shell. Falls back to plain python3 if mise isn't installed.
#
# Exit 0 = all cases pass.

set -euo pipefail

DIR="$(cd "$(dirname "$0")" && pwd)"
SKILL_ROOT="$(cd "$DIR/.." && pwd)"

cd "$SKILL_ROOT"
if command -v mise >/dev/null 2>&1; then
  mise exec -- python3 -m unittest tests.test_dedup -v
else
  echo "note: mise not found; falling back to system python3" >&2
  python3 -m unittest tests.test_dedup -v
fi
