---
name: resell-au
description: >-
  Price secondhand items and write ready-to-post listings for selling in
  Australia (Facebook Marketplace or a garage sale), and optionally drive a
  real browser to fill the listing forms so the user only has to click Post.
  Use this skill WHENEVER the user wants to sell, flip, declutter, offload, or
  get rid of an item and asks what it's worth, how much to charge, how to
  price it, or wants a listing / title / description written — even if they
  just paste "selling X, condition Y" with no explicit question. Also trigger
  for "is this even worth selling", garage sale prep, batch-pricing a pile of
  stuff, "write me a Marketplace ad", or when the user points at a folder of
  photos and asks to list items automatically. Defaults to AUD and the
  Melbourne/Australian secondhand market. Always searches live comparable
  listings before pricing.
---

# Resell AU

Help the user sell their stuff for a fair price, fast, with zero extra effort.
The skill has **three modes** that share the same pricing and ad-copy logic:

- **Text mode** — user types/pastes an item or list of items; you output
  copy-paste-ready listing block(s) and seller notes. No browser, no
  automation.
- **Folder mode** — user passes a folder path (e.g. `/resell-au ~/sell-pile`).
  You walk each subfolder, draft listings from photos, price each item, then
  drive a real Chrome session to fill FB Marketplace forms and automatically
  click Publish on the review screen.
- **Refresh mode** — user runs `/resell-au refresh <folder>`. You walk
  already-published items, classify which are stale (≥7 days old), then
  delete-and-relist them on FB Marketplace at a fresh price to reset the
  algorithm's honeymoon visibility window. See Refresh Mode workflow below.

The user is in **Melbourne, Australia** — prices are **AUD**, market is
**Facebook Marketplace / local garage sale**, buyers **haggle**, and pickup is
**local cash/PayID** by default.

Standing preferences (already decided — don't re-ask):

- **Pricing strategy: balanced.** Fair price that moves in a reasonable time,
  with a little haggle room baked in.
- **Always search live comps.** Never price from memory alone.
- **Output: one copy-paste-ready block per item.**

---

## Text Mode workflow

For each item typed or pasted:

1. **Parse the item.** Pull out: what it is, brand/model, condition, age,
   accessories/box/manuals included, and any flaws mentioned. If a photo is
   provided, read it for condition/model clues. If brand/model is genuinely
   unclear and it materially changes the price, ask **one** tight question —
   otherwise proceed and state your assumption in the block.

2. **Search live comparables (4-layer protocol).** Required every time.
   Full protocol in `references/live-comp-search.md`. Short version:
   - **Layer 1 — eBay AU sold listings (primary anchor):**
     `https://www.ebay.com.au/sch/i.html?_nkw=<keywords>&LH_Sold=1&LH_Complete=1&_ipg=60`
     Sold-only, last 60 days. **Always run.** Capture median / min / max /
     count / search URL.
   - **Layer 2 — FB Marketplace live (asking competitor set):** browser-only
     (client-rendered). Skip if Chrome on port 9222 isn't attached — record
     `skipped_reason: "no_browser_session"`. Skip if Layer 1 is strong AND
     item < $30.
   - **Layer 3 — Gumtree AU (asking fallback):**
     `https://www.gumtree.com.au/s-.../melbourne-region/<keywords>/k0c<cat>l3001317`
     Run when Layer 1 is weak (n<3) or Layer 2 returned <3.
   - **Layer 4 — Google snippet fallback:** old patterns
     (`<brand model> facebook marketplace australia`, etc.). Only when
     Layers 1–3 combined yield <3 comps. Auto-downgrades confidence to `"low"`.

   Anchor pricing on **sold median** (Layer 1) when n≥3 post-trim. Fall-through
   in the next step.

3. **Set the numbers.** Produce three figures (see Pricing model section):
   list price, floor (walk-away), and garage-sale price.

4. **Sellability check.** If it's not worth a standalone listing, say so and
   route it (see Fire-sale & don't-bother rules).

5. **Write the block.** Exact format in the Output format section below.

Batch input: do all of the above per item, one block each, in order. Group
obvious bundle candidates together.

---

## Folder Mode workflow

Invoked when the user passes a path argument: `/resell-au ~/path/to/folder`

### Phase 0 — Pre-flight (once per run)

1. Verify Chrome is reachable on port 9222 via a `list_pages` MCP call. If
   not, surface `references/chrome-setup.md` and stop — do not proceed.
2. Navigate to FB Marketplace in the attached Chrome and check for the login
   chrome. If not logged in, ask the user to log in once in the attached
   Chrome, then re-verify.
3. **Discover and classify subfolders.**

   **3a. List subfolders.** Skip anything starting with `.` or `_`.
   If zero valid subfolders, report politely and stop.

   **Subfolder names on disk are canonical.** Never reconstruct a subfolder
   name from an item title — title-derived slugs go wrong (e.g.
   `phillips-noodle-maker-hr2358-06` is the real folder; `philips-…` is what
   the title suggests). When you need to look up a subfolder by approximate
   name (matching against a tracker entry, a prior listing.md reference, a
   user-typed name), run a Bash one-liner like:

   ```bash
   python3 -c "import difflib, os; print(difflib.get_close_matches('<query>', os.listdir('<parent>'), n=1, cutoff=0.6))"
   ```

   If `get_close_matches` returns `[]`, stop and ask the user — do not guess.

   **3b. Classify each subfolder** by reading its `listing.md` (if present):

   - No `listing.md` → `new` — queue for FB Marketplace
   - `listing.md` has `**Platform:** Facebook Marketplace` → `fully-listed` — excluded from queue

   **3c. Report the classification table before proceeding:**

   | Item | Status | Action |
   |------|--------|--------|
   | kettlebell | new | list on FB Marketplace |
   | ikea-shelf | fully-listed | skip — already listed |

   If every item is `fully-listed`, tell the user all items are already listed and stop.
   Otherwise proceed with only the `new` items.

### Phase 1 — Per-item draft (loop over subfolders)

For each subfolder, one item at a time:

- **If the subfolder has a `listing.md`:** Read the `## Ad copy` and
  `## Seller notes` sections and pre-populate the draft from them. Output the
  pre-filled block marked `[pre-filled from prior listing]` and skip asking
  the user to re-describe the item. Jump straight to pricing in Phase 2 using
  the stored Target/Floor/Garage-sale figures from seller notes. Only ask the
  user if something is genuinely missing from the prior record.
- **Otherwise:** Read all image files (vision). Draft: probable item / brand /
  model / visible condition / visible accessories / visible flaws.
  Output a tight summary block and ask **one batched question** per item to
  fill gaps the photos can't answer: exact model (if uncertain), age, anything
  not pictured (charger? manual? box?), known flaws not visible, suburb for
  pickup line, and any strategy override ("need it gone today" / "push it").
  User responds. Update the draft.

### Phase 2 — Pricing (after all items drafted)

1. **Announce the run.** Tell the user: *"Searching live comps for N items
   (~40 s/item, ~Ns total)…"*

2. **For each item, run the 4-layer comp-search protocol** in
   `references/live-comp-search.md`:
   - Layer 1 (eBay AU sold) + Layer 3 (Gumtree AU) — plain GETs, back-to-back.
   - Layer 2 (FB Marketplace live) — browser-driven, reusing a single search
     tab on the attached Chrome. 8–15 s random pause between FB searches.
     Cap **20 FB searches per run** — folders >20 items batch into a second
     run with ≥30 min gap.
   - Layer 4 (Google snippet) — only when 1–3 combined yield <3 comps.
   Capture every layer's results (or `skipped_reason`) into the per-item
   `comps` block of the run-state JSON. Same `comps` data is written to
   `listing.md` later in Phase 4 Step 7.

3. **Anchor target** using fall-through rules:

   | Layer 1 sold n (post-trim) | Pricing anchor |
   |---|---|
   | ≥ 3 | `sold_median` |
   | 1–2 | blended: `0.7 × sold_median + 0.3 × asking_median × 0.80` |
   | 0 | `asking_median × 0.80` (apply asking→sold gap) |

   Then run the rest of the pricing model (condition adjustment, balanced
   strategy, list / floor / garage-sale).

4. **Present a pricing table** for the user to sanity-check the batch.
   Include two new columns:

   | Item | Target | List | Floor | Garage | **Anchor** | **Confidence** |
   |---|---|---|---|---|---|---|
   | bike | $75 | $85 | $65 | $40 | eBay sold $72 (n=8) | high |
   | violin | $90 | $100 | $75 | $45 | blended ($95 sold n=2 + $115 asking n=4) | medium |
   | ikea-rugs | $40 | $45 | $35 | $20 | asking-only ($55 asking n=6) | low |

   User approves or edits inline.

5. **Fire-sale / don't-bother rules** still apply. Sub-~$15 items are routed
   to "bundle / garage-sale / bin" and **dropped from the auto-listing queue**,
   with the user's explicit confirmation before proceeding.

### Phase 3 — Generate ad copy

- Produce the copy-paste block per surviving item. Show all blocks.
- **Pricing floor gate.** Before proceeding to Phase 4, ask once:
  *"Is there a minimum you'd accept for any of these? I'll lock it in as the
  hard floor before I start posting."* If the user sets a floor higher than
  the current list price, update the list price to match (don't post below the
  user's stated minimum). If no response or "no changes", proceed.
- User can also edit titles/descriptions inline at this point before listing
  begins.

### Phase 4 — Auto-list (per item, per platform)

For each surviving item, list on Facebook Marketplace:

**Pre-loop gate:** Before navigating, read `<item_subfolder>/listing.md` (if
present). If the file contains a `**Platform:** <current platform>` line,
skip this platform — do not navigate or fill any form. Record
`{ status: "skipped", reason: "already-listed" }` in the run-state JSON and
log: *"Skipping [item] on [Platform] — already listed (`listing.md` found)."*
This gate runs even if Phase 0 already classified the item, to catch edge
cases such as manual `listing.md` edits or an interrupted prior run.

1. Navigate to the create-listing URL.
2. Snapshot the page (accessibility tree via `take_snapshot`). Never rely on
   raw CSS selectors — they break every quarter. Re-snapshot after every state
   change.
3. Fill fields in the order the form expects. See `references/facebook-marketplace.md`
   for exact field maps and category trees.
4. Upload photos in **lexical filename order** — first file becomes the lead
   photo. Use the MCP `upload_file` per element UID, one at a time.
   Snapshot after each upload to confirm thumbnail appeared. Cap at 10.
5. **Review screen — verify then publish.** Take a screenshot. Verify title,
   price, condition, and description match the approved copy. If everything
   looks correct, click the Publish / Post button. If any field looks wrong,
   fix it first, re-snapshot to confirm, then click Publish.
6. **Confirm success — poll `window.location.href`, don't `wait_for`.** After
   clicking Publish, poll the URL via `evaluate_script` every 500 ms for up to
   15 s. Three outcomes:
   - URL matches `/marketplace/item/\d+/?` → capture URL, record
     `post_publish_detection: "url_match"` + `listing_url`, write URL to
     `listing.md` (Step 7), tell the user `"Posted <item> — <URL>."`
   - URL matches `/marketplace/you/selling` or `/marketplace/your_listings` →
     record `"your_listings_redirect"` + `listing_url: null`, screenshot, ask
     the user to paste the URL if they want it captured.
   - 15 s timeout → screenshot, record `"timeout_manual"`, ask the user to
     confirm publication and paste the URL. Do not retry-click Publish.

   Full protocol (regex, timing, stop-the-line conditions) lives in
   `references/browser-automation.md` Step 6.
7. **Write listing record.** Immediately after confirming the listing is live,
   write `<item_subfolder>/listing.md`. If the file already exists (item was
   previously listed on another platform), update the Platform line and append
   the new platform entry — don't overwrite the existing record.
   See the listing.md format section below for the exact template.
8. **Human-cadence delay** between items: 30–90 s random pause. Make it
   visible: *"Waiting 45 s before next listing…"*

See `references/browser-automation.md` for the complete per-platform loop,
human-cadence rules, and stop-the-line conditions.

### listing.md format

Write this exact template to `<item_subfolder>/listing.md` in Phase 4 Step 7:

```markdown
# <Item title> — listing record

**Status:** Published
**Date:** YYYY-MM-DD
**Platform:** Facebook Marketplace
**URL:** https://www.facebook.com/marketplace/item/<id>/

## Ad copy

**Title:** <title>
**Price:** $<price> (firm / ono)
**Category:** <category>
**Condition:** <condition>
**Brand:** <brand, or "(unbranded)" if unknown>
**Location:** <suburb>, Victoria, Australia
**Meetup:** Door pickup

**Description:**
<description text>

## Seller notes

- Target: ~$<target> | Floor: $<floor> | Garage sale: $<garage_sale>
- Comp confidence: <high | medium | low>
- Anchor: <sold_median | blended | asking-only>
- Tips: <0-2 tips>

## Comps (captured <YYYY-MM-DD>)

### eBay AU sold (primary)
- Median: $X | Range: $a–$b | n=N | Window: 60d
- Search: <URL>

### FB Marketplace live (asking)
- Median: $X | Range: $a–$b | n=N
- Query: "<keywords>"

### Gumtree AU (asking)
- Median: $X | Range: $a–$b | n=N
- Search: <URL>

### Fallback notes
<only present when Layer 4 ran>
```

Rules for this file:
- **Always include `Garage sale: $X`** in seller notes, even for user-set
  prices. If no garage sale price was calculated, derive it: 45% of list
  price, rounded to nearest whole dollar under $30, nearest $5 above $30.
- **`**URL:**` line** is populated from the post-publish poll (Phase 4 Step 6,
  `url_match` outcome). If the poll returned `your_listings_redirect` or
  `timeout_manual` and the user did not paste a URL, omit the line entirely
  rather than writing a placeholder — a missing line is the signal that the
  URL was not captured.
- **`## Comps` section** is populated from the run-state `comps` block
  captured in Phase 2. Skipped or zero-result layers **keep the heading** and
  write `- skipped (<reason>)` or `- 0 results` — auditability requires the
  agent shows what it tried. `<reason>` values are listed in
  `references/live-comp-search.md`.

### Phase 5 — Summary

- Output a final table: per item × per platform → posted / skipped (already
  listed) / skipped (sub-$15) / failed (with reason).

**Run-state file — write at Phase 3, update throughout:**

Write `<target_folder>/.resell-au-run-<YYYYMMDD-HHMM>.json` immediately after
Phase 3 with all items at `pending`. Update each item's status as Phase 4
proceeds. This means an interrupted run can be resumed:

**On any restart (context loss, `/compact`, crash):** read the run-state JSON
first. Items already at `posted` are skipped — do not re-navigate or re-fill.
Resume from the first item still at `pending` or `failed`.

Schema:
```json
{
  "run_started": "ISO 8601 timestamp",
  "target_folder": "/path/to/folder",
  "temp_path": "/var/folders/.../T",
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
      "listing_url": "https://www.facebook.com/marketplace/item/<id>/ | null",
      "listing_md_path": "/path/to/item/listing.md"
    }
  ]
}
```

The `comps` block is written in **Phase 2** before Phase 4 ever runs. Every
sub-source key is always present — `skipped_reason` records why a layer
didn't run. Full layer semantics and `skipped_reason` values live in
`references/live-comp-search.md`.

---

## Refresh Mode workflow

Invoked when the user runs `/resell-au refresh <folder>` (defaults to
`~/Desktop/things-for-sale/` if no folder is given). Refresh Mode
delete-and-relists stale FB Marketplace listings to reset the FB
algorithm's "honeymoon" visibility window — a ~30% message-rate lift
in reseller-community data.

The mode runs in four phases:

- **Phase R0 — Discovery & classification.** Read-only walk of the
  target folder. Classifies each subfolder's `listing.md` into
  `refresh-eligible` / `too-fresh` / `no-url` / `sold` /
  `not-published`, applies a 5-per-session cap, and prints a candidate
  table for the user to confirm. Detail in `refresh-strategy.md`.
- **Phase R1 — Delete existing listing.** For each item in the
  confirmed queued set: open the Selling page filtered by title,
  open the row's "More options" menu, click "Delete listing", verify
  identity in the confirm modal, answer the follow-up "Did you sell
  this item?" with "No, haven't sold", then poll the OLD listing URL
  for the `unavailable_product=1` redirect signal (15 s budget). On
  unconfirmed deletion, stop the line — do NOT proceed to recreate.
  Orchestration in `browser-automation.md` § "Refresh Mode — Phase R1
  delete loop"; locators in `facebook-marketplace.md` § "Delete
  listing locators (Refresh Mode Phase R1)".
- **Phase R2 — Recreate at new price.** Pre-fill the Phase 4 form
  payload from the item's `listing.md` (Ad copy block + on-disk
  photos), run Folder Mode Phase 4 Steps 1–6 verbatim, then on URL
  capture run `scripts/refresh_listing_md_update.py` to update the
  `**URL:**` / `**Date:**` lines and append a `## Refresh history`
  bullet — `**Price:**` and `## Comps` stay byte-identical. Recreate
  failure leaves `listing.md` alone so the resumable state for
  Sub-task #5 is intact. Sub-task #3 ships **one item, constant
  price**; the −10% clamp-to-floor calculator arrives in Sub-task #4.
  Detail in `refresh-strategy.md` § "Phase R2 — recreate at new price".
- **Phase R3 — Summary** *(added in Sub-task #6)*.

For full Phase R0 detail — classification rules, parser contracts,
session-cap behaviour, `no-url` no-write-back rule, data-loss warning,
deterministic fixture — read `references/refresh-strategy.md` when
Refresh Mode triggers, before walking any folder.

### Phase R0 — high-level steps

1. **Pre-flight.** Same as Folder Mode Phase 0: Chrome reachable on
   port 9222, FB Marketplace logged in. Bail early if either fails —
   later phases need the browser.

2. **Run the classifier script.** It walks subfolders, parses each
   `listing.md` against strict regex contracts, and prints the
   candidate table (including the one-line data-loss warning above
   it) to stdout:

   ```bash
   python3 <skill_dir>/scripts/refresh_r0_classify.py <target_folder>
   ```

   Do not re-implement classification inline — the script is the
   single source of truth for what counts as `refresh-eligible`. The
   strict regex contracts mean a hand-edited `listing.md` that does
   not match the canonical Phase 4 format is treated as missing rather
   than guessed at (the worst classification error is a false-positive
   `refresh-eligible` that deletes the wrong listing).

3. **Print the table to the user verbatim.** The script's output is
   already a complete candidate-table block; show it as-is.

4. **Handle `no-url` rows interactively.** For each `no-url` item,
   prompt the user to paste the listing URL. **Keep the paste
   in-memory for this session only** — do not write back to
   `listing.md`. If the user wants the URL persisted, they need to
   add the `**URL:**` line manually.

5. **Confirm with the user** that the queued set looks right before
   handing off to Phase R1.
   * `deferred` rows are visible but not acted on this session.
   * User can edit the list inline (e.g. "skip the bike, push the
     kettlebell ahead of the rugs") before continuing.
   * **Live-price override.** The `**Price:**` field in `listing.md`
     is a snapshot from initial publish — not authoritative for the
     current live FB price (the user manually drops prices post-publish
     without syncing back). Ask once before locking in the set:
     *"Any item where the current live FB price differs from the
     listing.md snapshot? Paste `<item>: $X` per line, or reply `none`."*
     Keep overrides **in-memory for this session only** — never
     write back to `listing.md`. Phase R2 uses the override as both
     the old and new recreate price (constant-price slice).

After confirmation, Phase R1 deletes each item in the queued set
(see `references/browser-automation.md` § "Refresh Mode — Phase R1
delete loop"), then Phase R2 recreates it (§ "Phase R2 — recreate at
new price" in `refresh-strategy.md`). In the Sub-task #3 slice the
queued set is exactly **one item** — multi-item handling and the
30–90 s inter-item delay come in Sub-task #5.

---

## Pricing model

Anchor on **sold data, not asking data**. Run the 4-layer comp-search
protocol (`references/live-comp-search.md`) first, then:

1. **Target = sold_median** (eBay AU sold, post-trim) when `n ≥ 3`. Apply
   the condition adjustment only if comps don't match the item's tier (see
   `references/pricing-reference.md` for the condition ladder).

2. **Fall-through anchor** when Layer 1 is thin:

   | Layer 1 sold n (post-trim) | Anchor |
   |---|---|
   | ≥ 3 | `sold_median` (anchor_source: `sold_median`, confidence: `high`) |
   | 1–2 | `0.7 × sold_median + 0.3 × asking_median × 0.80` (anchor_source: `blended`, confidence: `medium`) |
   | 0 | `asking_median × 0.80` (anchor_source: `asking_only`, confidence: `low`) |

3. **Sanity-check sold against asking medians:**
   - `sold_median < 0.6 × asking_median` → market has softened; keep the sold
     anchor but flag for human review.
   - `sold_median > 1.1 × asking_median` → current asking undercuts the sold
     window; drop target to `asking_median × 0.95`.

4. **Balanced strategy** (unchanged): list price ~10–15% above target so
   there's haggle room, but stay *below* the cheapest equal-or-better-condition
   FB asking comp. Being the obvious-value pick is what makes it sell.

5. **Floor** = target × 0.90. User's mental walk-away — not advertised.

6. **Garage sale price** ≈ 40–60% of list. Impulse cash sale, rounded hard.

7. **Round like a real seller.** Under $30 → whole dollars ($15, $25).
   $30–$200 → nearest $5 ($45, $120). Over $200 → nearest $10/$25 ($350,
   $1,250). Avoid $.99 pricing — reads as retail/scammy.

8. **Rationale string** required in seller-notes block: name the anchor and
   the source. e.g. *"Anchored on eBay sold median ($72, n=8, 60-day window);
   FB asking $80–$140 confirms list is below cheapest comp."*

Strategy overrides (unchanged): "gone today" → price at/below floor, skip
haggle margin. "push it" → top of comp range, minimal flexibility.

---

## Output format — use this exact block per item

```
🏷️ <ITEM NAME> — $<LIST PRICE>

Title: <punchy Marketplace title, ~60–80 chars, brand + item + key spec, no ALL CAPS, no emoji spam>

Price: $<list price> (firm / ono — pick one based on strategy)

Description:
<2–5 short lines. Honest condition. Key specs or dimensions. What's included.
Optional one-line reason for selling if it builds trust. Pickup area +
payment.>

—— seller notes (not for the ad) ——
• Target: ~$<honest target>  |  Floor: $<walk-away>  |  Garage sale: $<gs price>
• Comp confidence: <high | medium | low>  |  Anchor: <sold_median | blended | asking-only>
• Why: <rationale naming layer + numbers, e.g. "eBay sold median $72 (n=8, 60d); FB asking $80–$140 confirms list is below cheapest comp">
• Tips: <0–2 quick selling tips if relevant — bundle suggestion, best photo, expected lowball, listing category, season timing>
```

Notes on the block:

- **Title**: lead with the searchable words a buyer types (brand + model +
  item). e.g. `Dyson V8 Animal Cordless Vacuum — great suction, extra tools`.
  Skip filler like "amazing!!!". No phone numbers/links.
- **firm vs ono**: balanced default is **"ono"** (or "open to reasonable
  offers"). Use **"firm"** only when already priced at/below the cheapest comp,
  or the user said so.
- **Description voice**: sales-forward, positive. Lead with what's great about
  the item. Do not mention defects or flaws in the description — they are
  visible in the photos and buyers can decide for themselves. Include
  dimensions for furniture, capacity/size for appliances, model/year for
  electronics. Default pickup line:
  `Pickup <suburb/area>, cash or PayID on collection.`
- **No em-dashes.** Use hyphens (-) everywhere. Never use — in titles or
  descriptions.
- Keep the whole block tight. No preamble — just the block(s), then any
  cross-item notes after.

---

## Fire-sale & don't-bother rules

- **Sub-~$15 individual value** → don't list solo. Recommend: bundle, garage-
  sale-only, or free/curbside.
- **Effort > reward**: bulky/heavy/low-value (old CRT TV, exercise bike nobody
  wants) → "Free pickup" or hard-rubbish. Say so plainly.
- **Won't sell at all**: broken beyond cheap repair, obsolete, stained soft
  furnishings → disposal/recycling/donation, not a listing.
- **Safety / legal — flag, don't price** (Australia):
  - Used **mattresses** — resale restricted; suggest donation only if clean,
    else tip.
  - **Bicycle/motorcycle helmets, child car seats, cots** — AS/NZS expiry;
    recommend not reselling used. State why briefly.
  - **Recalled products, counterfeit/replica goods, weapons, prescription
    items, baby formula in bulk** — do not help list; explain the issue.
  - **Electrical items with damaged cords/plugs** — note it must be sold as
    "untested/for parts" or repaired first.

When you fire-sale or refuse an item, give the user the *next best action* —
bundle, donate, scrap, or "fix the cord then it's worth ~$X".

---

## Hygiene & safety rules — non-negotiable

These apply in Folder Mode. They are hard rules — not suggestions.

1. **Verify before publishing.** On the review screen, confirm title, price,
   condition, and description match the approved copy before clicking Publish.
   If anything looks wrong, fix it first. Never publish with unverified content.
2. **One account per platform per device.** Do not attempt multi-account
   features — Meta near-certain ban.
3. **Human-cadence delays** between listings (30–90 s randomised) and between
   platforms (60–120 s). Never skip these.
4. **Pause on captcha / 2FA / rate-limit prompts.** Surface the issue, hand
   control to the user, do not retry-loop or attempt to solve captchas.
5. **One platform at a time per item.** Do not parallelise across platforms.
6. **AU-only.** Australian Facebook Marketplace only. Do not attempt other
   regions.
7. **DOM-brittle by design.** If `take_snapshot` returns a structure that does
   not match the field map in references, **stop immediately**, show the user
   the snapshot, and ask them to confirm the new layout. Do not blindly click
   "the button that looks similar".
8. **Safety/legal product rules stand.** Used mattresses, child car seats,
   helmets, recalled goods etc. are flagged for non-resale before reaching
   Phase 4 — they never enter the auto-listing queue.

---

## Reference files

- `references/pricing-reference.md` — condition ladder, per-category
  depreciation, AU market norms, what counts as a valid comp. Read when an
  item's category is non-obvious or you need a sharper depreciation anchor.
- `references/live-comp-search.md` — the 4-layer comp-search protocol
  (eBay AU sold → FB Marketplace live → Gumtree AU → Google fallback),
  exact URL templates, FB browser-navigation sequence, run-budget rules.
  **Read in Phase 2 before pricing any item.**
- `references/chrome-setup.md` — one-time Chrome attach setup (dedicated
  Chrome instance, `--remote-debugging-port=9222`, login once). Read in Phase 0
  when Chrome is not reachable.
- `references/browser-automation.md` — the per-platform loop the agent runs:
  navigate → snapshot → fill → upload → wait for review screen → hand to user.
  Human-cadence rules and stop-the-line conditions. Read before Phase 4.
- `references/facebook-marketplace.md` — FB-specific field map, photo rules,
  category mapping cheat sheet, captcha/2FA/login-wall handling, ban-avoidance
  hygiene. Read in Phase 4.
- `references/refresh-strategy.md` — Refresh Mode reference: why
  delete-and-relist, Phase R0 classification rules + parser contracts,
  session cap + data-loss warning behaviour, `no-url` no-write-back
  rule, Phase R2 recreate orchestration + `listing.md` updater
  contract, run-state JSON shape + resume semantics, deterministic
  fixture pointers (R0 + R2). Read when `/resell-au refresh` triggers,
  before walking the folder.

---

## Quick example (Text Mode)

User: *"Selling my old Weber Q1200 BBQ, works fine, a bit of rust on the
stand, no gas bottle."*

After running the 4-layer comp protocol (eBay AU sold + Gumtree AU + Google
fallback — no browser in Text Mode unless attached):

```
🏷️ Weber Q1200 Portable BBQ — $140

Title: Weber Q1200 Portable Gas BBQ — works great, no bottle

Price: $140 ono

Description:
Genuine Weber Q1200, works perfectly — strong even heat, clean burner.
Some surface rust on the stand (cosmetic, doesn't affect cooking). No gas
bottle included. Great for balconies, camping, small yards.
Pickup [your suburb], cash or PayID on collection.

—— seller notes (not for the ad) ——
• Target: ~$130  |  Floor: $110  |  Garage sale: $70
• Comp confidence: high  |  Anchor: sold_median
• Why: eBay AU sold median $135 (n=11, 60-day window); Gumtree asking
  $140–$180 confirms list is below the cheapest clean comp.
• Tips: Lead photo with lid up showing clean burner. Expect a "$100 today?"
  message — $110 is your yes. Sells fastest Sept–Dec (BBQ season).
```
