# Refresh strategy

When the user runs `/resell-au refresh <folder>`, the skill enters
**Refresh Mode** — a third top-level mode alongside Text Mode and
Folder Mode. Refresh Mode delete-and-relists stale FB Marketplace
listings to reset the FB algorithm's "honeymoon" visibility window.

This file is the single home for refresh-only reference detail. Each
sub-task in the parent design (ABA-152) appends its phase here:

| Phase | What it does | Status |
|---|---|---|
| R0 | Discovery & classification (read-only) | Sub-task #1 ✓ + floor gate from Sub-task #4 ✓ |
| R1 | Delete existing listing on FB | Sub-task #2 ✓ — orchestration in `browser-automation.md` § "Refresh Mode — Phase R1 delete loop"; locators in `facebook-marketplace.md` § "Delete listing locators (Refresh Mode Phase R1)" |
| R2 | Recreate at new price | Sub-task #3 ✓ (constant price, one item) + Sub-task #4 ✓ wires the price-drop calculator in. Multi-item handling layers in via Sub-task #5. Orchestration in § "Phase R2 — recreate at new price" below; listing.md updater at `scripts/refresh_listing_md_update.py`; calculator at `scripts/refresh_pricing.py`. |
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
with the seller-rounding rules from the Pricing model. Both R0
preview and the Phase R2 final price flow through the same calculator
at `scripts/refresh_pricing.py` so the operator sees in R0 exactly
what gets posted in R2.

If `Floor:` is absent from seller notes, the floor falls back to
`list_price × 0.85` (matches Pricing model § 5). The clamp still
holds.

For `too-fresh` rows, the table shows `—` for proposed price and
floor — no decision is being made on these items this session.

The floor gate (next section) is where the operator confirms or
overrides the previewed price before Phase R1 runs.

### Session cap (5 per session)

If more than 5 items are `refresh-eligible`:
* Sort by age (oldest first).
* Take the oldest 5 as the queued set.
* Show the rest under `deferred to next session` in the table, with
  a count summary in the "### Deferred to next session" section.

The cap is FB rate-limit hygiene — bursts >5 refreshes/hour are the
shadowban signal in reseller-community data. Re-run the skill after
≥30 minutes to drain the deferred set.

### Floor gate (the operator-confirmation step)

After R0 prints the candidate table and the `no-url` paste pass
completes, the skill runs the **floor gate** before handing off to
Phase R1. The operator can accept all defaults, override per item, or
override in bulk.

**Per-item overrides** (one line per item, in any order):

| Operator input | Meaning |
|---|---|
| no response, or item not mentioned | accept the previewed `-10% clamp-to-floor` price |
| `<item>: same` | keep the current price (no drop) — useful when comps suggest the price is already right |
| `<item>: $X` | set the new price to `$X`, **still clamped to the floor** — operator's number overrides the calculator, the floor stays non-negotiable |

**Bulk overrides** (apply to every `refresh-eligible` item in the queued
set, not the deferred ones):

| Operator input | Meaning |
|---|---|
| `drop everything N%` | apply `−N%` instead of the default `−10%`, then clamp each item to its own floor |
| `keep all prices` | equivalent to `drop everything 0%` — recreate every item at its current price |

Resolution order when both kinds of input arrive:

1. Apply the bulk rate first (sets the new baseline for every item).
2. Apply per-item overrides on top (a per-item `$X` wins over the bulk rate; `same` wins over the bulk rate too).
3. Clamp every result to its floor as the last step — the floor is the only invariant the operator cannot override.

Operationally the calculator is one function call per item via
`scripts/refresh_pricing.py`:

```python
proposed_price(current, floor, drop_rate=0.10)   # default
proposed_price(current, floor, drop_rate=0.15)   # "drop everything 15%"
proposed_price(current, floor, drop_rate=0.0)    # "same" / "keep all prices"
clamp_to_floor(x, floor, current)                # per-item "$X" override
```

The CLI mirrors the Python API for shell-debug:

```bash
python3 <skill_dir>/scripts/refresh_pricing.py --current 40 --floor 35
# 35
python3 <skill_dir>/scripts/refresh_pricing.py --current 100 --floor 80 --drop 0.15
# 85
```

After the floor gate resolves, re-print the queued set as a
post-gate confirmation table — same columns, but the `Proposed`
column reflects the resolved prices and a new `Drop` column shows
the realised percentage (so the operator can spot floor-clamp
saves: `$40 → $35 (drop 12.5%, floor)`). The operator confirms once,
then Phase R1 begins.

### Interaction with the live-price override

The live-price override (already part of R0 from Sub-task #1) runs
**before** the floor gate. It updates the "current price" the
calculator sees, in-memory only — `listing.md` is never written
back. Sequence:

1. R0 classifier reads `**Price:**` from each `listing.md`. This is
   the *snapshot at publish time*, not always the live FB price.
2. Live-price override prompt: operator pastes `<item>: $X` per
   item where the live FB price has drifted from the snapshot.
3. Floor gate: defaults and overrides are computed against the
   live price from step 2, not the snapshot.

This ordering matters: an item published at $50, manually dropped
to $35 on FB, with floor $30, should refresh at `max(30, round(35 ×
0.9)) = max(30, round(31.5)) = $30` — not at `max(30, round(50 ×
0.9)) = $45`, which would be a *price increase*, the opposite of
what a refresh is for.

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

## Phase R2 — recreate at new price

Phase R2 runs after R1 has confirmed deletion for the current item
(`status: deleted` in the run-state JSON, `delete_detection`
populated). Still **one item at a time** — Sub-task #5 introduces
multi-item batching and the resume contract. As of Sub-task #4, the
recreate price comes from the R0 floor-gate resolution (default
−10% clamp-to-floor, with per-item and bulk overrides) rather than
the listing's snapshot.

R2 reuses Folder Mode Phase 4 Steps 1–6 verbatim — the recreate
form is the same `/marketplace/create/item` flow regardless of
whether it's a brand-new listing or a refresh. The only differences
are (a) **pre-fill data comes from `listing.md`** rather than from
Phase 1 photo-drafted output, and (b) on success, the `listing.md`
updater (`scripts/refresh_listing_md_update.py`) runs instead of the
Phase 4 writer.

### Pre-conditions

- Phase R1 ran on this item with terminal state `status: deleted`
  and `delete_detection ∈ {redirect, listing_gone_copy, row_missing}`.
  R2 must NOT run if deletion was unconfirmed
  (`delete_detection: "timeout_manual"`) — duplicate-listing risk is
  the whole reason R1 stop-the-lines.
- Recreate price (`new_price`) is decided by the R0 floor gate.
  `old_price` for the refresh-history bullet is the operator-confirmed
  live price (live-price override if provided, else `**Price:**`
  snapshot from `listing.md`). When the floor gate resolves to the
  same value as the live price (e.g. operator typed `same`, or
  `−10%` clamped exactly to floor and floor == current), `old_price`
  and `new_price` match and the bullet reads `$X → $X`.

### Step R2.1 — pre-fill the form payload from listing.md

Parse the item's `listing.md` for the recreate inputs:

| Phase 4 field | Source line in listing.md |
|---|---|
| Title | `**Title:**` in `## Ad copy` |
| Price | resolved `new_price` from the R0 floor gate (default `proposed_price(current, floor)`, per-item or bulk override applied) |
| Category | `**Category:**` in `## Ad copy` |
| Condition | `**Condition:**` in `## Ad copy` |
| Description | `**Description:**` body in `## Ad copy` |
| Location | `**Location:**` in `## Ad copy` |
| Photos | every image file in the item's subfolder, in lexical filename order |

Photos are not recorded in `listing.md` — they live on disk in the
same subfolder Folder Mode Phase 4 originally uploaded from, so a
lexical-order listing of `.jpg` / `.jpeg` / `.png` / `.heic` files
gives the same photo set. Cap 10 — same as Phase 4.

### Step R2.2 — drive the recreate (Phase 4 Steps 1–6)

Run `browser-automation.md` § "The loop (one item, one platform)"
Steps 1 through 6 verbatim. The outcome is one of:

- `post_publish_detection: "url_match"` — new listing URL captured.
- `post_publish_detection: "your_listings_redirect"` or
  `"timeout_manual"` — Publish click landed, but the URL wasn't
  captured by the polling loop. Ask the operator to paste it, same
  flow as Phase 4 Step 6.

If the recreate fails at any step (snapshot mismatch, captcha,
publish timeout with no URL pasted by the operator):

- **Do NOT touch `listing.md`.** Leaving it alone means the next
  run sees this item as `no-url` (since no URL was captured) and the
  operator can hand-fix or retry — the resumable state Sub-task #5
  picks up.
- Update the run-state JSON to `status: deleted` (not `recreated`)
  and populate `failure_reason` with a short string.
- Stop the session here. Multi-item batching is Sub-task #5.

### Step R2.3 — update listing.md

When a new URL is available (either from `url_match` or operator
paste), run the updater:

```bash
python3 <skill_dir>/scripts/refresh_listing_md_update.py \
    <item_subfolder>/listing.md \
    --old-url   "<old URL from run-state>" \
    --new-url   "<new URL>" \
    --age-days  <age_days from run-state> \
    --old-price <old_price from run-state> \
    --new-price <new_price from run-state>
```

`old_price` is the live-confirmed price the listing was running at
before the refresh; `new_price` is the floor-gate-resolved price the
recreate posted at. They differ when the drop took effect (typical
case) and match when the operator chose `same` or the floor clamp
caught a drop that would have been smaller than the rounding band.

The script (deterministic, byte-identical on Comps):

- Replaces `**URL:**` with the new URL (inserts the line after
  `**Platform:**` if absent — the `no-url` paste-in-R0 case).
- Replaces `**Date:**` with today (`REFRESH_R2_TODAY=YYYY-MM-DD`
  overrides for deterministic tests).
- Leaves `**Price:**` byte-identical.
- Creates or appends `## Refresh history` between `## Seller notes`
  and `## Comps`, adding one bullet:
  ```
  - YYYY-MM-DD (refresh #N): $X → $Y. Old URL: <old>. New URL: <new>. Age at refresh: Nd.
  ```
  The refresh number increments from any existing `(refresh #N)`
  bullet in the section.
- Refuses to write if the `## Comps` block (heading to end-of-file)
  is not byte-identical — internal safety guard against the
  refresh history insertion accidentally clobbering captured comp
  data.

Pass `--dry-run` to print to stdout instead of mutating the file
(used by the regression tests in `tests/check_refresh_r2.sh`).

### Step R2.4 — finalise run-state

On successful update:

```
status: recreated
new_url: <captured URL>
```

`delete_detection` was already populated by R1 and is carried
forward unchanged.

## Refresh Mode run-state file

Written to `<target_folder>/.resell-au-refresh-<YYYYMMDD-HHMM>.json`
when R2 picks up its item. Refresh runs use a separate file from
Folder Mode runs because the per-item shape differs (no comp block,
no platforms map — refresh is single-platform, single-action).

```json
{
  "run_started": "ISO 8601 timestamp",
  "target_folder": "/path/to/folder",
  "session_cap": 5,
  "items": [
    {
      "subfolder": "kettlebell",
      "title": "12kg Kettlebell — like new",
      "old_url": "https://www.facebook.com/marketplace/item/111/",
      "old_price": 45,
      "new_price": 45,
      "floor": 35,
      "age_days": 12,
      "refresh_count_before": 0,
      "status": "pending | deleted | recreated | failed | skipped",
      "delete_detection": "redirect | listing_gone_copy | row_missing | timeout_manual | null",
      "new_url": "https://www.facebook.com/marketplace/item/222/ | null",
      "failure_reason": "string | null"
    }
  ]
}
```

Resume semantics (mirrors Folder Mode):

| Terminal state | Meaning |
|---|---|
| `pending` | Not started — R1 has not yet deleted. Start from R1. |
| `deleted` | R1 succeeded but R2 did not capture a new URL. Resume from R2 — the OLD listing is already gone. Do not re-run R1 (would 404). |
| `recreated` | R2 succeeded, `listing.md` updated. Item is done. |
| `failed` / `skipped` | Operator-decided terminal states. Do not auto-retry; the operator chooses. |

The `deleted` row is the resumable state Sub-task #5 picks up. The
single-item slice never exercises multi-item resume, but the field
shape is fixed here so the resume logic has a stable contract to
build on.

## Test fixture (Phase R2 updater)

A deterministic fixture set covering the three updater invariants
lives at `tests/fixtures/refresh-r2/`:

| Case | Invariant |
|---|---|
| `case-1-full-with-comps` | First refresh on a complete `listing.md`: URL + Date replaced, Price unchanged, Refresh history section created, Comps block byte-identical. |
| `case-2-second-refresh` | A second refresh appends bullet `#2` (number auto-increments). Comps block stays byte-identical. |
| `case-3-no-url-no-comps` | `**URL:**` line inserted after `**Platform:**` (the post-`no-url`-paste case). Refresh history appended at end of file when no `## Comps` section exists. Omitting `--old-price`/`--new-price` produces a `price unchanged` bullet. |

Run after any change to `refresh_listing_md_update.py`:

```bash
bash <skill_dir>/tests/check_refresh_r2.sh
```

`REFRESH_R2_TODAY=2026-05-21` is locked inside the script so the
generated dates match the goldens.

## Test suite (price-drop calculator)

`scripts/refresh_pricing.py` is covered by `tests/test_refresh_pricing.py`
— a standard `unittest` module rather than a golden-file diff (the
calculator returns integers, not text). Cases:

| Class | What it pins |
|---|---|
| `AcceptanceCriteria` | The four worked examples from ABA-156 ($40/$35→$35, $40/$30→$35, $100/$80→$90, $25/$20→$23). |
| `PerItemOverrides` | `same` keeps current; `$X` passes through if ≥floor; `$X` clamps up if <floor; clamping uses the absent-floor fallback when needed. |
| `BulkOverride` | `drop everything 15%` shaves 15%; clamps to floor when the drop would breach it; `keep all prices` is `drop_rate=0.0`. |
| `RoundingBands` | Round-half-up at each band boundary (under $30, $30–$200, $200–$1000, $1000+). Guards the seller-rounding contract. |
| `AbsentFloorFallback` | `list_price × 0.85` fallback kicks in when `Floor:` is missing from seller notes. |
| `R0ClassifierGoldenStability` | Same inputs as `tests/fixtures/refresh-r0/` so a calculator change that would break the R0 golden gives a targeted failure first. |

Run after any change to `refresh_pricing.py` (or the R0 classifier,
since R0 now imports the calculator):

```bash
bash <skill_dir>/tests/check_refresh_pricing.sh
```
