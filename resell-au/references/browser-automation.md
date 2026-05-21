# Browser Automation Loop

The agent runs this loop in Folder Mode Phase 4 for each item × platform pair.
It is the generic orchestration layer; platform-specific field maps live in
`facebook-marketplace.md`.

## Pre-conditions (verified in Phase 0 before this loop ever runs)

- Chrome is reachable on port 9222.
- User is logged in to Facebook Marketplace in the attached Chrome.
- All items have been drafted, priced, and ad copy approved (Phases 1–3).

The same Chrome session is also used in **Phase 2** for FB Marketplace
comp search (Layer 2 in `live-comp-search.md`). A Marketplace search tab may
remain open from Phase 2 when Phase 4 begins — leave it alone; Phase 4
navigates a separate tab to the create-listing URL.

## The loop (one item, one platform)

### Step 1 — Navigate

Navigate to the create-listing URL:

- Facebook Marketplace: `https://www.facebook.com/marketplace/create/item`

Wait for the page to fully load before snapshotting (use `wait_for` on a
known stable element — see the platform-specific file for the selector).

### Step 2 — Snapshot

Call `take_snapshot` to get the accessibility tree. This is the source of
truth for all subsequent interaction. Never rely on remembered CSS selectors
or XPaths from prior runs — DOM layouts change quarterly.

**If the snapshot doesn't match the field map in the platform reference file:**

1. Stop immediately.
2. Take a screenshot with `take_screenshot`.
3. Show the user the screenshot and the field map you expected.
4. Ask: *"The [Platform] listing form has changed layout. Can you confirm what
   the [field name] field looks like now? I'll update my reference before
   continuing."*
5. Do not guess. Do not click elements that "look similar". Wait for the user
   to confirm before proceeding.

### Step 3 — Fill fields

Fill fields in the order the platform form expects them. Use element UIDs from
the accessibility snapshot, not CSS selectors. After filling each field,
re-snapshot to confirm the value was accepted (some fields trigger dynamic
updates — category selection is the most common).

Fill order:

- **Facebook Marketplace**: photos → category → title → price → condition →
  description → location → hide-from-friends toggle. See
  `facebook-marketplace.md` for the exact interaction sequence.

### Step 4 — Upload photos

Use the platform's file-upload element UID from the snapshot. Upload in
**lexical filename order** — the first file becomes the lead photo.

Upload protocol:

1. Call `upload_file` with the element UID and the first photo path.
2. Snapshot. Confirm the thumbnail appeared. If it didn't, wait 2 s and
   snapshot again. If it still hasn't appeared after two checks, stop and
   tell the user.
3. Repeat for each photo. Cap at 10 — do not attempt an 11th upload.

Do not upload all photos in one call even if the MCP supports it — confirm
each thumbnail before the next upload.

### Step 5 — Review screen — verify then publish

After all fields are filled and photos uploaded, the form presents a review /
preview screen before final submission.

1. Snapshot the review screen.
2. Take a `take_screenshot`.
3. **Verify** title, price, condition, and description all match the approved
   ad copy. Check each field explicitly against the Phase 3 approved block.
4. If any field looks wrong: fix it (navigate back or use inline edit on the
   review screen), re-snapshot to confirm, then return to step 1.
5. If everything is correct: locate the Publish / Post button in the snapshot
   and click it.

### Step 6 — Confirm the listing is live

After clicking Publish, **do not use `wait_for` to detect navigation** — that
MCP tool matches page text content, not URL changes, and will never resolve
on the post-publish redirect. Instead, poll the URL via `evaluate_script`.

**Detection protocol** — Facebook Marketplace:

1. Poll `window.location.href` every **500 ms** for up to **15 s** using
   `evaluate_script` with body `return window.location.href;`.

2. **Success path A — listing URL matched.** URL matches
   `^https://www\.facebook\.com/marketplace/item/\d+/?(\?.*)?$`:
   - Capture the full URL.
   - Record `{ status: "posted", post_publish_detection: "url_match",
     listing_url: "<captured>", timestamp }` in the run-state JSON.
   - Write the URL to `listing.md` under the `**URL:**` field.
   - Break the poll. Tell the user: *"Posted `<item>` — `<URL>`."*

3. **Success path B — redirect to your-listings.** URL matches
   `/marketplace/you/selling` or `/marketplace/your_listings` (FB A/B tests
   this destination):
   - Record `{ status: "posted", post_publish_detection:
     "your_listings_redirect", listing_url: null }` in the run-state.
   - Take a screenshot.
   - Tell the user: *"Posted `<item>` — FB redirected to your-listings page;
     the listing URL was not captured. Paste it here if you want it stored
     in `listing.md`."*
   - Break the poll.

4. **Timeout — 15 s elapsed without a match.**
   - `take_screenshot`.
   - Record `{ status: "posted", post_publish_detection: "timeout_manual",
     listing_url: null }` in the run-state (provisional — user will confirm).
   - Surface to user: *"Publish click sent, but I couldn't confirm the
     listing went live within 15 s. Screenshot attached. Was it published?
     If yes, paste the listing URL."*
   - Wait for the user's reply before continuing to Step 7. Do not retry-click
     Publish.

5. If at any point during the poll the page shows an error banner, a captcha,
   or a "posting too fast" warning: **stop immediately**. Screenshot + surface
   to user per the stop-the-line conditions below.

**Why polling, not `wait_for`:** `wait_for` waits for text to appear on the
page. The post-publish state is a URL change, not a text change — there is no
reliable text token to wait for. A 500 ms `evaluate_script` poll is the
correct shape, and 30 calls over 15 s is trivial load on CDP.

### Step 7 — Human-cadence delay

After each successfully handled listing (whether posted or skipped), pause
**30–90 seconds (random)** before starting the next item.

Tell the user: *"Waiting [N] s before the next listing…"*

Never skip these delays. Burst posting is the primary detection trigger.

**How to actually pause** — the Claude Code Bash tool blocks long leading
`sleep` commands (the harness rejects `sleep 60` and similar). Use one of:

1. **`run_in_background: true`** on a `sleep N` Bash call — the harness
   accepts it, the task ID is returned immediately, and you get a completion
   notification when it finishes. This is the cleanest pattern.
2. **Bash `Monitor` with an until-loop** for conditional waits — e.g.
   `until <check>; do sleep 2; done`. Only when polling external state.

Do not chain shorter `sleep` calls to work around the block — the harness
detects that pattern. Do not poll with multiple Bash calls in a loop —
`run_in_background` already gives you a single notification.

---

## Refresh Mode — Phase R1 delete loop (one item)

Phase R1 runs after R0 produces a confirmed queued set. It deletes
ONE already-published listing on FB Marketplace, then verifies
deletion. **Recreate (Phase R2) does not run in this phase** —
duplicate-listing risk is bounded by completing the delete and
confirming it before handing back.

Locator patterns are in `facebook-marketplace.md` § "Delete listing
locators (Refresh Mode Phase R1)". This section is the orchestration
sequence — read both before running.

R1 is one step in the **multi-item R1+R2 loop** orchestrated by
`scripts/refresh_runstate.py`. The loop decides which item runs
next (and whether the next action for that item is R1 or R2 —
resume can start from R2 when R1 has already deleted the listing
in a prior session). Read `refresh-strategy.md` § "Phase R1+R2
multi-item loop" for the loop structure, the defer notice that
precedes the first R1, and the resume contract; this section
documents the per-item R1 mechanics.

### Pre-conditions

- Phase R0 has classified the target as `refresh-eligible` and the
  user has confirmed the queued set.
- The item's `listing.md` has a `**URL:**` line (the post-deletion
  poll target) AND a `**Title:**` line (the selling-page filter
  input).
- Chrome attached on port 9222, FB Marketplace logged in (Phase 0
  pre-flight already passed).

### Step R1.1 — Navigate to the seller's filtered listings page

The delete affordance lives only on `/marketplace/you/selling/`, not
on the listing detail page. Navigate using the title filter param so
the target row loads in the first batch:

```
https://www.facebook.com/marketplace/you/selling?title_search=<URL-encoded title>
```

The title comes from the `**Title:**` line in the item's `listing.md`
(produced by Folder Mode Phase 4 Step 7). URL-encode it before
appending — titles routinely contain spaces, `&`, `+`, hyphens, and
the `~` character.

### Step R1.2 — Snapshot, verify the target row exists

Call `take_snapshot`. Find a `button "More options for <Title>"` whose
accessible name matches the expected title exactly.

**Verification gate:** If zero matching rows exist, the listing is
already deleted (rare but possible — e.g. previous interrupted run).
Mark the item `status: deleted, delete_detection: "row_missing"` in
the run-state JSON and skip to Step R1.7 to confirm via URL poll.

If more than one row matches (rare — listing duplicated): disambiguate
by `target_id=<listing_id>` in the row's `Promote now` link URL. The
listing_id is the digits in the stored `**URL:**` between
`/marketplace/item/` and the trailing `/`.

### Step R1.3 — Open the "More options" menu

Snapshot. Click the `"More options for <Title>"` button. Re-snapshot.

The opened menu has role `menu "More options for listing"` with these
items (order may vary):

```
menuitem "Renew (N days)"   // disabled until 7-day cooldown elapses
menuitem "Mark as pending"
menuitem "View listing"
menuitem "List in more places"
menuitem "Edit listing"
menuitem "Delete listing"
menuitem "View messages"
```

If the menu doesn't open (snapshot still shows `expandable` collapsed),
re-click once. If still closed: **stop the line** — show user, do not
proceed.

### Step R1.4 — Click "Delete listing"

Re-snapshot. Click `menuitem "Delete listing"`. Re-snapshot.

A modal opens: `dialog "Delete listing"` containing a confirm heading
and the listing's title + price as static text.

### Step R1.5 — Verify listing identity, then click Delete

**Read the modal's title + price text. Compare against the expected
item from the run-state JSON.** If they don't match — stop the line.
This is the last point at which the wrong listing can be aborted.

If they match: click `button "Delete"` inside the modal.

### Step R1.6 — Handle the "Did you sell this item?" follow-up

After the first Delete click, FB shows a second-stage screen:
`heading "Did you sell this item?"` with four radio options. Defaults
to no selection; `button "Next"` is disabled until one is picked.

**Choose `radio "No, haven't sold"`** — that is the truthful answer
for refresh-mode (we are delisting due to staleness, not due to a
sale). Picking "Yes, sold …" might signal to FB's algorithm that the
item is no longer available, which is the opposite of what we want
when we relist it minutes later.

Click the radio, re-snapshot to confirm `checked`, then click
`button "Next"`. The modal closes. The row disappears from the
filtered Selling page.

### Step R1.7 — Verify deletion (poll the OLD listing URL)

Navigate the same tab to the stored `**URL:**` from `listing.md`
(`https://www.facebook.com/marketplace/item/<id>/`). Then poll
`window.location.href` via `evaluate_script` every **500 ms for up to
15 s**, same shape as Phase 4 Step 6:

```javascript
() => ({ url: window.location.href,
         hasGoneCopy: document.body.innerText.toLowerCase()
                       .includes("no longer available") ||
                       document.body.innerText.toLowerCase()
                       .includes("isn't available") })
```

Three outcomes:

1. **Success path A — URL redirect.** `window.location.href` no
   longer matches the original `^/marketplace/item/\d+/?$` pattern.
   The observed redirect is `…/marketplace/melbourne/?unavailable_product=1`
   — the `unavailable_product=1` query param is the cleanest single
   test. Record `delete_detection: "redirect", status: "deleted"`.

2. **Success path B — listing-gone copy.** Page text contains
   "no longer available" or "isn't available". Record
   `delete_detection: "listing_gone_copy", status: "deleted"`. (Both
   signals typically fire together; either alone is sufficient.)

3. **Timeout — 15 s without either signal.** Stop the line. Take a
   screenshot. Record `delete_detection: "timeout_manual",
   status: "delete_unconfirmed"`. **Do NOT proceed to Phase R2 (or to
   any other item)** — re-listing while the old listing might still
   be live duplicates content and is a primary trigger for FB's
   content-similarity flag. Surface to user:
   *"Couldn't confirm deletion of `<item>` within 15 s. Screenshot
   attached. Please verify the listing is gone in the browser and
   reply `continue` (skip recreate) or `manual-delete` (delete it
   yourself, then I'll continue)."*

### Step R1.8 — Human-cadence delay before next item

Same protocol as Phase 4 Step 7 — **30–90 s random pause** before
moving to the next item's R1 sequence. Use Bash `run_in_background:
true` on `sleep N`; do not skip.

The delay runs at the **multi-item loop level**, not after every
phase. R1 hands directly to R2 for the same item (no inter-phase
sleep — see `refresh-strategy.md` § "Step M2"), then the sleep
fires before the loop picks up the next item's R1.

The session cap of 5 deletes per session (Refresh Mode hygiene rule)
caps the burst risk even with the inter-item delay. Over-cap items
defer to a future session ≥30 min later; the defer notice listing
them by name prints once at the start of the loop (see
`refresh-strategy.md` § "Step M1").

---

## Stop-the-line conditions

These apply to both **Phase 4 listing creation** (the loop above) and
**Phase 2 comp search** (Layer 2 in `live-comp-search.md`). Stop the loop
immediately and surface the issue to the user if:

| Condition | Action |
|---|---|
| Captcha / hCaptcha appears | Screenshot + "Captcha appeared — please solve it in the browser, then reply `continue`." Do not attempt to solve it. |
| 2FA prompt appears | Screenshot + "2FA required — please complete it in the browser, then reply `continue`." |
| "Posting too fast" / rate-limit message | Screenshot + "Rate-limit warning on [Platform]. Suggest waiting at least 10 minutes before continuing. Reply `continue` when ready." |
| Login wall (session expired) | Screenshot + "Logged out of [Platform]. Please log back in in the browser, then reply `continue`." |
| Snapshot doesn't match field map | As described in Step 2 above. |
| MCP error / navigation failure | Surface the error, stop. Do not retry silently. |
| **Undetected deletion** (Phase R1 only) | After the 15 s URL poll, if neither `unavailable_product=1` redirect nor "no longer available" copy is observed: screenshot + "Couldn't confirm deletion of `<item>` within 15 s. Do NOT proceed to recreate. Please verify in the browser, then reply `continue` (skip the recreate for this item) or `manual-delete` (you'll delete it manually first)." Never re-list while deletion is unconfirmed. |
| **Listing identity mismatch in delete-confirm modal** (Phase R1 only) | Title or price shown in the `dialog "Delete listing"` modal does not match the run-state JSON for this item: stop, screenshot, do not click Delete. Surface to user. |

On `continue` reply: re-snapshot the current state and resume from Step 2.

---

## Run-state file

Written to `<target_folder>/.resell-au-run-<YYYYMMDD-HHMM>.json`.

Schema:

```json
{
  "run_started": "ISO 8601 timestamp",
  "target_folder": "/path/to/folder",
  "items": [
    {
      "subfolder": "item-name",
      "title": "Ad title",
      "list_price": 140,
      "floor": 110,
      "garage_sale": 70,
      "ad_copy": "Full description text",
      "photos": ["photo1.jpg", "photo2.jpg"],
      "comps": {
        "captured_at": "ISO 8601",
        "confidence": "high | medium | low",
        "anchor_source": "sold_median | blended | asking_only",
        "ebay_sold":      { "median": 72, "min": 55, "max": 110, "count": 8, "window_days": 60, "search_url": "...", "skipped_reason": null },
        "fb_marketplace": { "median": 95, "min": 80, "max": 140, "count": 6, "query": "...", "skipped_reason": null },
        "gumtree":        { "median": 85, "min": 70, "max": 110, "count": 4, "search_url": "...", "skipped_reason": null },
        "google_fallback": { "ran": false, "notes": null }
      },
      "platforms": {
        "facebook_marketplace": "posted | skipped | failed | pending"
      },
      "post_publish_detection": "url_match | your_listings_redirect | timeout_manual | null",
      "listing_url": "https://www.facebook.com/marketplace/item/<id>/ | null"
    }
  ]
}
```

The `comps` block is populated in **Phase 2** before Phase 4 ever runs. Every
sub-source key is present even when its layer was skipped — `skipped_reason`
records why. Full layer-source semantics and run-budget rules live in
`live-comp-search.md`.

Write the file after Phase 3 (with all items at `pending`), then update each
item's platform status as you go. This means an interrupted run can be resumed
by reading the file and skipping already-posted items.

---

## Common rationalisations to reject

| Rationalisation | Why it fails |
|---|---|
| "The element UID looks similar to what I'd expect — I'll just click it." | DOM layouts change. A wrong click can trigger actions that are hard to undo (e.g. posting to the wrong category, submitting a draft prematurely). Always re-snapshot and verify. |
| "I'll try to solve the captcha automatically." | Automated captcha solving is exactly the behaviour that triggers bans. Stop the line, hand to user. |
| "I'll skip the delay — we're in a hurry." | The delay is ban-avoidance, not convenience. Skipping it is the primary detection trigger. |
| "The review screen fields look roughly right — I'll just publish." | Verify each field explicitly against the approved copy before clicking Publish. "Roughly right" is how wrong content gets posted. |
