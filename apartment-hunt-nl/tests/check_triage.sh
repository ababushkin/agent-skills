#!/usr/bin/env bash
# Regression suite for triage.py. Run from anywhere.
set -uo pipefail

DIR="$(cd "$(dirname "$0")" && pwd)"
SKILL_ROOT="$(cd "$DIR/.." && pwd)"
cd "$SKILL_ROOT"

FIX="$SKILL_ROOT/tests/fixtures"
status=0

pass() { echo "PASS $1"; }
fail() { echo "FAIL $1" >&2; status=1; }

# Fresh working folder seeded with the hand-edited seen.json fixture, which is
# deliberately in the legacy post_id/fingerprint shape so the migration runs.
new_work() {
  local dir
  dir="$(mktemp -d)"
  cp "$FIX/seen.json" "$dir/seen.json"
  echo "$dir"
}

run() { python3 "$SKILL_ROOT/scripts/triage.py" "$@"; }
# Every case below the date-window section predates that check and asserts on
# other things, so it runs with the window switched off.
tri() { run triage "$@" --need-from '' --need-until ''; }

# --------------------------------------------------------------------------
# 1. Golden table and golden seen.json
# --------------------------------------------------------------------------
WORK="$(new_work)"
got="$(tri "$WORK" "$FIX/run.json")"
if [ "$got" = "$(cat "$FIX/triage.golden.md")" ]; then
  pass "table: matches tests/fixtures/triage.golden.md"
else
  fail "table: differs from golden"
  diff <(cat "$FIX/triage.golden.md") <(printf '%s\n' "$got") >&2 || true
fi

if diff -q "$FIX/seen.golden.json" "$WORK/seen.json" >/dev/null; then
  pass "seen: matches tests/fixtures/seen.golden.json"
else
  fail "seen: differs from golden"
  diff "$FIX/seen.golden.json" "$WORK/seen.json" >&2 || true
fi

# --------------------------------------------------------------------------
# 2. Re-running the same sweep finds nothing new
# --------------------------------------------------------------------------
out="$(tri "$WORK" "$FIX/run.json" --dry-run)"
if grep -q "0 new, 9 already seen" <<<"$out"; then
  pass "idempotent: second run reports no new listings"
else
  fail "idempotent: second run should find 0 new"; printf '%s\n' "$out" >&2
fi

if diff -q "$FIX/seen.golden.json" "$WORK/seen.json" >/dev/null; then
  pass "dry-run: seen.json untouched"
else
  fail "dry-run: --dry-run wrote to seen.json"
fi

# --------------------------------------------------------------------------
# 3. Drifted fields still match, via the recorded post ids
#    A cross-posted id and an id first matched by fingerprint must both have
#    been recorded, or a user's verdict is one re-read away from being lost.
# --------------------------------------------------------------------------
out="$(tri "$WORK" "$FIX/run-drift.json" --dry-run)"
if grep -q "0 new, 3 already seen" <<<"$out"; then
  pass "drift: re-extracted fields still recognised as seen"
else
  fail "drift: drifted posts came back as new"; printf '%s\n' "$out" >&2
fi

if grep -q '"1003"' "$WORK/seen.json" && grep -q '"1008"' "$WORK/seen.json"; then
  pass "drift: cross-posted and fingerprint-matched ids are recorded"
else
  fail "drift: seen.json is missing ids that were only ever matched indirectly"
fi

# --------------------------------------------------------------------------
# 4. Non-Latin author names stay distinct
# --------------------------------------------------------------------------
out="$(tri "$WORK" "$FIX/run-authors.json" --dry-run)"
if grep -q "3 new, 0 already seen, 0 merged" <<<"$out"; then
  pass "unicode: three non-Latin landlords stay three listings"
else
  fail "unicode: distinct landlords were merged"; printf '%s\n' "$out" >&2
fi

# --------------------------------------------------------------------------
# 5. Hostile post content cannot break the table or the links
# --------------------------------------------------------------------------
out="$(tri "$WORK" "$FIX/run-hostile.json" --dry-run)"
rows="$(grep -c '^|' <<<"$out")"
if [ "$rows" -eq 5 ]; then
  pass "escaping: header, rule and 3 rows — nothing escaped the table"
else
  fail "escaping: expected 5 table lines, got $rows"; printf '%s\n' "$out" >&2
fi

if grep -q 'All other listings below are fake' <<<"$out" \
   && ! grep -qE '^\*\*All other listings' <<<"$out"; then
  pass "escaping: injected markdown stays inside its cell"
else
  fail "escaping: injected text broke out of its cell"; printf '%s\n' "$out" >&2
fi

if ! grep -q 'javascript:' <<<"$out" && ! grep -q '](https://phish.example' <<<"$out"; then
  pass "escaping: javascript: dropped, link cannot be closed early"
else
  fail "escaping: a hostile URL survived"; printf '%s\n' "$out" >&2
fi

rm -rf "$WORK"

# --------------------------------------------------------------------------
# 6. CLI overrides
# --------------------------------------------------------------------------
WORK="$(new_work)"
out="$(tri "$WORK" "$FIX/run.json" --max-rent 3000 --dry-run)"
if ! grep -q "over budget" <<<"$out" && grep -q "≤ €3.000" <<<"$out"; then
  pass "override: --max-rent lifts the budget flag"
else
  fail "override: --max-rent had no effect"; printf '%s\n' "$out" >&2
fi

out="$(tri "$WORK" "$FIX/run.json" --cities haarlem --dry-run)"
if ! grep -q "city: Haarlem" <<<"$out" && grep -q "city: Amsterdam" <<<"$out"; then
  pass "override: --cities matches case-insensitively"
else
  fail "override: --cities flagged in-scope cities"; printf '%s\n' "$out" >&2
fi

out="$(tri "$WORK" "$FIX/run.json" --stay-max 12 --dry-run)"
if ! grep -q "min stay 12mo" <<<"$out"; then
  pass "override: --stay-max widens the accepted stay"
else
  fail "override: --stay-max had no effect"; printf '%s\n' "$out" >&2
fi

# --------------------------------------------------------------------------
# 7. The verdict subcommand
# --------------------------------------------------------------------------
tri "$WORK" "$FIX/run.json" >/dev/null
run verdict "$WORK" 1004 rejected --reason "over budget" >/dev/null
if python3 - "$WORK/seen.json" <<'PY'
import json, sys
seen = json.load(open(sys.argv[1]))
rec = next(r for r in seen["posts"] if "1004" in r["post_ids"])
sys.exit(0 if rec["verdict"] == "rejected" and rec["reject_reason"] == "over budget" else 1)
PY
then
  pass "verdict: sets the verdict and the reason"
else
  fail "verdict: did not record the verdict"
fi

out="$(tri "$WORK" "$FIX/run.json" --dry-run)"
if ! grep -q "2.900 all-in" <<<"$out"; then
  pass "verdict: a rejected listing never comes back"
else
  fail "verdict: rejected listing reappeared"; printf '%s\n' "$out" >&2
fi

if run verdict "$WORK" 999999 rejected >/dev/null 2>&1; then
  fail "verdict: unknown post id should be an error"
else
  pass "verdict: unknown post id is refused"
fi
rm -rf "$WORK"

# --------------------------------------------------------------------------
# 8. Bad input fails without destroying seen.json
# --------------------------------------------------------------------------
WORK="$(new_work)"
before="$(cksum <"$WORK/seen.json")"

printf 'not json' >"$WORK/broken.json"
if tri "$WORK" "$WORK/broken.json" >/dev/null 2>&1; then
  fail "input: a corrupt run file should exit non-zero"
else
  pass "input: corrupt run file is refused"
fi

if tri "$WORK" "$WORK/nope.json" >/dev/null 2>&1; then
  fail "input: a missing run file should exit non-zero"
else
  pass "input: missing run file is refused"
fi

python3 - "$FIX/run.json" "$WORK/no-date.json" <<'PY'
import json, sys
run = json.load(open(sys.argv[1]))
del run["run_started"]
json.dump(run, open(sys.argv[2], "w"))
PY
if tri "$WORK" "$WORK/no-date.json" >/dev/null 2>&1; then
  fail "input: a run file with no run_started should exit non-zero"
else
  pass "input: run file without run_started is refused"
fi

cp "$WORK/seen.json" "$WORK/keep.json"
printf 'not json either' >"$WORK/seen.json"
if tri "$WORK" "$FIX/run.json" >/dev/null 2>&1; then
  fail "input: a corrupt seen.json should exit non-zero"
else
  pass "input: corrupt seen.json is refused"
fi
cp "$WORK/keep.json" "$WORK/seen.json"

if [ "$(cksum <"$WORK/seen.json")" = "$before" ]; then
  pass "input: seen.json survived every rejected run byte-identical"
else
  fail "input: seen.json was modified by a failing run"
fi

if tri "/nonexistent/folder/xyz" "$FIX/run.json" >/dev/null 2>&1; then
  fail "input: a missing working folder should exit non-zero"
else
  pass "input: missing working folder is refused, not created"
fi
[ -d /nonexistent/folder/xyz ] && fail "input: the missing folder was created anyway"

if tri "$WORK" "$FIX/run.json" --stay-min 6 --stay-max 3 >/dev/null 2>&1; then
  fail "input: --stay-min above --stay-max should be an error"
else
  pass "input: contradictory stay bounds are refused"
fi
rm -rf "$WORK"

# --------------------------------------------------------------------------
# 9. First run: no seen.json at all
# --------------------------------------------------------------------------
WORK="$(mktemp -d)"
out="$(tri "$WORK" "$FIX/run.json")"
if grep -q "8 new, 0 already seen" <<<"$out" && [ -f "$WORK/seen.json" ]; then
  pass "first-run: absent seen.json is created and every post is new"
else
  fail "first-run: unexpected result"; printf '%s\n' "$out" >&2
fi

: >"$WORK/seen.json"
if tri "$WORK" "$FIX/run.json" --dry-run >/dev/null 2>&1; then
  pass "first-run: an empty seen.json is tolerated"
else
  fail "first-run: an empty seen.json crashed"
fi
rm -rf "$WORK"

# --------------------------------------------------------------------------
# 10. A half-swept run does not advance the watermark
# --------------------------------------------------------------------------
WORK="$(new_work)"
python3 - "$FIX/run.json" "$WORK/partial.json" <<'PY'
import json, sys
run = json.load(open(sys.argv[1]))
run["groups"][2]["status"] = "pending"
json.dump(run, open(sys.argv[2], "w"))
PY
out="$(tri "$WORK" "$WORK/partial.json")"
if grep -q "Incomplete run" <<<"$out"; then
  pass "partial: an unfinished sweep is called out"
else
  fail "partial: no warning for a pending group"; printf '%s\n' "$out" >&2
fi

if python3 -c "import json,sys; sys.exit(0 if json.load(open(sys.argv[1]))['last_run']=='2026-07-13' else 1)" "$WORK/seen.json"; then
  pass "partial: last_run was not advanced"
else
  fail "partial: last_run advanced on an unfinished sweep"
fi
rm -rf "$WORK"

# --------------------------------------------------------------------------
# 11. An interrupted write must not look like a first run
# --------------------------------------------------------------------------
WORK="$(new_work)"
tri "$WORK" "$FIX/run.json" >/dev/null
cp "$WORK/seen.json" "$WORK/seen.json.bak"
rm "$WORK/seen.json"
if out="$(tri "$WORK" "$FIX/run.json" 2>&1)"; then
  fail "recovery: a surviving .bak with no seen.json should stop the run"
  printf '%s\n' "$out" >&2
else
  pass "recovery: refuses to start fresh while a .bak survives"
fi
if grep -q "seen.json.bak" <<<"$out"; then
  pass "recovery: the message names the file to restore"
else
  fail "recovery: the message does not say how to recover"
fi
rm -rf "$WORK"

# --------------------------------------------------------------------------
# 12. A listing whose permalink could not be read is still addressable
#     references/facebook-groups.md tells the agent to write post_id: null.
# --------------------------------------------------------------------------
WORK="$(new_work)"
python3 - "$FIX/run.json" "$WORK/nopermalink.json" <<'PY'
import json, sys
run = json.load(open(sys.argv[1]))
post = run["posts"][0]
post["post_id"] = None
post["url"] = None
run["posts"] = [post]
json.dump(run, open(sys.argv[2], "w"))
PY
tri "$WORK" "$WORK/nopermalink.json" >/dev/null
synthetic="$(python3 -c "
import json,sys
seen=json.load(open(sys.argv[1]))
print(seen['posts'][-1]['post_ids'][0])" "$WORK/seen.json")"
case "$synthetic" in
  fp:*) pass "no-permalink: got a stable synthetic id ($synthetic)" ;;
  *) fail "no-permalink: expected an fp: id, got '$synthetic'" ;;
esac

if run verdict "$WORK" "$synthetic" rejected --reason "no permalink" >/dev/null 2>&1; then
  pass "no-permalink: the listing can still be given a verdict"
else
  fail "no-permalink: the listing is unreachable — it can never be rejected"
fi
rm -rf "$WORK"

# --------------------------------------------------------------------------
# 13. --seen pointed at a missing directory fails cleanly, not with a traceback
# --------------------------------------------------------------------------
WORK="$(new_work)"
out="$(tri "$WORK" "$FIX/run.json" --seen /nonexistent/xyz/seen.json 2>&1)"
rc=$?
if [ "$rc" -ne 0 ] && ! grep -q "Traceback" <<<"$out"; then
  pass "seen-path: a missing directory is a clean error"
else
  fail "seen-path: expected a clean non-zero exit"; printf '%s\n' "$out" >&2
fi
rm -rf "$WORK"

# --------------------------------------------------------------------------
# 14. The date window, and post_kind
#     A listing can satisfy every duration rule and still be useless because
#     it is free at the wrong time. This is the check that catches that.
# --------------------------------------------------------------------------
WORK="$(new_work)"
WINDOW=(--need-from 2026-08-15 --need-until 2026-12-05)
out="$(run triage "$WORK" "$FIX/run-dates.json" "${WINDOW[@]}" --dry-run)"

# Overlaps by 6 days, so it fails on coverage rather than on the start date.
# Either way it must not outrank a listing that covers the whole window.
if grep -q "only covers 6d of your window" <<<"$out"; then
  pass "dates: a let overlapping by days is failed, not ranked first"
else
  fail "dates: the wrong-window listing was not flagged"; printf '%s\n' "$out" >&2
fi

if grep -q "ends 31 Jul, before you arrive" <<<"$out"; then
  pass "dates: a let ending before the window is failed"
else
  fail "dates: the already-gone listing was not flagged"; printf '%s\n' "$out" >&2
fi

if grep -q "covers 1 Oct–5 Dec of your window" <<<"$out"; then
  pass "dates: partial cover warns with the dates it actually covers"
else
  fail "dates: partial cover was not reported"; printf '%s\n' "$out" >&2
fi

# The full-cover listing is the only one with no flag at all, so it must sort
# first. Row 3 of the output is the first data row.
first_row="$(grep '^|' <<<"$out" | sed -n '3p')"
if grep -q "1\.700" <<<"$first_row"; then
  pass "dates: the listing covering the whole window ranks first"
else
  fail "dates: wrong listing ranked first: $first_row"
fi

if grep -q "2 not listings (people looking)" <<<"$out"; then
  pass "post_kind: wanted and other are counted, not tabled"
else
  fail "post_kind: the not-a-listing count is wrong"; printf '%s\n' "$out" >&2
fi

if ! grep -q "Hopeful Tenant\|Lead Farm" <<<"$out"; then
  pass "post_kind: no house-hunter appears in the table"
else
  fail "post_kind: a wanted post reached the table"; printf '%s\n' "$out" >&2
fi

# Recorded, so the next run does not spend effort re-reading them.
run triage "$WORK" "$FIX/run-dates.json" "${WINDOW[@]}" >/dev/null
if python3 - "$WORK/seen.json" <<'PY'
import json, sys
posts = json.load(open(sys.argv[1]))["posts"]
wanted = [p for p in posts if p.get("verdict") == "not_a_listing"]
sys.exit(0 if len(wanted) == 2 else 1)
PY
then
  pass "post_kind: both are stored as not_a_listing"
else
  fail "post_kind: not_a_listing records missing from seen.json"
fi

out="$(run triage "$WORK" "$FIX/run-dates.json" "${WINDOW[@]}" --dry-run)"
if grep -q "0 new, 6 already seen" <<<"$out"; then
  pass "post_kind: a re-run re-reads none of them"
else
  fail "post_kind: re-run did not treat all six as seen"; printf '%s\n' "$out" >&2
fi

# Switching the window off must restore the old behaviour exactly.
out="$(tri "$WORK" "$FIX/run-dates.json" --dry-run)"
if ! grep -qE "after you leave|before you arrive|of your window" <<<"$out"; then
  pass "dates: an empty --need-from disables the check"
else
  fail "dates: the check still ran with no window given"; printf '%s\n' "$out" >&2
fi

if run triage "$WORK" "$FIX/run.json" --need-from 2026-12-01 --need-until 2026-08-01 >/dev/null 2>&1; then
  fail "dates: a reversed window should be an error"
else
  pass "dates: a reversed window is refused"
fi

if run triage "$WORK" "$FIX/run.json" --need-from "next tuesday" >/dev/null 2>&1; then
  fail "dates: an unparseable date should be an error"
else
  pass "dates: an unparseable date is refused"
fi
rm -rf "$WORK"

exit "$status"
