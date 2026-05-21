#!/usr/bin/env bash
# Regression check for the Phase R2 listing.md updater.
#
# Runs scripts/refresh_listing_md_update.py against each input fixture
# (REFRESH_R2_TODAY=2026-05-21 locks today's date) and diffs --dry-run
# output against the golden file. Each case targets a distinct invariant:
#
#   case-1-full-with-comps      First refresh on a full listing.md.
#                               Verifies URL/Date replaced, Price unchanged,
#                               Refresh history section created, Comps block
#                               byte-identical.
#   case-2-second-refresh       Second refresh — bullet appended, number
#                               increments to #2, Comps block byte-identical.
#   case-3-no-url-no-comps      No **URL:** line, no Comps section. URL line
#                               inserted after **Platform:**, Refresh history
#                               appended at end of file. price-unchanged bullet
#                               wording when --old-price/--new-price are omitted.
#
# Exit 0 = all cases pass; non-zero = at least one case diverged from its
# golden and needs review before updating.

set -euo pipefail

DIR="$(cd "$(dirname "$0")" && pwd)"
SKILL_ROOT="$(cd "$DIR/.." && pwd)"
FIXTURE_DIR="$DIR/fixtures/refresh-r2"
SCRIPT="$SKILL_ROOT/scripts/refresh_listing_md_update.py"

run_case() {
    local name="$1"; shift
    local input="$FIXTURE_DIR/inputs/${name}.md"
    local golden="$FIXTURE_DIR/golden/${name}.md"
    if ! diff -u "$golden" <(REFRESH_R2_TODAY=2026-05-21 python3 "$SCRIPT" "$input" --dry-run "$@"); then
        echo "FAIL: case '$name' diverged from $golden" >&2
        echo "      If the new output is intentional, re-generate the golden:" >&2
        echo "      REFRESH_R2_TODAY=2026-05-21 python3 $SCRIPT $input --dry-run $* > $golden" >&2
        return 1
    fi
    echo "PASS: $name"
}

fail=0

run_case "case-1-full-with-comps" \
    --old-url "https://www.facebook.com/marketplace/item/111111111/" \
    --new-url "https://www.facebook.com/marketplace/item/222222222/" \
    --age-days 20 --old-price 15 --new-price 15 || fail=1

run_case "case-2-second-refresh" \
    --old-url "https://www.facebook.com/marketplace/item/200000000/" \
    --new-url "https://www.facebook.com/marketplace/item/300000000/" \
    --age-days 11 --old-price 45 --new-price 40 || fail=1

run_case "case-3-no-url-no-comps" \
    --old-url "https://www.facebook.com/marketplace/item/333333333/" \
    --new-url "https://www.facebook.com/marketplace/item/444444444/" \
    --age-days 7 || fail=1

if [[ "$fail" -ne 0 ]]; then
    echo "FAIL: at least one Phase R2 updater case diverged from its golden." >&2
    exit 1
fi
echo "PASS: refresh R2 updater matches all goldens."
