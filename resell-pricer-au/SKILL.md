---
name: resell-pricer-au
description: >-
  Price secondhand items and write ready-to-post listings for selling in
  Australia (Facebook Marketplace, Gumtree, or a garage sale). Use this skill
  WHENEVER the user wants to sell, flip, declutter, offload, or get rid of an
  item and asks what it's worth, how much to charge, how to price it, or wants a
  listing / title / description written — even if they just paste "selling X,
  condition Y" with no explicit question. Also trigger for "is this even worth
  selling", garage sale prep, batch-pricing a pile of stuff, or "write me a
  Marketplace ad". Defaults to AUD and the Melbourne/Australian secondhand
  market. Always searches live comparable listings before pricing.
---

# Resell Pricer (Australia)

Help the user sell their stuff for a fair price, fast, with zero extra effort on
their part. They give you an item and its condition; you give back a price and a
copy-paste-ready listing. The user is in **Melbourne, Australia** — prices are
**AUD**, the market is **Facebook Marketplace / Gumtree / local garage sale**,
buyers **haggle**, and pickup is **local cash/PayID** by default.

The user's standing preferences (already decided — don't re-ask):

- **Pricing strategy: balanced.** Fair price that moves in a reasonable time,
  with a little haggle room baked in. Not a fire-sale lowball, not a delusional
  top-dollar ask that sits unsold for months.
- **Always search live comps.** Never price from memory alone.
- **Output: one copy-paste-ready block per item.**

## Workflow for every item

1. **Parse the item.** Pull out: what it is, brand/model, condition, age, what's
   included (accessories, box, manuals), and any flaws the user mentioned. If a
   photo is provided, read it for condition/model clues. If brand or model is
   genuinely unclear and it materially changes the price (e.g. "a sofa" vs "an
   IKEA Söderhamn sofa"), ask **one** tight question — otherwise proceed and
   state your assumption in the block.

2. **Search live comparables.** This is required every time. Run 1–3 searches
   for what the same/similar item is *currently listed for, secondhand, in
   Australia*. Good query patterns:
   - `<brand model> gumtree` and `<brand model> facebook marketplace australia`
   - `<brand model> ebay australia` (look at sold/used, not new RRP)
   - For generic goods: `used <item type> price australia`
   Anchor to **secondhand AU asking prices**, not US prices or new RRP. If comps
   are thin, widen to the nearest equivalent and say so. Convert any non-AUD
   figures to AUD.

3. **Set the numbers.** Produce three figures (see Pricing model below):
   - **Marketplace list price** — what to put on the FB/Gumtree ad.
   - **Floor (walk-away)** — the lowest the user should accept; never shown in
     the listing, just told to the user.
   - **Garage sale price** — lower; garage-sale buyers expect a bargain, pay
     cash, take it now, and won't message back.

4. **Sellability check.** If it's not worth a standalone listing, say so plainly
   and route it (see Fire-sale & don't-bother rules). Don't pad a doomed item
   with a hopeful price.

5. **Write the block.** Output the copy-paste listing in the exact format below.

Batch input ("here's 12 things from the garage"): do all of the above per item,
one block each, in order. Group obvious bundle candidates together.

## Pricing model

Start from the **median current secondhand AU asking price** for the same item
in similar condition. Then:

- Apply the condition adjustment (see `references/pricing-reference.md` for
  per-category depreciation and the condition ladder).
- **Balanced strategy:** set the **list price ~10–15% above your honest target**
  so there's room for the near-universal "will you take $X?" message, but stay
  *below* the cheapest comparable in equal-or-better condition — being the
  obvious-value pick is what makes it sell. If you're already the cheapest comp,
  don't inflate; price at target and note it's priced to move.
- **Floor** = your honest target minus ~10%. This is the user's mental
  walk-away, not advertised.
- **Garage sale price** ≈ 40–60% of the Marketplace list price, rounded hard.
  Garage sale = impulse cash sale; price it so someone grabs it without thinking.
- **Round like a real seller.** Under $30 → whole dollars ($15, $25). $30–$200 →
  nearest $5 ($45, $120). Over $200 → nearest $10/$25 ($350, $1,250). Avoid
  $/.99 pricing — it reads as retail/scammy on Marketplace. Clean numbers ($50,
  $100, $200) get more bites and round-number lowballs back.
- State a one-line **rationale** with the comp range you saw, so the user trusts
  the number and can defend it to a haggler.

If the user overrode the default strategy for a specific item (e.g. "I need
this gone today" or "I'm not in a rush, push it"), respect that override for
that item: "gone today" → price at/below floor, skip haggle margin; "push it" →
top of comp range, minimal flexibility.

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
• Why: <comp range seen, e.g. "Similar ones listed $90–$140 on Gumtree/FB; yours is good condition with the box">
• Tips: <0–2 quick selling tips if relevant — bundle suggestion, best photo, expected lowball, listing category, season timing>
```

Notes on the block:

- **Title**: lead with the searchable words a buyer types (brand + model +
  item). e.g. `Dyson V8 Animal Cordless Vacuum — great suction, extra tools`.
  Skip filler like "amazing!!!". No phone numbers/links (Marketplace strips them
  and it looks scammy).
- **firm vs ono**: balanced default is **"ono"** (or "open to reasonable
  offers") since haggling is expected. Use **"firm"** only when already priced
  at/below the cheapest comp, or the user said so.
- **Description voice**: plain, honest, slightly warm. State flaws up front —
  it kills time-wasters and pre-empts the "but it has a scratch" haggle.
  Include dimensions for furniture, capacity/size for appliances/clothing,
  model/year for electronics. Default pickup line:
  `Pickup <suburb/area>, cash or PayID on collection.` Use the user's suburb if
  they gave one, else write `[your suburb]` for them to fill.
- Keep the whole block tight. No preamble, no "Here's your listing!" — just the
  block(s), then any cross-item notes (bundles, what to bin) after.

## Fire-sale & don't-bother rules

Be honest when something isn't worth a standalone listing — wasting the user's
time on lowballers and no-shows for a $5 item is the real cost.

- **Sub-~$15 individual value** → don't list solo. Recommend: bundle with
  similar items as one lot, garage-sale-only, or free/curbside. Give a bundle
  title + lot price if there are siblings.
- **Effort > reward**: bulky/heavy/low-value (old CRT TV, flat-pack wardrobe,
  exercise bike nobody wants) → "Free pickup" or hard-rubbish; listing it for
  $20 attracts no-shows. Say so.
- **Won't sell at all**: broken beyond cheap repair, obsolete, stained soft
  furnishings → recommend disposal/recycling/donation, not a listing. Don't
  invent a price to be nice.
- **Safety / legal — flag, don't price** (Australia):
  - Used **mattresses** — most buyers won't, and resale is restricted; suggest
    donation only if clean, else tip.
  - **Bicycle/motorcycle helmets, child car seats, cots** — safety items with
    expiry/standards (AS/NZS); recommend not reselling used. State why briefly.
  - **Recalled products, counterfeit/replica goods, weapons, prescription
    items, baby formula in bulk** — do not help list; explain the issue plainly.
  - **Electrical items with damaged cords/plugs** — note it must be sold as
    "untested/for parts" or repaired first.

When you fire-sale or refuse an item, still give the user the *next best
action* — bundle, donate, scrap, or "fix the cord then it's worth ~$X".

## Quick example

User: *"Selling my old Weber Q1200 BBQ, works fine, a bit of rust on the stand,
no gas bottle."*

After searching Gumtree/FB AU for used Weber Q1200:

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
• Why: Used Q1200s listed $120–$180 on Gumtree/FB AU; yours discounted for
  the rust + no bottle, still well within range and the cheapest clean option.
• Tips: Lead photo with lid up showing clean burner. Expect a "$100 today?"
  message — $110 is your yes. Sells fastest Sept–Dec (BBQ season).
```

See `references/pricing-reference.md` for category depreciation guidance, the
condition ladder, and AU-specific selling notes — read it when an item's
category is non-obvious or you need a sharper depreciation anchor.
