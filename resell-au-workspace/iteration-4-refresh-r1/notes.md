# Iteration 4 — Refresh Mode Phase R1 (ABA-154)

Per the parent ABA-152's authoring approach: capture before/after
notes per sub-task. Sub-task #2 — Phase R1 delete-listing browser
flow (one item). The first action of this slice was exploratory
because the ⋯ menu / Delete-listing affordance was NOT pre-mapped.

## What was built

* `references/facebook-marketplace.md` — new § "Delete listing
  locators (Refresh Mode Phase R1)" with full label-driven selector
  patterns for: row-on-Selling-page locator, More-options menu,
  Delete confirm modal, second-stage "Did you sell?" radio, deletion-
  verification signals. Also captures the Renew menuitem locator for
  the future `--use-renew` variant.
* `references/browser-automation.md` — new § "Refresh Mode — Phase R1
  delete loop (one item)" with 8 step-by-step orchestration steps
  (R1.1 → R1.8). Stop-the-line table extended with two new rows:
  "Undetected deletion" and "Listing identity mismatch in delete-
  confirm modal".
* `references/refresh-strategy.md` — phase table updated: R0 ✓ → R1 ✓
  with pointers to the new sections.
* `SKILL.md` — Refresh Mode phase list expanded with the full R1
  summary (replaces the one-liner placeholder).

## Findings vs the parent design (ABA-152)

The parent design assumed:
> Navigate to the stored listing URL → snapshot → click ⋯ menu → click
> Delete listing → confirm dialog → poll for deletion signal.

Reality on the live FB Marketplace UI (captured 2026-05-21):

1. **No ⋯ menu on the listing detail page.** The seller's view of
   `/marketplace/item/<id>/` shows only `Edit`, `Share`,
   `Mark out of stock`, `Promote now`. There is no delete affordance
   on that page (see screenshot `01-listing-page.png`).
2. **No Delete button on the Edit page either.** Navigating to
   `/marketplace/edit/?listing_id=<id>` opens the listing form with
   only an `Update` button (see `02-edit-page-no-delete.png`).
3. **Delete lives only on the Your-Listings page**
   (`/marketplace/you/selling/`). Each listing row has a "More options
   for `<title>`" button (role: `button`, `expandable
   haspopup="dialog"`) that opens a menu containing `Delete listing`.
4. **The Selling page supports server-side title filtering** via
   `?title_search=<URL-encoded title>` — this is how Phase R1 locates
   the target row without scrolling through lazy-loaded chunks.
5. **Two-stage confirmation, not one.** After clicking the first
   "Delete" button in the confirm modal, FB shows a second dialog
   asking "Did you sell this item?" with four radio options before
   the deletion actually fires. The parent design did not anticipate
   this. Picked `"No, haven't sold"` as the truthful answer for
   refresh-mode (we are delisting due to staleness, not a sale —
   signalling a sale could affect FB's algorithmic treatment when
   we relist).
6. **Deletion signal is cleaner than the design expected.** Both
   `unavailable_product=1` redirect AND "no longer available" copy
   fire together; either is sufficient. The `unavailable_product=1`
   query param is the single cleanest test.
7. **Native Renew menuitem is present** alongside Delete in the
   "More options" menu, in disabled state until the 7-day cooldown
   elapses. Locator captured for the future `--use-renew` variant
   (deferred per parent design).

## Hand-run record

* **Target:** `kids-wooden-playing-blocks` ($15, 1d old, FB listing
  ID `1332595162113434`).
* **Staleness override:** The R0 classifier identified zero items
  with age ≥7d AND captured URL in `~/Desktop/things-for-sale/`.
  Hand-picked the lowest-value too-fresh item with the user's
  confirmation that data loss was acceptable (see AskUserQuestion
  in conversation). The 7-day rule is a Phase R0 hygiene gate; the
  R1 mechanism works on any URL.
* **Result:** Delete confirmed. Old URL `/marketplace/item/1332595162113434/`
  now redirects to `/marketplace/melbourne/?unavailable_product=1`.
* **Run-state JSON:** see `run-state.json` in this directory.
  `delete_detection: "redirect"`, `status: "deleted"`.

## Acceptance criteria — verification

* ✅ Hand-picked one already-published listing from
  `~/Desktop/things-for-sale/`. Ran the delete flow end-to-end.
* ✅ Opening the old URL shows the FB "isn't available" state with
  `unavailable_product=1` query param.
* ✅ The run-state JSON records `delete_detection: "redirect"` and
  `status: "deleted"`.
* ✅ Stop-the-line on undetected deletion is in place (row added to
  table in `browser-automation.md`). Verified by reading the new
  Step R1.7 outcome 3 ("Timeout — 15s without either signal") — it
  records `delete_unconfirmed` and explicitly forbids proceeding to
  Phase R2.
* ✅ Screenshots saved to `resell-au-workspace/iteration-4-refresh-r1/`:
  `01-listing-page.png` (seller view of detail page, no delete),
  `02-edit-page-no-delete.png` (Edit form has no delete),
  `03-selling-page-row-filtered.png` (target row located via
  `title_search` URL param),
  `04-more-options-menu-open.png` (the ⋯ menu open with Delete
  listing menuitem visible),
  `05-delete-confirm-dialog.png` (first confirm modal),
  `06-did-you-sell-dialog.png` (second-stage radio dialog — the
  un-anticipated step),
  `07-selling-page-after-delete.png` (filtered Selling page empty
  after delete fired),
  `08-old-url-redirects-unavailable.png` (deletion verified —
  `unavailable_product=1` page).
* ✅ Snapshot-before-every-click rule held throughout: each click
  was preceded by a fresh `take_snapshot`. No cached UIDs were
  re-used across state transitions.

## Known artefacts / cleanup notes

* **Stale listing.md.** `kids-wooden-playing-blocks/listing.md` still
  has `Status: Published` and a `**URL:**` line pointing at the now-
  deleted listing. This is intentional per the parent design:
  `listing.md` is updated atomically in Phase R2 (recreate), and R2
  isn't wired yet. Until R2 ships (Sub-tasks #3/#4), the user either
  (a) re-lists the item manually via Folder Mode and the new URL gets
  written, or (b) deletes the listing.md (then folder reclassifies
  as `new`). The R0 classifier will currently re-list this item as
  `refresh-eligible` only if its `**Date:**` ages past 7d — until
  then it stays `too-fresh`.
* **Inferring listing_id from listing.md.** Phase R1 uses
  `**Title:**` for the Selling-page filter and `**URL:**` for the
  post-deletion poll target. Both are required. The `**URL:**` regex
  contract from Phase R0 (`^\*\*URL:\*\*\s+(\S+)`) already gives the
  full URL — extract the digits between `/marketplace/item/` and `/`
  if the listing_id is needed elsewhere.

## Hand-off to Sub-task #3 (ABA-155)

Phase R2 (recreate at new price). Reuses Folder Mode Phase 4
Steps 1–7 verbatim. The new URL captured at Phase R2 Step 6 should
update the same `listing.md` whose old URL we just confirmed gone.
The 30–90 s human-cadence delay (Phase R1 Step R1.8) covers the
post-delete-pre-recreate window — no extra delay needed between R1
and R2 for the same item.
