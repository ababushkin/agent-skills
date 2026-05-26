# Pricing Reference (Australia secondhand market)

Read this when an item's category isn't obvious to price, when live comps are
thin, or when you want a sharper anchor than "median asking price". These are
**starting anchors** — live comps always win over the table.

## Condition ladder

Map the user's words to one of these. State the condition plainly in the ad.

| Tier | Means | Rough % of equivalent new RRP* |
|---|---|---|
| New / sealed | Unopened, with tags/receipt | 60–80% |
| Like new | Used lightly, no marks, all parts/box | 50–65% |
| Good | Normal wear, fully works, minor cosmetic marks | 35–50% |
| Fair | Visible wear or a working flaw, still usable | 20–35% |
| Worn / for parts | Cosmetically rough or partially working | 5–20% |

*Percent of *new RRP* only as a fallback. If you have real secondhand AU comps,
anchor to those instead — they already price in depreciation and demand.

## Category depreciation notes (AU)

- **Electronics (phones, laptops, TVs, consoles):** depreciate fast and by
  generation, not age. A 2-gen-old flagship can be 30–40% of new. Working +
  charger + box matters a lot. Apple holds value best; budget Android barely
  resells. Check eBay AU *sold* listings for the tightest read.
- **Large appliances (fridge, washer, dryer):** sell well used if working and
  clean — 25–45% of new, more if <3 yrs and a known brand (Bosch, Fisher &
  Paykel, Miele). Delivery is the friction; "you collect" lowers price ~15%.
- **Furniture:** brand-dependent. IKEA resells at 20–35% of new (buyers compare
  to cheap new IKEA). Mid/high-end (King, Jardan, West Elm, vintage teak) holds
  40–60%. Flat-pack that's been disassembled/reassembled drops hard. Soft
  furnishings with stains/odours → near zero, don't bother.
- **Power tools / outdoor (Makita, Ozito, Weber, Victa):** strong resale,
  35–55% used if working. Brand and "works perfectly" do heavy lifting.
- **Baby/kids gear:** prams and quality toys resell well (Bugaboo, Lego) at
  30–50%. BUT car seats, cots, helmets = safety-restricted, see SKILL.md.
- **Clothing/shoes:** unless designer/streetwear with demand, individual items
  rarely clear >$10–20 secondhand — bundle or garage-sale. Designer (with
  authenticity), workwear, and good boots are the exceptions.
- **Bikes:** decent resale, 30–50% if mechanically sound; flag worn brakes/tyres
  honestly. Kids bikes are low value — bundle/garage-sale.
- **Books / CDs / DVDs / bric-a-brac:** individually near-worthless online.
  Garage-sale-only at $1–5, or bulk lot ("80 books, $30 the lot").
- **Whitegoods/electricals with cord damage:** "untested / for parts" only.
- **Exercise equipment (treadmills, multi-gyms):** notoriously hard to sell,
  bulky; often free-pickup territory unless premium brand and near-new.

## What counts as a valid comp

The 3-layer search protocol that produces comps lives in
`live-comp-search.md`. This section is the rule set for **what to keep** once
you have results. The same rules apply to every layer; differences are noted
inline.

- **Recency.** eBay sold listings ≤ 60 days old. FB Marketplace live is
  current by definition.
- **Condition match.** Prefer same-tier comps. One tier away is fine without
  adjustment. Two tiers away counts only as a last signal, with a tier-step
  adjustment derived from the condition ladder above. Unknown-condition comps
  → treat as "good" but mark `condition: unknown` in the record.
- **Title match.** Brand token + item-type token both required. Reject
  same-brand-different-product (e.g. adult Mongoose mountain bike when pricing
  a kids' 20" Mongoose). Same item-type-different-brand only when the user's
  item is unbranded.
- **Outlier trim** (eBay sold, primarily):
  - n ≥ 10 → trim top and bottom 10th percentile before computing median.
  - 3 ≤ n < 10 → drop one extreme outlier if it's >2× median or <0.5× median.
  - n < 3 → keep all, but downstream `comp_confidence` is `"low"`.
- **Free listings ($0) excluded** everywhere.
- **Asking → sold gap.** When the anchor is asking-only (no Layer 1 sold
  data), multiply asking median by **0.80** to approximate realised price.
  20% gap is the AU-wide rule of thumb; revisit once we have ≥10 same-item
  observations of both sold and asking.

## AU market norms to bake into advice

- **Channels:** Facebook Marketplace = highest volume + most lowballers/no-shows.
  Garage sale = instant cash, no messaging, deep discounts expected.
- **Sold beats asking, every time.** eBay AU sold listings
  (`LH_Sold=1&LH_Complete=1`) are the **primary anchor** — the only signal
  that reflects actual realised AU prices. FB Marketplace shows
  what sellers *want*, not what items go for. Use asking medians as the
  competitor set / ceiling, not as the target. Full protocol:
  `live-comp-search.md`.
- **FB Marketplace pricing anchor:** Once the target is anchored on sold data,
  price the **list** at or just below the lowest equal-condition FB asking
  comp. Buyers on FB scroll through multiple listings and message the
  cheapest clearly-good one first. Being the obvious-value pick is the
  strategy — but the value is judged against sold, not against other asking
  listings.
- **Haggling is the default.** Listing "ono" or "open to offers" gets more
  contacts; "firm" filters but reduces them. First message is almost always a
  lowball — the floor figure is the user's pre-decided "yes".
- **Payment:** cash or **PayID** on pickup. Warn against posting items for
  "buyers" who insist on courier + overpayment (classic scam).
- **No-hold without deposit.** Suggest the user not reserve items on a promise.
- **Seasonality:** BBQs/outdoor/aircon → spring–summer (Sep–Feb). Heaters →
  autumn–winter. Furniture moves around moving peaks (start/end of month, uni
  semester starts). Mention timing only when it materially helps.
- **Bundling beats single low-value listings.** One "garage clear-out lot"
  listing outperforms ten $5 listings for effort and reach.
- **Photos sell.** When relevant, suggest: natural light, decluttered
  background, show flaws honestly, first photo = the hero shot.

## Sanity checks before finalising a price

- **n ≥ 3 sold comps post-trim?** If not, `comp_confidence` drops to `"low"`
  and the agent says so plainly in seller notes (e.g. *"Anchor: asking-only —
  no recent AU sold data."*). Don't quietly publish a low-confidence price as
  if it were strong.
- **Sold-median vs asking-median sanity:**
  - `sold_median < 0.6 × asking_median` → market has softened since the sold
    window; keep the sold anchor but flag for human review.
  - `sold_median > 1.1 × asking_median` → current asking market undercuts the
    sold window; drop target to `asking_median × 0.95`.
- Is the list price *below the cheapest equal-condition asking comp*? If not,
  the buyer just buys the other one. Balanced strategy = be the value pick.
- Would *you* drive across Melbourne to buy this at that price? If no, drop it.
- Is the floor a real number the user can say "yes" to instantly when the
  lowball arrives? It should be.
- Sub-$15 and not designer/branded? → bundle or garage-sale, don't solo-list.
