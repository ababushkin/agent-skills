# Browser Automation Loop

The agent runs this loop in Folder Mode Phase 4 for each item × platform pair.
It is the generic orchestration layer; platform-specific field maps live in
`facebook-marketplace.md`.

## Pre-conditions (verified in Phase 0 before this loop ever runs)

- Chrome is reachable on port 9222.
- User is logged in to Facebook Marketplace in the attached Chrome.
- All items have been drafted, priced, and ad copy approved (Phases 1–3).

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

---

## Stop-the-line conditions

Stop the loop immediately and surface the issue to the user if:

| Condition | Action |
|---|---|
| Captcha / hCaptcha appears | Screenshot + "Captcha appeared — please solve it in the browser, then reply `continue`." Do not attempt to solve it. |
| 2FA prompt appears | Screenshot + "2FA required — please complete it in the browser, then reply `continue`." |
| "Posting too fast" / rate-limit message | Screenshot + "Rate-limit warning on [Platform]. Suggest waiting at least 10 minutes before continuing. Reply `continue` when ready." |
| Login wall (session expired) | Screenshot + "Logged out of [Platform]. Please log back in in the browser, then reply `continue`." |
| Snapshot doesn't match field map | As described in Step 2 above. |
| MCP error / navigation failure | Surface the error, stop. Do not retry silently. |

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
      "platforms": {
        "facebook_marketplace": "posted | skipped | failed | pending"
      },
      "post_publish_detection": "url_match | your_listings_redirect | timeout_manual | null",
      "listing_url": "https://www.facebook.com/marketplace/item/<id>/ | null"
    }
  ]
}
```

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
