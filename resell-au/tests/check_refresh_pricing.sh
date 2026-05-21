#!/usr/bin/env bash
# Regression check for the Phase R0/R2 price-drop calculator.
#
# Runs tests/test_refresh_pricing.py — pure unit tests covering each
# acceptance criterion from ABA-156 (Sub-task #4), plus rounding-band
# edge cases that guard the R0 classifier's golden file.
#
# The R0 candidate-table golden at tests/fixtures/refresh-r0.golden.txt
# is the integration counterpart — it exercises the same calculator
# end-to-end through the classifier. Both should stay green together.
#
# Exit 0 = all cases pass.

set -euo pipefail

DIR="$(cd "$(dirname "$0")" && pwd)"
SKILL_ROOT="$(cd "$DIR/.." && pwd)"

cd "$SKILL_ROOT"
python3 -m unittest tests.test_refresh_pricing -v
