# Refresh strategy

When the user runs `/resell-au refresh <folder>`, the skill enters
**Refresh Mode** — a third top-level mode alongside Text Mode and
Folder Mode. Refresh Mode delete-and-relists stale FB Marketplace
listings to reset the FB algorithm's "honeymoon" visibility window.

This file is the single home for refresh-only reference detail. Phase
index (all sections live below):

| Phase | What it does | Where to read |
|---|---|---|
| R0 | Discovery & classification (read-only) — candidate table, session cap, floor gate | § "Phase R0 — discovery & classification" |
| R1 | Delete existing listing on FB | `browser-automation.md` § "Refresh Mode — Phase R1 delete loop"; locators in `facebook-marketplace.md` § "Delete listing locators" |
| R2 | Recreate at new price + update `listing.md` | § "Phase R2 — recreate at new price"; scripts: `refresh_listing_md_update.py`, `refresh_pricing.py` |
| Multi-item loop | Session cap, inter-item delays, resume on restart | § "Phase R1+R2 multi-item loop"; script: `refresh_runstate.py` |
| R3 | Summary table | § "Phase R3 — summary output" |

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

The live-price override runs **before** the floor gate. It updates
the "current price" the calculator sees, in-memory only — `listing.md`
is never written back. Sequence:

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

## Phase R2 — recreate at new price

Phase R2 runs after R1 has confirmed deletion for the current item
(`status: deleted` in the run-state JSON, `delete_detection`
populated). One item at a time — multi-item batching and resume
semantics are documented in § "Phase R1+R2 multi-item loop". The
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
Steps 1 through 6 verbatim (including Step 6b). The outcome is one of:

- `post_publish_detection: "url_match"` — new listing URL captured
  directly from the post-publish redirect.
- `post_publish_detection: "iframe_extract"` — the publish landed on the
  your-listings page or timed out, and Step 6b recovered the real URL from
  the Selling-page ad-preview iframe (verified by exact title match).
- `post_publish_detection: "your_listings_redirect"` or
  `"timeout_manual"` — Publish click landed, but neither the polling loop
  nor the Step 6b iframe recovery captured the URL. Ask the operator to
  paste it, same flow as Phase 4 Step 6.

If the recreate fails at any step (snapshot mismatch, captcha,
publish timeout with no URL pasted by the operator):

- **Do NOT touch `listing.md`.** Leaving it alone means the next
  run sees this item as `no-url` (since no URL was captured) and the
  operator can hand-fix or retry — the multi-item loop's resume
  contract picks up from this state.
- Update the run-state JSON to `status: deleted` (not `recreated`)
  and populate `failure_reason` with a short string. The multi-item
  loop then surfaces the item as `action: manual` on the next
  `plan` call.

### Step R2.3 — update listing.md

When a new URL is available (from `url_match`, `iframe_extract`, or
operator paste), run the updater:

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

## Phase R1+R2 multi-item loop

After R0 produces the queued set (up to 5 items, oldest-first) and
the operator confirms the floor gate, the skill runs R1 then R2 for
each queued item in order, with **30–90 s human-cadence delays**
between items. The loop is driven off the Refresh Mode run-state
JSON file, which is **the single source of truth** for what each
item's next action is — both for the in-session loop and for
resuming after a crash, `/compact`, or the user killing the session.

The orchestration script is `scripts/refresh_runstate.py`. It has
three subcommands; the agent's loop is built on `init` (start or
resume), `plan` (what's next), `update` (record the result).

### Step M0 — init or resume the run-state file

After the floor gate, build a queued items array and pass it to
`init`. The script's behaviour is the resume contract:

```bash
# JSON file with one object per queued item — see schema below.
python3 <skill_dir>/scripts/refresh_runstate.py init <target_folder> \
    --queued-json /tmp/queued.json
```

| Folder state | What init does |
|---|---|
| No `.resell-au-refresh-*.json` in folder | Create a new file `<folder>/.resell-au-refresh-<YYYYMMDD-HHMM>.json` seeded from `--queued-json`. Print its path. |
| Latest file has any item in `pending`, `deleted`, or `failed` | **Resume** — print the existing file's path, ignore `--queued-json`. This is the load-bearing rule for the "kill mid-flight + restart" path. |
| Latest file has all items in `recreated` / `skipped` | Treat as new run — create a new file from `--queued-json`. (The drained-queue-then-add-more case.) |
| Latest file unreadable (JSON corrupted) | Exit non-zero. Do not silently overwrite — the operator may want to recover it. |

**The same run-state file is updated in place across resumes.** A
restart never produces a new timestamped file — `init` returns the
existing path, the loop continues mutating it.

The queued-item JSON shape (the agent assembles this from R0's
classified set + the floor-gate-resolved prices, then feeds it to
init):

```json
[
  {
    "subfolder": "kettlebell",
    "title": "12kg Kettlebell — like new",
    "old_url": "https://www.facebook.com/marketplace/item/111/",
    "old_price": 45,
    "new_price": 40,
    "floor": 35,
    "age_days": 12,
    "refresh_count_before": 0
  }
]
```

`refresh_count_before` is optional (defaults to 0) and informational
only — the listing.md updater derives the canonical refresh number
from existing `## Refresh history` bullets in the file, so this
field doesn't need to be accurate.

### Step M1 — defer-notice before R1 starts

Before the first R1 begins, print the defer notice **exactly once**
per session, naming the deferred items so the operator knows what
will be left over. R0 already shows the deferred set in the
candidate table; this is the "confirming what I'm about to do"
message at the start of execution:

```
Processing 5 items this session. Deferred to next session
(≥30 min from now): eligible-8d, eligible-9d.
Re-run `/resell-au refresh <folder>` after the cooldown to drain them.
```

If zero items are deferred, skip the message entirely — no value
in noise.

### Step M2 — loop on `plan` until no `r1`/`r2` actions remain

Each iteration calls `plan`, which emits one JSON object per item
(newline-delimited) with a `status` and a derived `action`:

```bash
python3 <skill_dir>/scripts/refresh_runstate.py plan <runstate_path>
```

| `status` in run-state | `action` from plan | Loop branches to |
|---|---|---|
| `pending` | `r1` | R1 delete loop in `browser-automation.md` → on success, `update --status deleted`; on confirmed deletion failure, `update --status failed` |
| `deleted` | `r2` | R2 recreate (§ "Phase R2 — recreate at new price" above) — **do NOT re-run R1**, the old listing is already gone (would 404) |
| `recreated` | `done` | Skip — item already finished in this run-state |
| `skipped` | `done` | Skip — operator-decided terminal |
| `failed` | `manual` | Surface the item + `failure_reason` to the operator; do not auto-retry. Operator can edit the run-state file by hand or re-run R0 once the underlying issue is fixed. |

Take the first item whose action is `r1` or `r2`, run that phase,
update the run-state, then sleep 30–90 s (random) using
`run_in_background: true` on a Bash `sleep` — same pattern as Phase
4 Step 7 / R1.8. After the sleep, re-run `plan` and continue.
The loop terminates when no items have action `r1` or `r2` left.

The per-item delay applies between **items**, not between R1 and R2
of the same item — R1 hands directly to R2 once deletion is
confirmed, with no inter-phase delay (per the Phase R2 pre-condition
that the delete confirmation be recent and unambiguous).

### Step M3 — update after each phase

After a phase resolves, write the result back:

```bash
# Successful deletion.
python3 <skill_dir>/scripts/refresh_runstate.py update <runstate_path> \
    --item 0 --status deleted --delete-detection redirect

# Successful recreate.
python3 <skill_dir>/scripts/refresh_runstate.py update <runstate_path> \
    --item 0 --status recreated --new-url "https://www.facebook.com/marketplace/item/222/"

# Confirmed failure (e.g. deletion timeout, operator picked "continue" to skip).
python3 <skill_dir>/scripts/refresh_runstate.py update <runstate_path> \
    --item 0 --status failed --failure-reason "delete timeout — operator skipped"
```

`update` is atomic (temp + rename) so a kill mid-write can't
corrupt the file. The corresponding `*_at` field
(`pending_at` / `deleted_at` / `recreated_at` / `skipped_at` /
`failed_at`) is auto-stamped on every status transition —
`pending_at` is stamped by `init` at creation time. The
timestamps let the operator verify the 30–90 s inter-item gap
from the file alone, no shell history needed.

### Resume in practice

Headline scenario: kill the run after item 0 is `deleted` but before
`recreated`, re-invoke `/resell-au refresh <folder>`. The skill then:

1. Calls `init <folder>` (no `--queued-json` needed) — picks up
   the existing `.resell-au-refresh-…json`.
2. Calls `plan` — item 0 has `action: r2` (resume from recreate;
   the old listing is already gone), items 1+ have `action: r1`.
3. Runs R2 for item 0 first (no R1 re-run, no 404 risk), then
   R1+R2 for the rest, with 30–90 s gaps between items.
4. The same run-state file ends up with every item at `recreated`
   — **never a new file per resume**.

## Refresh Mode run-state file

Written to `<target_folder>/.resell-au-refresh-<YYYYMMDD-HHMM>.json`
by `scripts/refresh_runstate.py init` at the start of the R1+R2
loop. Refresh runs use a separate file from Folder Mode runs because
the per-item shape differs (no comp block, no platforms map —
refresh is single-platform, single-action).

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
      "new_price": 40,
      "floor": 35,
      "age_days": 12,
      "refresh_count_before": 0,
      "status": "pending | deleted | recreated | failed | skipped",
      "delete_detection": "redirect | listing_gone_copy | row_missing | timeout_manual | null",
      "new_url": "https://www.facebook.com/marketplace/item/222/ | null",
      "failure_reason": "string | null",
      "pending_at": "ISO 8601 | null",
      "deleted_at": "ISO 8601 | null",
      "recreated_at": "ISO 8601 | null",
      "skipped_at": "ISO 8601 | null",
      "failed_at": "ISO 8601 | null"
    }
  ]
}
```

Resume semantics:

| Terminal state | Meaning |
|---|---|
| `pending` | Not started — R1 has not yet deleted. Resume from R1. |
| `deleted` | R1 succeeded but R2 did not capture a new URL. Resume from R2 — the OLD listing is already gone. Do not re-run R1 (would 404). |
| `recreated` | R2 succeeded, `listing.md` updated. Item is done. |
| `skipped` | Operator-decided skip (e.g. unrecoverable mismatch). Do not retry. |
| `failed` | Phase failed and operator has not yet decided next step. Re-running `init` will resume the file; `plan` surfaces these as `action: manual` so the operator chooses (edit run-state by hand, or fix the underlying issue and re-run). |

The `pending_at` / `deleted_at` / `recreated_at` / `skipped_at` /
`failed_at` fields are auto-stamped by
`scripts/refresh_runstate.py` — `pending_at` at `init` time,
the rest on each `update` call. The inter-item-delay
verification (each item-to-item gap between 30 and 90 s) works
off the file alone — no shell history needed.

`session_cap` is written into the run-state at `init` for
observability (it tells anyone inspecting the file "this run was
capped at 5"). The cap is enforced in two places: upstream in
`refresh_r0_classify.py` (trims eligible items to `SESSION_CAP`
before writing `--queued-json`), and defensively in
`refresh_runstate.py init` (refuses `--queued-json` arrays longer
than `SESSION_CAP` with a non-zero exit). The double enforcement
guards against an R0 regression silently passing too many items to
the loop. `refresh_count_before` is similarly informational; the
listing.md updater derives the canonical refresh number from
existing `## Refresh history` bullets in the file rather than
trusting this field.

## Phase R3 — summary output

After the multi-item loop drains (every queued item has terminal
status `recreated` / `failed` / `skipped`), Phase R3 reads the
run-state JSON and prints one summary block to the user. R3 is
read-only: no further `listing.md` updates, no browser actions.

### Output format

```
## Refresh summary

5 items processed: 4 refreshed, 0 skipped, 1 failed.

| Item | Status | Detail |
|------|--------|--------|
| kettlebell | refreshed | $45 → $40 — https://www.facebook.com/marketplace/item/222/ (was 111) |
| ikea-rugs  | refreshed | $40 → $35 — https://www.facebook.com/marketplace/item/444/ (was 333) |
| violin     | refreshed | $100 → $90 — https://www.facebook.com/marketplace/item/666/ (was 555) |
| bookshelf  | refreshed | $80 → $72 — https://www.facebook.com/marketplace/item/888/ (was 777) |
| chair      | failed    | delete timeout — operator skipped |

Deferred to next session (2 items, re-run after ≥30 min):
- couch (10d)
- mirror (8d)
```

### Per-row composition

| Run-state `status` | Row "Status" | Row "Detail" |
|---|---|---|
| `recreated` | `refreshed` | `$<old_price> → $<new_price> — <new_url> (was <old_id>)` where `<old_id>` is the digits in `old_url` between `/marketplace/item/` and the trailing `/` |
| `skipped` | `skipped` | `failure_reason` verbatim (operator-typed at the stop-the-line `continue` prompt) |
| `failed` | `failed` | `failure_reason` verbatim |
| `pending` / `deleted` | — | should not appear at R3 — loop only exits on terminal states. If present, the loop terminated abnormally; surface a stop-the-line message instead of the summary table |

### Deferred section

The R0-classified items that were over the 5-per-session cap are not
in the run-state JSON (only the queued 5 are). R3 sources them from
the R0 classifier output retained in memory for the session. Format
is `<subfolder> (<age_days>d)` per line, sorted oldest-first to
match R0's queueing order.

If zero items were deferred, **omit the entire `Deferred to next
session` section** — no value in printing empty noise.

### Total processed count

Header counts come from the run-state items array — total = items in
the run-state (not including R0-deferred items). The sum of
refreshed + skipped + failed equals total processed.

## Tests and fixtures

All scripts ship with deterministic fixtures or unit tests so the
contracts above are regression-checked. Run after touching the
matching script.

| Script | Tests | Invocation | Env override |
|---|---|---|---|
| `refresh_r0_classify.py` | `tests/fixtures/refresh-r0/` (golden diff covering all 5 buckets + cap deferral) | `bash tests/check_refresh_r0.sh` | `REFRESH_R0_TODAY=YYYY-MM-DD` |
| `refresh_listing_md_update.py` | `tests/fixtures/refresh-r2/` (3 cases: first-refresh-with-comps, second-refresh, no-url-no-comps) | `bash tests/check_refresh_r2.sh` | `REFRESH_R2_TODAY=YYYY-MM-DD` |
| `refresh_pricing.py` | `tests/test_refresh_pricing.py` (unittest: acceptance cases, per-item + bulk overrides, rounding bands, absent-floor fallback) | `bash tests/check_refresh_pricing.sh` | — |
| `refresh_runstate.py` | `tests/test_refresh_runstate.py` (unittest: status-action mapping, `*_at` auto-stamp, find-latest, filename format, init CLI integration) | `bash tests/check_refresh_runstate.sh` | `REFRESH_RUNSTATE_NOW=YYYY-MM-DDTHH:MM:SS` |

The fixtures are parser-correctness only. End-to-end verification —
the real eval — is a hand-run against `~/Desktop/things-for-sale/`
with the candidate table and summary table sanity-checked against
what the operator expects.
