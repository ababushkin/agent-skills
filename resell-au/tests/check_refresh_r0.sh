#!/usr/bin/env bash
# Regression check for the Phase R0 classifier.
#
# Runs scripts/refresh_r0_classify.py against the deterministic fixture
# set at tests/fixtures/refresh-r0/ (with REFRESH_R0_TODAY=2026-05-21
# locking the age math) and diffs the output against the golden file.
#
# Exit 0 = pass; non-zero = the classifier's behaviour changed and the
# golden file needs to be reviewed before updating.

set -euo pipefail

DIR="$(cd "$(dirname "$0")" && pwd)"
SKILL_ROOT="$(cd "$DIR/.." && pwd)"
FIXTURE="$DIR/fixtures/refresh-r0"
GOLDEN="$DIR/fixtures/refresh-r0.golden.txt"
SCRIPT="$SKILL_ROOT/scripts/refresh_r0_classify.py"

if ! diff -u "$GOLDEN" <(REFRESH_R0_TODAY=2026-05-21 python3 "$SCRIPT" "$FIXTURE"); then
    echo "FAIL: refresh_r0_classify.py output does not match $GOLDEN" >&2
    echo "      If the new output is intentional, re-generate the golden:" >&2
    echo "      REFRESH_R0_TODAY=2026-05-21 python3 $SCRIPT $FIXTURE > $GOLDEN" >&2
    exit 1
fi

echo "PASS: refresh R0 classifier matches golden."
