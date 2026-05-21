# Live Comp Search — 4-Layer Protocol

The agent runs this loop in **Phase 2 (Pricing)** of Folder Mode, and in
**Step 2** of Text Mode, for every item being priced. Sold-anchored, multi-
source, date-stamped. Replaces the prior asking-only Google-snippet approach.

Pricing math (target → list → floor → garage-sale) lives in `SKILL.md` and
`pricing-reference.md`. **This file is about how to find the comp numbers**,
not what to do with them.

## The 4 layers, in order

| Layer | Source | Signal | When to run |
|---|---|---|---|
| 1 | eBay AU sold listings | **Sold** (primary anchor) | Always |
| 2 | FB Marketplace live search | Asking (competitor set) | Always, unless Layer 1 strong AND item < $30 |
| 3 | Gumtree AU search | Asking (fallback) | Always when Layer 1 weak (n<3); else only if Layer 2 returned <3 |
| 4 | Google snippet search | Asking (last resort) | Only when Layers 1–3 combined yield <3 valid comps |

Every layer either produces a captured block or a `skipped_reason` — never
silently absent. See "Recording skipped layers" at the bottom.

---

## Layer 1 — eBay AU sold listings (primary anchor)

### URL template

```
https://www.ebay.com.au/sch/i.html?_nkw=<keywords>&LH_Sold=1&LH_Complete=1&_ipg=60
```

- `LH_Sold=1` and `LH_Complete=1` together filter to **sold** listings only
  (without `_Sold`, `_Complete` includes unsold ended auctions).
- `_ipg=60` returns 60 results per page — usually enough.

### Optional refinements

- `&_sop=13` — sort by ended most recently. Use when the default relevance
  ranking surfaces stale items.
- `&LH_PrefLoc=1` — restrict to AU-located sellers only. Use for items where
  locality affects price (furniture, large appliances, bikes). Skip for small
  shippable items where AU vs international doesn't change the realised price.

### Keyword crafting

Brand + model + key spec. **No condition words** ("used", "good cond"). eBay's
sold filter already implies real transactions. Examples:

- `Mongoose 20 inch kids mountain bike`
- `Weber Q1200 bbq`
- `IKEA Lappljung Ruta rug 200x300`
- `Enrico student violin 1/2`

### Recency filter

eBay's sold listings persist for ~90 days. Discard any sold result older than
**60 days** from today — the market shifts and stale sales mislead.

### Outlier trim

- `n ≥ 10`: trim top and bottom 10th percentile before computing median.
- `3 ≤ n < 10`: drop a single extreme outlier if it's >2× the median or
  <0.5× the median.
- `n < 3`: keep all, but mark `comp_confidence: "low"` downstream.

### What counts as a strong Layer-1 anchor

`n ≥ 3` post-trim **AND** at least 2 results within one condition tier of the
item being priced (see `pricing-reference.md` for the condition ladder).

### Captures

Write to the run-state `comps.ebay_sold` block:

```
{
  "median": <int AUD>,
  "min": <int AUD>,
  "max": <int AUD>,
  "count": <int post-trim>,
  "window_days": 60,
  "search_url": "<full URL>",
  "skipped_reason": null
}
```

---

## Layer 2 — FB Marketplace live (asking-side competitor set)

FB Marketplace search is **client-rendered** — no URL params survive a
navigation. The agent must drive the browser via Chrome DevTools MCP on the
attached Chrome (port 9222). See `browser-automation.md` for general
pre-conditions; this layer reuses the same login session.

### Navigation sequence

1. `navigate_page` → `https://www.facebook.com/marketplace/melbourne/search`
   (Melbourne-scoped search route. If FB shows a different default city,
   change it once in the UI — the agent doesn't manage the city setting.)
2. `take_snapshot` to find the search input (role: `searchbox`, name: "Search
   Marketplace" or similar).
3. `click` the searchbox UID → `press_key("ctrl+a")` → `fill(<keywords>)`.
   The same field-replace quirk from `facebook-marketplace.md` applies — fill
   appends without the select-all first.
4. `press_key("Enter")`. Wait ~1 s for the result grid to populate.
5. `take_snapshot` of the grid. Extract the first **15–20 cards**: title,
   price, location, posted-at relative time if visible.
6. Confirm the location filter is **Melbourne or Melbourne region**. If FB
   has auto-widened to "Australia" or another city, record
   `skipped_reason: "wrong_location"` and move on — do not adjust filters.

### When to run

- **Always**, except: Layer 1 anchor is strong AND the item's expected target
  price is < $30. (Browser time isn't free for sub-$30 items.)
- When Layer 1 is strong, timebox Layer 2 to **20 s** — it's a sanity check,
  not a decision input.

### Captures

```
{
  "median": <int AUD>,
  "min": <int AUD>,
  "max": <int AUD>,
  "count": <int>,
  "query": "<keywords>",
  "skipped_reason": null
}
```

### Run-budget rules

- **8–15 s random pause** between FB searches in a single run.
- Cap **20 FB searches per run**. Folders with >20 priced items batch into a
  second run with a ≥30 min gap.
- Reuse a single Marketplace search tab across items — don't open a new tab
  per item.
- Same stop-the-line conditions as the listing-creation loop:
  captcha / login wall / "browsing too fast" warning → screenshot + surface
  to the user, stop the search loop. Do not retry-search.

### Sponsored / off-topic cards

FB doesn't always label sponsored slots. If the first 20 cards are mostly
off-topic for the keywords (e.g. searching "Mongoose kids bike" returns adult
bikes), scroll the grid once and re-snapshot. If still off-topic, record
`count: <n on-topic>` and `skipped_reason: null` — partial signal is fine,
just honest.

---

## Layer 3 — Gumtree AU (asking-side, fallback)

### URL template

```
https://www.gumtree.com.au/s-<cat-slug>/melbourne-region/<keywords>/k0c<cat-code>l3001317
```

- `l3001317` = **Melbourne Region** location code. Hardcoded — AU/Melbourne
  scope only.
- `c0` = "all categories" — use when the category is genuinely uncertain.

### Category codes (most common)

| Category | Slug | Code |
|---|---|---|
| Sporting goods | sporting-goods | c9311 |
| Home & Garden | home-garden | c18293 |
| Electronics & Computer | electronics-computer | c9266 |
| Baby & Children | baby-children | c20186 |
| Musical Instruments | musical-instruments | c18280 |

Other categories: drop the `<cat-slug>` to `for-sale` and use `c0` — Gumtree
will return matches across all categories.

### Recency filter

Gumtree shows "Posted X days ago" on each card. Exclude anything labelled
**>30 days ago** — those listings have failed to sell and warp the median.

### When to run

- **Always when Layer 1 is weak** (n<3 sold) — Gumtree is the primary asking-
  side fallback in that case.
- **Only run when Layer 1 is strong AND Layer 2 yielded <3 comps** — saves
  a request when the sold anchor is solid and FB already gave a sanity check.

### Captures

```
{
  "median": <int AUD>,
  "min": <int AUD>,
  "max": <int AUD>,
  "count": <int>,
  "search_url": "<full URL>",
  "skipped_reason": null
}
```

---

## Layer 4 — Google snippet fallback

Only fires when Layers 1–3 **combined** produce <3 valid comps (e.g. genuinely
niche or discontinued items).

Existing search patterns:

- `<brand model> facebook marketplace australia`
- `<brand model> ebay australia used`
- `used <item type> price australia`

Extract any concrete price mentions from snippets. Confidence is auto-
downgraded to `"low"` when Layer 4 is the anchor source — Google snippets
mix new RRP, US prices, and old listings without distinguishing them.

### Captures

```
{
  "ran": true,
  "notes": "<1-line description of what was found>"
}
```

---

## Comp validity rules (recap)

Full rules and condition ladder live in `pricing-reference.md` (section: "What
counts as a valid comp"). The short version:

- **Recency** — eBay sold ≤60 d; Gumtree exclude "posted >30 d ago"; FB live
  is current by definition.
- **Condition match** — same tier preferred; one tier away OK without
  adjustment; two tiers away only as last signal, with tier-step adjustment.
  Unknown condition → treat as "good", mark `condition: unknown`.
- **Title match** — brand + item-type token both required. Reject same-brand-
  different-product (e.g. adult Mongoose when pricing a kids bike).
- **Outlier trim** — see Layer 1 rules.
- **Free listings ($0)** — excluded everywhere.
- **n<3 anywhere** → `comp_confidence: "low"`; the agent says so plainly in
  the seller-notes block.

---

## Recording skipped layers (auditability)

A `comps` block in run-state always contains all four layer keys. When a
layer doesn't run, populate `skipped_reason`:

| `skipped_reason` value | Meaning |
|---|---|
| `"sub_30_strong_anchor"` | Layer 1 strong + item < $30 → Layer 2 skipped |
| `"layer1_strong_layer2_sufficient"` | Layer 1 strong + Layer 2 ≥ 3 → Layer 3 skipped |
| `"layers_1_to_3_sufficient"` | Layers 1–3 combined ≥ 3 → Layer 4 skipped |
| `"no_browser_session"` | Text Mode without attached Chrome → Layer 2 skipped |
| `"wrong_location"` | FB widened scope past Melbourne region |
| `"stop_the_line"` | Captcha / login wall / rate-limit — see browser-automation.md |
| `"zero_results"` | Layer ran but returned nothing on-topic |

Same shape in `listing.md` `## Comps` — write `- skipped (<reason>)` under the
heading rather than dropping the heading.

---

## Common rationalisations to reject

| Rationalisation | Why it fails |
|---|---|
| "eBay had n=0 — I'll just use the asking median as the target." | Apply the asking→sold gap (×0.80). Asking median ≠ realised price; ignoring the gap is what the prior protocol got wrong. |
| "I'll skip Layer 2 — Layer 1 was strong." | Only skip Layer 2 when target < $30. Above $30, Layer 2 catches stale-sold / live-market divergence (sanity-check role). |
| "The first 20 FB cards looked off-topic — I'll just write count=0." | Scroll and re-snapshot once before giving up. Partial on-topic count is more honest than abandoning the layer. |
| "I'll skip the 8–15 s pause between FB searches — the listing-creation delay is what matters." | Read traffic also triggers rate limits on Marketplace search. Burst searching can captcha the same account that's about to post listings. |
| "Listings posted >30 d ago on Gumtree are still real comps." | They're listings that **didn't sell**. Including them pulls the asking median upward and breaks the asking→sold-gap math. |
