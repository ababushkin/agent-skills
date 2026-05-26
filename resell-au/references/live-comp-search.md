# Live Comp Search — 3-Layer Protocol

The agent runs this loop in **Phase 2 (Pricing)** of Folder Mode, and in
**Step 2** of Text Mode, for every item being priced. Sold-anchored, multi-
source, date-stamped. Replaces the prior asking-only Google-snippet approach.

Pricing math (target → list → floor → garage-sale) lives in `SKILL.md` and
`pricing-reference.md`. **This file is about how to find the comp numbers**,
not what to do with them.

## The 3 layers, in order

| Layer | Source | Signal | When to run |
|---|---|---|---|
| 1 | eBay AU sold listings | **Sold** (primary anchor) | Always when a browser is attached; else skip → lean on Layers 2–3 |
| 2 | FB Marketplace live search | Asking (competitor set) | Always, unless Layer 1 strong AND item < $30 |
| 3 | Google snippet search | Asking (last resort) | Only when Layers 1–2 combined yield <3 valid comps |

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

### Fetch mechanism — browser-driven (not a plain GET)

eBay AU blocks non-browser HTTP clients: a plain WebFetch / WebSearch GET to the
URL above returns an Akamai **403 "Access Denied"** edge block or a
`splashui/challenge` interstitial — **never sold rows**. A real browser session
(cookies + JS) clears the challenge in ~3 s. So Layer 1 runs through the **same
attached Chrome (port 9222) as Layer 2**, via Chrome DevTools MCP. Unlike FB,
eBay's search is URL-driven — the params survive navigation, so there's no
searchbox to type into; you navigate straight to the URL.

Sequence (reuse a single eBay search tab across items, like Layer 2's FB tab):

1. `navigate_page` → the eBay sold URL above (keywords URL-encoded).
2. Pause **~3 s** for the `splashui/challenge` interstitial to auto-clear. Tune
   from 3 s: if step 3 still shows the challenge / "Access Denied" / a "checking
   your browser" page instead of result rows, wait once more (up to ~8 s total)
   or `navigate_page` reload once. If it still won't clear, that's a
   stop-the-line (see below) — not an empty result.
3. Read the resolved results page. Prefer `evaluate_script` to pull sold rows
   straight from the DOM — more reliable than the a11y snapshot for a dense
   result grid. As of this writing eBay AU renders each result as `li.s-card`
   (older layout: `li.s-item`): title in `.s-card__title` (`.s-item__title`),
   price in `.s-card__price` (`.s-item__price`), sold date in the card's
   caption / "Sold <date>" signal line (feeds the recency filter below).
   **Skip the first card** — eBay seeds a hidden "Shop on eBay" template row.
   Take the first price per card (the sold price) and parse the leading number
   from strings like "AU $44.49" or a range "AU $20 to AU $40". Selectors
   drift: if a parse returns **zero rows while the page clearly shows results**,
   that's stale selectors — re-derive them from a fresh snapshot, don't record
   0 comps.
4. Parse median / min / max / count from the sold prices, then apply the recency
   filter, outlier trim, and captures schema below — all unchanged.

### Run-budget rules (rate-limit hygiene)

- **8–15 s random pause between eBay searches** in a single run — same cadence
  as Layer 2's FB pause, because Layer 1 now shares the same browser and the
  same rate-limit surface.
- **No hard per-run search cap** (unlike Layer 2's 20-FB-search cap): eBay
  search is read-only and not tied to the logged-in account that posts, so the
  ban consequence is lower. The pause is the primary hygiene; a block that
  recurs across several items is the rate-limit signal — escalate via
  stop-the-line (below) rather than enforcing a fixed count.
- Same **stop-the-line conditions** as Layer 2 and the listing-creation loop
  (`browser-automation.md` § Stop-the-line). The transient ~3 s challenge that
  clears itself is normal; a block that *persists* after a reload, a captcha, a
  "browsing too fast" warning, or a login wall → screenshot + surface to the
  user, stop the search loop. Do not retry-search.

### No attached browser (Text Mode without Chrome)

This path is reachable in **Text Mode only** — Folder and Refresh Mode hard-gate
on an attached Chrome at Phase 0 and abort before pricing, so Layer 1 always has
a browser there.

Layer 1 needs the browser. With no attached Chrome, **do not fall back to a
plain GET** — it returns the 403 / challenge page, never comps, so a
"best-effort" GET is just a guaranteed-empty request that risks misparsing the
block page as data. Instead record `skipped_reason: "no_browser_session"` on
`ebay_sold` (the same value Layer 2 uses) and lean on Layers 2–3, applying the
asking→sold gap (×0.80) to the asking-side anchor. Comp confidence drops
accordingly.

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

## Layer 3 — Google snippet fallback

Only fires when Layers 1–2 **combined** produce <3 valid comps (e.g. genuinely
niche or discontinued items).

Existing search patterns:

- `<brand model> facebook marketplace australia`
- `<brand model> ebay australia used`
- `used <item type> price australia`

Extract any concrete price mentions from snippets. Confidence is auto-
downgraded to `"low"` when Layer 3 is the anchor source — Google snippets
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

- **Recency** — eBay sold ≤60 d; FB live is current by definition.
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

A `comps` block in run-state always contains all three layer keys. When a
layer doesn't run, populate `skipped_reason`:

| `skipped_reason` value | Meaning |
|---|---|
| `"sub_30_strong_anchor"` | Layer 1 strong + item < $30 → Layer 2 skipped |
| `"layers_1_to_2_sufficient"` | Layers 1–2 combined ≥ 3 → Layer 3 (Google) skipped |
| `"no_browser_session"` | Text Mode without attached Chrome → Layer 1 and/or Layer 2 skipped (both are browser-driven) |
| `"wrong_location"` | FB widened scope past Melbourne region |
| `"stop_the_line"` | Captcha / login wall / rate-limit — see browser-automation.md |
| `"zero_results"` | Layer ran but returned nothing on-topic |

Same shape in `listing.md` `## Comps` — write `- skipped (<reason>)` under the
heading rather than dropping the heading.

---

## Common rationalisations to reject

| Rationalisation | Why it fails |
|---|---|
| "eBay sold via WebFetch came back empty — Layer 1 has no comps, skip it." | WebFetch can't clear eBay's bot challenge (it returns a 403 / `splashui` page, not rows). That's the wrong tool, not "no comps." Drive Layer 1 through the attached Chrome. |
| "eBay had n=0 — I'll just use the asking median as the target." | Apply the asking→sold gap (×0.80). Asking median ≠ realised price; ignoring the gap is what the prior protocol got wrong. |
| "I'll skip Layer 2 — Layer 1 was strong." | Only skip Layer 2 when target < $30. Above $30, Layer 2 catches stale-sold / live-market divergence (sanity-check role). |
| "The first 20 FB cards looked off-topic — I'll just write count=0." | Scroll and re-snapshot once before giving up. Partial on-topic count is more honest than abandoning the layer. |
| "I'll skip the 8–15 s pause between FB searches — the listing-creation delay is what matters." | Read traffic also triggers rate limits on Marketplace search. Burst searching can captcha the same account that's about to post listings. |