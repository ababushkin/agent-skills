#!/usr/bin/env bash
# Regression check for the Refresh Mode run-state helper (Sub-task ABA-157).
#
# Runs tests/test_refresh_runstate.py — unit tests covering plan
# (resume classification), apply_update (status → *_at stamping),
# find_latest_runstate / has_unfinished_work (resume-vs-new decision),
# and cmd_init end-to-end (fresh / resume / stale-terminal paths).
#
# The Refresh Mode end-to-end hand-test against ~/Desktop/things-for-sale/
# is the integration counterpart for the multi-item loop, per the
# ABA-157 acceptance criteria. Both should stay green together.
#
# Exit 0 = all cases pass.

set -euo pipefail

DIR="$(cd "$(dirname "$0")" && pwd)"
SKILL_ROOT="$(cd "$DIR/.." && pwd)"

cd "$SKILL_ROOT"
python3 -m unittest tests.test_refresh_runstate -v
