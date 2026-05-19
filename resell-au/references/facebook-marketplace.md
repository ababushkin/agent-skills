# Facebook Marketplace — Field Map & Listing Guide

## Create listing URL

```
https://www.facebook.com/marketplace/create/item
```

Log in must be active in the attached Chrome before navigating here. If you
land on a login wall, stop and surface the issue to the user (see
`browser-automation.md` stop-the-line conditions).

## Marketplace search (read-only — comp lookup)

For **Phase 2 comp searches** the agent uses Marketplace search, not the
create-listing form. The URL is client-rendered, so query terms must be
typed into the searchbox rather than passed as URL params:

```
https://www.facebook.com/marketplace/melbourne/search
```

Full navigation sequence (snapshot → click searchbox → ctrl+a → fill → Enter
→ snapshot grid → extract cards), run-budget rules (8–15 s pause between
searches, cap 20/run), and skipped-layer recording live in
`live-comp-search.md` (Layer 2).

Same stop-the-line conditions apply (captcha, login wall, "browsing too
fast") — see the table at the bottom of this file.

## Field fill order

FB Marketplace validates fields progressively — fill in this order to avoid
state errors:

1. **Photos** — upload first; the form won't let you change category until at
   least one photo is present on some variants of the form.
2. **Category** — select from the category mapping table below.
3. **Title** — from the approved ad copy.
4. **Price** — AUD, numbers only (no `$` sign — the field adds currency).
5. **Condition** — see condition mapping table below.
6. **Description** — from the approved ad copy.
7. **Location** — type suburb; select the autocomplete suggestion. Do not
   free-type the full address.
8. **"Hide from friends" toggle** — leave at user's current default (do not
   change this setting; it varies by account preference).

After filling Location, the form typically shows a preview / "Next" button
leading to the review screen. Snapshot to confirm you're on the review screen
before stopping.

## Photo rules

- Maximum **10 photos** per listing (free accounts). Do not attempt an 11th
  upload — FB may silently drop it or show an error.
- First photo uploaded becomes the **lead/cover photo** in search results.
  Upload in lexical filename order so the user controls ordering by naming
  files `01-front.jpg`, `02-side.jpg`, etc.
- Supported formats: JPEG, PNG, HEIC. Minimum resolution: 500 × 500 px.
  Maximum file size: 10 MB per photo.
- Do not upload watermarked, AI-generated, or stock photos — image similarity
  detection will flag the listing.

## Category mapping

Use the closest match. FB's category tree changes occasionally; re-snapshot
after selecting a top-level category to confirm the subcategory options.

| Item type | Top-level | Subcategory |
|---|---|---|
| Furniture (sofa, table, chair, shelf) | Home & Garden | Furniture |
| Appliances (washing machine, fridge) | Home & Garden | Appliances |
| Small appliances (blender, toaster) | Home & Garden | Household items |
| Garden / outdoor furniture | Home & Garden | Outdoor |
| TVs, monitors | Electronics | TVs & Video |
| Computers, laptops | Electronics | Computers & Tablets |
| Phones | Electronics | Phones |
| Audio (speakers, headphones) | Electronics | Audio |
| Power tools | Tools | Power Tools |
| Hand tools | Tools | Hand Tools |
| Bikes (push bikes) | Sporting Goods | Bikes |
| Exercise equipment | Sporting Goods | Exercise & Fitness |
| Kids / baby gear | Baby & Kids | Baby & Toddler Gear |
| Kids' footwear / sports boots | Sporting Goods | Sports & Outdoors |
| Clothing, shoes (adult) | Clothing & Accessories | (match gender/type) |
| Books, music, games | Entertainment | Books, Movies & Music |
| Cars, utes, vans | Vehicles | Cars & Trucks |
| BBQs, outdoor cooking | Home & Garden | Outdoor |
| Camera / photography | Electronics | Cameras |

If an item doesn't fit cleanly, prefer the broader top-level category over an
incorrect subcategory — buyers search the top level more often.

## Condition mapping

| User's condition | FB condition field value |
|---|---|
| New / sealed | New |
| Like new / barely used | Used - Like New |
| Good condition | Used - Good |
| Fair / some wear | Used - Fair |
| For parts / broken | Used - For Parts |

Do not select "New" for any item that has been opened, even if unused.

## Captcha / login-wall / 2FA handling

- **Login wall on navigate**: session expired. Screenshot + stop. User must
  log in again in the browser.
- **"Confirm your identity" / checkpoint screen**: a Meta security check.
  Screenshot + stop. User must complete it. Do not retry.
- **Photo upload captcha**: rare but occurs on new accounts or burst uploads.
  Screenshot + stop.
- **"You're temporarily blocked from listing"**: rate-limit. Screenshot + stop.
  Tell the user to wait at least 1 hour (Meta's typical block window) before
  continuing.

## Ban-avoidance hygiene

These reduce (not eliminate) the risk of account action:

- **One listing at a time, 30–90 s apart.** Never post multiple items in rapid
  succession.
- **Don't list more than ~5–10 items per week from a new account.** Older
  accounts with transaction history tolerate higher volumes.
- **Real photos only.** Stock / AI-generated images trigger image classifiers.
- **No phone numbers or external URLs in the description.** FB strips them and
  the listing may be demoted or rejected.
- **Accurate category.** Miscategorised listings get flagged by other users and
  may be removed.
- **Don't relist the same item within 7 days.** Even if you delete and
  repost, FB's hashing catches it.
- **Use the pickup location accurately.** Mismatched locations (profile address
  vs. listing suburb) are a soft signal.
- **Hide from friends** — this is a per-listing toggle. Some users prefer it
  on to avoid acquaintances seeing everything they sell; leave at the user's
  existing default.

## Known fill quirks (discovered in testing — read before Phase 4)

These are not in the accessibility tree docs. Each was found through a failed
attempt during a real run; baked in here to avoid repeating them.

- **Title and price fields append, not replace.** `fill()` appends to the
  existing placeholder or previous value. The native value setter approach
  throws "Illegal invocation" on FB's React fiber. Use this sequence instead:
  1. `click(uid)` — focus the field
  2. `press_key("ctrl+a")` — select all existing content
  3. `fill(value)` — type the new value (replaces selection)
  4. `evaluate_script` to read back the field value and confirm it matches.
  If the readback doesn't match, repeat once before escalating.

- **Description textarea requires click then type_text.** `fill()` alone does
  not persist in the Sports & Outdoors (and some other) category forms.
  Correct sequence: `click(uid)` → `type_text(text)`. Verify the value was
  accepted: `document.querySelectorAll('textarea')[0].value`.

- **Location autocomplete: use keyboard, not snapshot click.** The autocomplete
  suggestions often do not appear in the a11y tree even though they exist in
  the DOM. Reliable sequence: JS-clear the location field → `fill("suburb")` →
  `press_key("ArrowDown")` → `press_key("Enter")`. This reliably selects the
  first suggestion.

- **Photos must be in an MCP-accessible path.** The `upload_file` MCP tool
  only allows files within the workspace roots. `/tmp/` is NOT accessible —
  it will return "Access denied". Use the system temp dir instead:
  ```bash
  cp /path/to/photo.jpg /var/folders/jd/9__6t9p9725glsmql48869lh0000gn/T/photo.jpg
  ```
  The accessible temp path is discovered in Phase 0: run `evaluate_script`
  with `os.tmpdir()` or check the MCP workspace roots list for a path matching
  `/var/folders/*/T`. Store it in the run-state for the whole run. If the
  path is unknown, copy a test file and confirm the upload succeeds before
  staging all photos.

- **Post-publish success signal — poll, don't `wait_for`.** After clicking
  Publish, FB navigates either to the listing detail page (URL contains
  `/marketplace/item/<id>`) or, on some A/B variants, to a your-listings page
  (`/marketplace/you/selling` or `/marketplace/your_listings`).
  Do NOT use `wait_for` for this — it matches text content, not URL changes,
  and will never resolve. Poll `window.location.href` via `evaluate_script`
  every 500 ms for up to 15 s and match against the URL patterns above.
  Full protocol (success paths, redirect fallback, timeout handling) lives in
  `browser-automation.md` Step 6.

## DOM stability notes

FB Marketplace's DOM changes frequently (sometimes monthly during A/B tests).
The accessibility tree snapshot is the reliable interaction layer — never
hardcode element IDs or CSS classes.

Known volatile areas:
- The photos upload element changes between `input[type=file]` and a custom
  component; always locate it from the snapshot's file-input UID.
- The category dropdown sometimes renders as a searchable text field; if the
  snapshot shows a text input, type the category name and select from the
  autocomplete.
- The price field sometimes adds a currency prefix automatically; don't
  double-enter the `$`.

If the snapshot doesn't match expectations: stop, screenshot, ask the user to
confirm the new layout before proceeding (see `browser-automation.md` Step 2).
