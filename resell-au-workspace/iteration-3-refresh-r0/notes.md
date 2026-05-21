# Iteration 3 — Refresh Mode Phase R0 (ABA-153)

Per the parent ABA-152's authoring approach: capture before/after
notes per sub-task. This is the first refresh slice — Phase R0
(read-only discovery & classification).

## What was built

* `scripts/refresh_r0_classify.py` — Phase R0 classifier as a Python
  script. Walks subfolders, parses each `listing.md` against strict
  regex contracts, classifies into 5 buckets, applies the 5-per-session
  cap, and prints the candidate table with a one-line data-loss
  warning.
* `references/refresh-strategy.md` — single home for Refresh Mode
  reference detail. Created in this slice (re-shape vs ABA-152's
  original plan which had it land in Sub-task #6) so subsequent
  sub-tasks can append phases here rather than ballooning SKILL.md.
* `SKILL.md` — intro updated from "two modes" to "three modes";
  high-level Refresh Mode workflow section added before Pricing model
  (~80 new lines); reference-file entry pointing at
  `refresh-strategy.md`.
* `tests/fixtures/refresh-r0/` — 10-subfolder deterministic fixture
  covering all 5 buckets plus the session-cap deferral case (6 eligible
  → 5 queued + 1 deferred). Date math locked via
  `REFRESH_R0_TODAY=2026-05-21`.
* `tests/fixtures/refresh-r0.golden.txt` — expected classifier output.
* `tests/check_refresh_r0.sh` — diffs classifier output against golden.

## Re-shape decisions (from skill-creator sanity check)

1. **Created `references/refresh-strategy.md` in this slice**, not in
   Sub-task #6 as originally planned. Reason: SKILL.md was already 559
   lines (past the 500-line skill-creator target). Letting Refresh
   detail balloon SKILL.md until #6 finally extracts it would mean
   re-editing an unwieldy file four times. Sub-task #6 (ABA-158) scope
   narrows to: hygiene-rules wording, Phase R3 summary, cold-read pass.
2. **Implemented classifier as a Python script**, not inline agent
   parsing. Trade-off: adds Python script dependency to the skill (it
   had none before, only `python3 -c "..."` one-liners). Reasoning:
   classification is deterministic + repetitive; a script makes
   parser correctness regression-testable for Sub-tasks #2–#6 at near-
   zero ongoing cost. Matches the parent design's expectation that
   `scripts/refresh_pricing.py` may emerge from Sub-task #4 if the
   price-drop calculator turns out deterministic.

## Spec tightenings (added to acceptance criteria)

1. **Date format strictness.** `**Date:**` parser is ISO `YYYY-MM-DD`
   only; non-matches treated as missing (silently skipped). Matches
   Folder Mode Phase 4 writer.
2. **Floor parser regex.** `Floor:\s*\$(\d+)` against the seller-notes
   composite line. Absent Floor → fall back to `list_price × 0.85`.
3. **`no-url` interaction.** Paste captured in-memory for this session
   only; never written back to `listing.md`. A missing `**URL:**` line
   is the signal that capture failed at publish — consistent with
   Folder Mode Phase 4 Step 6.
4. **Fixture readiness for hand-test.** `~/Desktop/things-for-sale/`'s
   recent smoke-test items are 1–3 days old → all classify
   `too-fresh`. To exercise `refresh-eligible` for hand-test, copy one
   listing.md to a temp folder and bump its `**Date:**` to a ≥7d-old
   value.

## Hand-test against ~/Desktop/things-for-sale/

Ran with `REFRESH_R0_TODAY=2026-05-21`. Result:

```
Found 42 items: 0 queued, 0 deferred, 5 no-url, 37 too-fresh, 0 silently skipped.
```

Observations:

* **5 no-url items** (all 7d old) — these are from an earlier smoke
  test pre-dating the URL-poll fix (commit 3074cce, "poll URL after
  Publish instead of broken wait_for"). The classifier correctly
  identifies them and the user can paste URLs interactively in Phase R0.
* **37 too-fresh items** — recent smoke-test results from 2026-05-18
  through 2026-05-20. Classifier correctly skips them.
* **0 refresh-eligible items** — no listings >7d old that also have a
  URL. To exercise this bucket against real-world data, I copied
  `breville-fast-slow-pro-pressure-cooker-bpr700` to a temp folder,
  bumped its `**Date:**` to 2026-04-21 (30d old), and added a fake
  `**URL:**` line. The classifier correctly identified it as
  `refresh-eligible` with proposed $145 → $130 (floor $120). Temp
  folder cleaned up.
* **One real-world edge case caught**: `ozito-1100w-belt-sander-bsg-151`
  has current price $30 but Floor: $50. The classifier proposes $50
  (clamp-to-floor wins over −10% drop). Refresh would *increase* the
  listing price. This is correct behaviour for an item priced below
  floor (likely a "gone today" strategy override that didn't sell);
  the user can choose to skip at table-review time. Future
  enhancement: flag `proposed > current` rows in the table — not in
  AC for this slice.
* **Re-run identical, no side effects** ✓ — confirmed via diff of two
  back-to-back invocations.

## Acceptance criteria — verification

* ✅ `**Status:** Published` + Date ≥7d + URL present → `refresh-eligible`
  (verified via temp-copy of real breville listing).
* ✅ `**Date:**` <7d → `too-fresh`, proposed shows `—`
  (37 real items in the actual folder).
* ✅ `**Status:** Published` + no `**URL:**` → `no-url`, prompt for paste
  (5 real items in the actual folder).
* ✅ `**Status:** Sold` or no `listing.md` → silently skipped
  (fixture: `sold-item/` + `not-published-folder/`).
* ✅ Data-loss warning prints exactly once per session above the table.
* ✅ >5 refresh-eligible → oldest 5 queued, rest under "Deferred to
  next session" (fixture: 6 eligible → 5 queued + 1 deferred).
* ✅ Re-running on same folder shows identical classification, no side
  effects (verified via diff of two real-folder runs).

## Regression check

```
bash /Users/anton/src/agent-skills/resell-au/tests/check_refresh_r0.sh
→ PASS: refresh R0 classifier matches golden.
```

Hand-off to Sub-task #2 (ABA-154): Phase R1 delete-listing browser
flow. R0 produces the confirmed queued set as a list of subfolder
names; R1 picks the first item by subfolder name and navigates to the
stored `**URL:**` to begin the delete sequence.
