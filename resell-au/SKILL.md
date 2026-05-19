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
The skill has **two modes** that share the same pricing and ad-copy logic:

- **Text mode** — user types/pastes an item or list of items; you output
  copy-paste-ready listing block(s) and seller notes. No browser, no
  automation.
- **Folder mode** — user passes a folder path (e.g. `/resell-au ~/sell-pile`).
  You walk each subfolder, draft listings from photos, price each item, then
  drive a real Chrome session to fill FB Marketplace forms and automatically
  click Publish on the review screen.

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

2. **Search live comparables.** Required every time. Run 1–3 searches for what
   the same/similar item is *currently listed for, secondhand, in Australia*.
   Good patterns:
   - `<brand model> facebook marketplace australia`
   - `<brand model> ebay australia` (sold/used, not new RRP)
   - For generics: `used <item type> price australia`
   Anchor to **secondhand AU asking prices**, not US prices or new RRP. If
   comps are thin, widen to nearest equivalent and say so.

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

- For each item, run the existing pricing logic verbatim (live-comp search,
  condition ladder, balanced strategy, list/floor/garage-sale).
- Present **all** prices as a table so the user can sanity-check the batch.
  User approves or edits inline.
- Fire-sale / don't-bother rules still apply. Sub-~$15 items are routed to
  "bundle / garage-sale / bin" and **dropped from the auto-listing queue**,
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
6. **Confirm success.** After clicking Publish, wait for the page to navigate
   away from the form. Snapshot and screenshot the result. Confirm the listing
   is live (FB navigates to the listing detail page). If the page shows an
   error or unexpected state, stop and surface it to the user — do not
   retry-click.
   Tell the user: *"Posted `<item>` on [Platform] — [listing URL if visible]."*
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
- Comps: <comp range and source>
- Tips: <0-2 tips>
```

Rules for this file:
- **Always include `Garage sale: $X`** in seller notes, even for user-set
  prices. If no garage sale price was calculated, derive it: 45% of list
  price, rounded to nearest whole dollar under $30, nearest $5 above $30.

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
      "platforms": {
        "facebook_marketplace": "posted | skipped | failed | pending"
      },
      "listing_url": "https://www.facebook.com/marketplace/item/<id>/",
      "listing_md_path": "/path/to/item/listing.md"
    }
  ]
}
```

---

## Pricing model

Start from the **median current secondhand AU asking price** for the same item
in similar condition. Then:

- Apply the condition adjustment (see `references/pricing-reference.md` for
  per-category depreciation and the condition ladder).
- **Balanced strategy:** set the **list price ~10–15% above your honest
  target** so there's room for the near-universal "will you take $X?" message,
  but stay *below* the cheapest comparable in equal-or-better condition.
  Being the obvious-value pick is what makes it sell. If you're already the
  cheapest comp, don't inflate; price at target and note it's priced to move.
- **Floor** = honest target minus ~10%. The user's mental walk-away, not
  advertised.
- **Garage sale price** ≈ 40–60% of the Marketplace list price, rounded hard.
  Impulse cash sale; price it so someone grabs it without thinking.
- **Round like a real seller.** Under $30 → whole dollars ($15, $25).
  $30–$200 → nearest $5 ($45, $120). Over $200 → nearest $10/$25 ($350, $1,250).
  Avoid $.99 pricing — reads as retail/scammy. Clean numbers get more bites.
- State a one-line **rationale** with the comp range you saw.

If the user overrode the default strategy ("I need this gone today" or "push
it"): "gone today" → price at/below floor, skip haggle margin; "push it" →
top of comp range, minimal flexibility.

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
• Why: <comp range seen, e.g. "Similar ones listed $90–$140 on FB Marketplace; yours is good condition with the box">
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
  depreciation, AU market norms. Read when an item's category is non-obvious
  or you need a sharper depreciation anchor.
- `references/chrome-setup.md` — one-time Chrome attach setup (dedicated
  Chrome instance, `--remote-debugging-port=9222`, login once). Read in Phase 0
  when Chrome is not reachable.
- `references/browser-automation.md` — the per-platform loop the agent runs:
  navigate → snapshot → fill → upload → wait for review screen → hand to user.
  Human-cadence rules and stop-the-line conditions. Read before Phase 4.
- `references/facebook-marketplace.md` — FB-specific field map, photo rules,
  category mapping cheat sheet, captcha/2FA/login-wall handling, ban-avoidance
  hygiene. Read in Phase 4.

---

## Quick example (Text Mode)

User: *"Selling my old Weber Q1200 BBQ, works fine, a bit of rust on the
stand, no gas bottle."*

After searching FB Marketplace AU for used Weber Q1200:

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
• Why: Used Q1200s listed $120–$180 on FB Marketplace AU; yours discounted for
  the rust + no bottle, still within range and the cheapest clean option.
• Tips: Lead photo with lid up showing clean burner. Expect a "$100 today?"
  message — $110 is your yes. Sells fastest Sept–Dec (BBQ season).
```
