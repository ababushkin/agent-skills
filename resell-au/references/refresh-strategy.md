# Refresh strategy

When the user runs `/resell-au refresh <folder>`, the skill enters
**Refresh Mode** — a third top-level mode alongside Text Mode and
Folder Mode. Refresh Mode delete-and-relists stale FB Marketplace
listings to reset the FB algorithm's "honeymoon" visibility window.

This file is the single home for refresh-only reference detail. Each
sub-task in the parent design (ABA-152) appends its phase here:

| Phase | What it does | Status |
|---|---|---|
| R0 | Discovery & classification (read-only) | Sub-task #1 — **this file's current scope** |
| R1 | Delete existing listing on FB | Sub-task #2 |
| R2 | Recreate at new price | Sub-task #3 + #4 |
| R3 | Summary | Sub-task #6 |

When a later sub-task fires, append its phase to this file rather than
inflating `SKILL.md` — the top-level skill index should stay light.

## Why delete-and-relist

FB Marketplace gives every new listing a 24–48 hour "honeymoon" of
aggressive feed visibility. After a few days, visibility drops sharply.
The established reseller tactic — confirmed across 2024–2026
reseller-community research — is to **delete the stale listing and
recreate it with a fresh price.** Empirically this produces a ~30%
message-rate lift vs the native "Renew" button.

Trade-off: deleting loses **saves, chat history, and view count.** The
skill prints a one-line data-loss warning at the top of Phase R0 so
the user is reminded before confirming the candidate table.

## Phase R0 — discovery & classification

Phase R0 is read-only: walk the target folder, parse each subfolder's
`listing.md`, and produce a candidate table. No browser actions in
this phase other than the existing Chrome login check from Folder Mode
Phase 0.

### Trigger

```
/resell-au refresh <folder>
```

If no folder is given, default to `~/Desktop/things-for-sale/`.

### Classification rules

For each subfolder (skip names starting with `.` or `_`):

| Condition | Classification | In table? |
|---|---|---|
| no `listing.md` | `not-published` | silent skip |
| `**Status:** Sold` | `sold` | silent skip |
| `**Status:** Published` + `**Date:**` ≥ 7 days old + `**URL:**` present | `refresh-eligible` | yes |
| `**Status:** Published` + `**Date:**` < 7 days old | `too-fresh` | yes, action = "too-fresh, skip" |
| `**Status:** Published` + no `**URL:**` line | `no-url` | yes, action = "no URL — paste required" |

Silent skips are surfaced as a count summary above the candidate table
("Silently skipped: N items") so the operator can spot-check that the
right things were ignored.

### Parser contracts

`listing.md`'s canonical format is produced by Folder Mode Phase 4.
The Phase R0 classifier uses **strict regex contracts** — anything
that does not match is treated as missing rather than guessed at. The
worst classification error is a false-positive `refresh-eligible` that
deletes a wrong listing, so the parser errs on the side of "skip".

| Field | Regex | Source line |
|---|---|---|
| Status | `^\*\*Status:\*\*\s+(\S+)` | `**Status:** Published` |
| Date | `^\*\*Date:\*\*\s+(\d{4}-\d{2}-\d{2})` | `**Date:** 2026-05-21` |
| URL | `^\*\*URL:\*\*\s+(\S+)` | `**URL:** https://www.facebook.com/marketplace/item/...` |
| Price | `^\*\*Price:\*\*\s+\$(\d+)` | `**Price:** $140 ono` |
| Floor | `Floor:\s*\$(\d+)` | `- Target: ~$130 | Floor: $110 | Garage sale: $70` |

Date format is **ISO `YYYY-MM-DD` only.** Anything else means the file
was hand-edited and is classified as `not-published` (silent skip).

### Proposed-price preview

For `refresh-eligible` and `no-url` items, R0 previews the proposed
new price using the **default rule** — `−10% clamp-to-floor`, rounded
with the seller-rounding rules from the Pricing model. The full
price-drop calculator (per-item `same` / `$X` override, bulk override,
floor gate) lives in Sub-task #4 (ABA-156). R0 just shows the default.

If `Floor:` is absent from seller notes, the floor falls back to
`list_price × 0.85` (matches Pricing model § 5). The clamp still
holds.

For `too-fresh` rows, the table shows `—` for proposed price and
floor — no decision is being made on these items this session.

### Session cap (5 per session)

If more than 5 items are `refresh-eligible`:
* Sort by age (oldest first).
* Take the oldest 5 as the queued set.
* Show the rest under `deferred to next session` in the table, with
  a count summary in the "### Deferred to next session" section.

The cap is FB rate-limit hygiene — bursts >5 refreshes/hour are the
shadowban signal in reseller-community data. Re-run the skill after
≥30 minutes to drain the deferred set.

### `no-url` interaction

When an item is classified `no-url`, the skill prompts the user to
paste the listing's FB URL during Phase R0. **The paste is in-memory
for the current session only — never written back to `listing.md`.**

If the user wants the URL persisted, they need to add the `**URL:**`
line manually. A missing URL line in the file is the signal that
capture failed at publish time (consistent with the Folder Mode
Phase 4 Step 6 rule: omit rather than write a placeholder).

### Re-running is identical (no side effects)

Phase R0 writes nothing. Re-running on the same folder on the same
day, with the same listings, produces the same table. This is the
hand-test invariant for the slice.

## Output: the candidate table

```
⚠️  Refresh = delete + relist on FB Marketplace.
    DELETE LOSES: saves, chat history, view count.
    This is the established tactic for resetting the FB algorithm; the loss is the price.

Found 10 items: 5 queued, 1 deferred, 1 no-url, 1 too-fresh, 2 silently skipped (sold or no listing.md).

## Candidate table

| Item | Age | Current | Proposed | Floor | Action |
|------|-----|---------|----------|-------|--------|
| eligible-60d | 60d | $50 | $45 | $35 | refresh |
| eligible-30d | 30d | $100 | $90 | $70 | refresh |
| ...
| too-fresh-3d | 3d | $40 | — | — | too-fresh, skip |
| eligible-8d | 8d | $25 | $22 | $20 | deferred to next session |

### Deferred to next session (1 item)
Rate-limit hygiene caps refresh at 5 per session.
Re-run `/resell-au refresh ...` after ≥30 minutes to drain the queue.
```

The data-loss warning prints **exactly once per session** — the start
of Phase R0, above the table. Each `/resell-au refresh ...` invocation
is one session; subsequent invocations re-print it.

## Running the classifier

The R0 classifier is implemented as a Python script so the parsing is
deterministic and regression-testable. Invoke it directly rather than
re-implementing the rules inline — the script is the single source of
truth for what counts as `refresh-eligible`.

```bash
python3 <skill_dir>/scripts/refresh_r0_classify.py <target_folder>
```

For deterministic fixture testing, set `REFRESH_R0_TODAY=YYYY-MM-DD`
to override the "today" date so age classifications stay stable across
runs.

## Test fixture

A deterministic fixture covering all 5 buckets plus the session-cap
deferral case lives at `tests/fixtures/refresh-r0/`. After any change
to the classifier, run the verification script:

```bash
bash <skill_dir>/tests/check_refresh_r0.sh
```

The script runs the classifier against the fixture with
`REFRESH_R0_TODAY=2026-05-21` locked, then diffs the output against
`fixtures/refresh-r0.golden.txt`. Exit 0 = pass; non-zero = the
classifier's behaviour changed and the golden file needs review before
updating.

The fixture is parser-correctness only. End-to-end verification — the
real eval for the slice — is a hand-run against `~/Desktop/things-for-sale/`
with the classification table sanity-checked against what the operator
expects to see.
