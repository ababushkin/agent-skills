---
name: garage-sale
description: >-
  Generate a print-ready HTML garage sale label sheet from listing.md files.
  Scans a folder of item subfolders, reads each listing.md for the Marketplace
  price and garage sale price, and outputs an A4 HTML label sheet showing the
  original listed price and the marked-down garage sale price side-by-side.
  Use this skill whenever the user mentions a garage sale, wants price labels,
  wants to print tags, or says anything like "mark everything down", "I'm having
  a garage sale", or "print labels for my listings". Requires listing.md files
  produced by the resell-au skill.
---

# Garage Sale Labels

Scans a folder of item subfolders that each contain a `listing.md` (written
by the `resell-au` skill) and generates a print-ready HTML label sheet with
two prices per item: the original Marketplace listing price and the marked-down
garage sale price.

---

## Invocation

```
/garage-sale ~/path/to/things-for-sale
```

The path argument is the root folder containing item subfolders. Each subfolder
must have a `listing.md` file (created by the `resell-au` Folder Mode). The
generated HTML is written to that same root folder.

If no path argument is given, ask the user for the folder. If the path does not
exist or is not a directory, tell the user and stop.

---

## Workflow

### Step 1 — Scan

List all subfolders of the target path. Skip anything starting with `.` or `_`.
For each subfolder, check if `listing.md` exists. Collect all that do.

If zero listing.md files are found: tell the user and stop.

**Load sold items from tracker.json.** If `<target_folder>/tracker.json` exists,
read and parse it. Build a sold-names set: the lowercased `name` value of every
entry where `sold` is a non-empty string. Example:

```json
[
  { "id": "a1b2c3d4", "name": "12kg Kettlebell - Good Condition!", "listed": "15", "sold": "15" },
  { "id": "b2c3d4e5", "name": "Knife Sharpening Stone Pack - brand new", "listed": "15", "sold": "" }
]
```

The first entry is sold (`sold` = "15"); the second is not (`sold` = ""). If
`tracker.json` is absent, continue with an empty sold-names set (no items
filtered) and note this in the final report.

### Step 2 — Parse each listing.md

For each `listing.md`, extract:

| Field | Where it lives in listing.md |
|---|---|
| `item_name` | The `**Title:**` line value |
| `list_price` | The `**Price:**` line — strip "firm"/"ono"/whitespace, keep the dollar number |
| `garage_sale_price` | The `Garage sale: $X` value from the seller notes line, e.g. `Seller notes: Garage sale: $5. Good condition.` |

**If `Garage sale:` is absent** (e.g. user-set price, or old format): calculate
it as `list_price × 0.45`, rounded to:
- Nearest whole dollar if result < $30
- Nearest $5 if result ≥ $30

No special marking on the label for estimated prices.

**If the item has `Status: Skipped` or `Status: Not listed`**: include it in
the label sheet anyway — it still needs a garage sale price.

**If the item name (lowercased) matches an entry in the sold-names set**: skip
it and add it to a "skipped — sold" list. Do not generate a label for it.

**If list_price cannot be parsed**: skip that item and note it in the final
report.

Both prices (Was and NOW) must appear on every label. The "Was" price is what
motivates the buyer — omitting it defeats the purpose of the label.

### Step 3 — Generate HTML

Write `<target_folder>/garage-sale-labels-<YYYYMMDD>.html` (use today's date).

#### Page layout
- A4 paper (210mm × 297mm)
- 2-column × 3-row grid = 6 labels per A4 page, auto-paginating
- Each label: ~95mm × 90mm, 1px solid border, 8mm padding
- No background colours — borders only (saves ink)
- Font: system sans-serif stack (`-apple-system, BlinkMacSystemFont, 'Segoe UI', Arial, sans-serif`)
- No web fonts — must work fully offline

#### Label layout

```
┌───────────────────────────────────┐
│                                   │
│  Kids Football Boots              │  ← item_name, bold 13pt, max 2 lines
│  US 3, Blue, Firm Ground          │     overflow: hidden; line clamp 2
│                                   │
│  Was $10        →   NOW $5        │  ← row, vertically centred
│  (grey 11pt,          (black      │
│   strikethrough)       bold 24pt) │
│                                   │
│                                   │
└───────────────────────────────────┘
```

Exact CSS rules:
- `.label`: `display: flex; flex-direction: column; justify-content: center; border: 1px solid #000; padding: 8mm; box-sizing: border-box; width: 95mm; height: 90mm; break-inside: avoid;`
- `.item-name`: `font-weight: bold; font-size: 13pt; line-height: 1.3; overflow: hidden; display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical;`
- `.price-row`: `display: flex; align-items: center; gap: 6mm; margin-top: 4mm;`
- `.was`: `font-size: 11pt; color: #888; text-decoration: line-through;`
- `.arrow`: `font-size: 11pt; color: #888;`
- `.now`: `font-size: 24pt; font-weight: bold; color: #000;`
- `.est`: `display: none;` — estimated prices are not marked on the label; the class exists only as a hook
- `.grid`: `display: grid; grid-template-columns: repeat(2, 95mm); gap: 5mm; padding: 10mm;`
- `@media print`: `body { margin: 0; } .grid { padding: 5mm; } .no-print { display: none; }`

#### Print instructions block (no-print)
At the top of the page, before the label grid, include a `<div class="no-print">` with:
```
Print instructions: Cmd+P (Mac) or Ctrl+P (Windows) → Paper size: A4 →
Margins: None (or Minimum) → Scale: 100% → Click Print.
```

### Step 4 — Report

Tell the user:

> Generated `garage-sale-labels-<date>.html` — N labels across M pages.
> Open in your browser and print: Cmd+P, paper A4, margins None, scale 100%.

If any items were skipped because they matched a sold entry in tracker.json,
list them:

> Skipped (already sold): Item Name A, Item Name B, …

If any items were skipped (unparseable price): list them by folder name.

If tracker.json was absent: note that sold-item filtering was skipped.

---

## Example output (2 items)

```html
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>Garage Sale Labels</title>
<style>
  body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Arial, sans-serif; }
  .no-print { background: #f5f5f5; padding: 12px; margin-bottom: 16px; font-size: 12px; }
  .grid { display: grid; grid-template-columns: repeat(2, 95mm); gap: 5mm; padding: 10mm; }
  .label { display: flex; flex-direction: column; justify-content: center; border: 1px solid #000; padding: 8mm; box-sizing: border-box; width: 95mm; height: 90mm; break-inside: avoid; }
  .item-name { font-weight: bold; font-size: 13pt; line-height: 1.3; overflow: hidden; display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; }
  .price-row { display: flex; align-items: center; gap: 6mm; margin-top: 4mm; }
  .was { font-size: 11pt; color: #888; text-decoration: line-through; }
  .arrow { font-size: 11pt; color: #888; }
  .now { font-size: 24pt; font-weight: bold; color: #000; }
  .est { display: none; }
  @media print { body { margin: 0; } .grid { padding: 5mm; } .no-print { display: none; } }
</style>
</head>
<body>
<div class="no-print">
  Print: Cmd+P → Paper A4 → Margins: None → Scale: 100%
</div>
<div class="grid">
  <div class="label">
    <div class="item-name">Kids Football Boots - US 3, Blue, Firm Ground</div>
    <div class="price-row">
      <span class="was">$10</span>
      <span class="arrow">→</span>
      <span class="now">$5</span>
    </div>
  </div>
  <div class="label">
    <div class="item-name">IKEA Nolmyra Easy Chair - birch frame, grey mesh fabric</div>
    <div class="price-row">
      <span class="was">$65</span>
      <span class="arrow">→</span>
      <span class="now">$30</span>
    </div>
  </div>
</div>
</body>
</html>
```
