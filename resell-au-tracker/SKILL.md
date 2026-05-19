---
name: resell-au-tracker
description: >-
  Sync items from resell-au listing.md files into the sales tracker page
  (~/Desktop/things-for-sale/tracker.html). Use when the user says "sync
  tracker", "update the tracker", "add my listings to the tracker", or after
  the resell-au skill has published new listings. Non-destructive: never
  modifies existing rows or sold prices. Generates tracker.html first if it
  doesn't exist. Requires Chrome running with --remote-debugging-port=9222
  (same setup as the resell-au skill).
---

# Resell AU — Tracker Sync

Scan `~/Desktop/things-for-sale/` for published listings and add any new items
to the sales tracker page without touching rows that already exist.

---

## Workflow

### Step 1 — Find listing.md files

```bash
find ~/Desktop/things-for-sale -maxdepth 2 -name "listing.md"
```

Read each file. Extract:
- **Title**: the value after `**Title:**` in the Ad copy section
- **Price**: the numeric value after `**Price:** $` (strip ` (firm)` / ` (ono)` suffix)

Include listings where `**Status:**` is `Published` or `Sold` — both represent
items that were live. Skip `Draft`, `Skipped`, and `Not listed`.

If the price cannot be parsed as a number, skip that item and include it in
the Step 6 report as "skipped — unparseable price".

### Step 2 — Ensure tracker.html exists

Check if `~/Desktop/things-for-sale/tracker.html` exists.

If it **does not exist**: write the standard tracker template to that path.
The template source is embedded at the bottom of this skill file.

### Step 3 — Open tracker in Chrome DevTools MCP

Use the Chrome DevTools MCP (Chrome must be running with `--remote-debugging-port=9222`
— same Chrome used by the resell-au skill). Open a new tab:

```
new_page: file:///Users/<your-username>/Desktop/things-for-sale/tracker.html
```
(Expand `~` to an absolute path when constructing the `file://` URL.)

Wait for the page to initialise, then verify the API is ready:

```js
// evaluate_script
() => typeof window.addItem === 'function'
```

Should return `true`. If not, issue a second `evaluate_script` call after a
short pause (e.g. a no-op script to let the event loop tick) and retry once.
If still not ready, surface an error and stop.

**Note:** Playwright blocks `file://` URLs, so use Chrome DevTools MCP here.
If Chrome is not attached, ask the user to open Chrome with remote debugging
first (same prerequisite as the resell-au skill — see `resell-au/references/chrome-setup.md`).

### Step 4 — Read current state

```js
// evaluate_script
() => {
  const raw = localStorage.getItem('sales-tracker');
  return JSON.parse(raw || '[]').map(r => r.name.trim().toLowerCase());
}
```

This returns the list of existing item names (lowercased) to deduplicate against.

### Step 5 — Add missing items

For each item parsed in Step 1, call evaluate_script:

```js
// evaluate_script  — construct one call per item, baking values as literals
() => window.addItem('Kettlebell 20kg', '45')
```

The string values for name and price must be baked directly into the function
body as string literals — `evaluate_script` runs in the page context and cannot
close over agent-side variables. Construct a separate `evaluate_script` call
for each item.

`window.addItem` returns `true` if added, `false` if duplicate. Collect
results for the summary.

### Step 6 — Report

Output a table:

| Item | Listed | Added? |
|------|--------|--------|
| Kettlebell | $45 | yes |
| IKEA Chair | $80 | already in tracker |

State the tracker path so the user can open it:
`~/Desktop/things-for-sale/tracker.html`

---

## Notes

- **Never modify existing rows.** If an item is already in the tracker (even
  with an empty sold price), leave it alone. The user may have edited it.
- **Price extraction**: `**Price:** $45 (ono)` → `45`. Strip everything after
  the first space following the number.
- **Title extraction**: `**Title:** Weber Q1200 Portable Gas BBQ — works great`
  → use the full title string as the item name in the tracker.
- **Multiple platforms**: a listing.md can have two Platform lines (FB +
  Gumtree). Only add the item once — deduplicate by title before the loop.
- **No browser already open**: if Chrome DevTools is not reachable and
  Playwright is unavailable, surface the error and stop. Do not attempt to
  write to localStorage directly — always go through the browser so the page's
  own persistence logic runs.

---

## tracker.html template

If `tracker.html` does not exist, write this verbatim to
`~/Desktop/things-for-sale/tracker.html`:

```html
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Sales Tracker</title>
  <style>
    *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
    body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: #f0f2f5; color: #1a1a1a; padding: 2rem; min-height: 100vh; }
    h1 { font-size: 1.4rem; font-weight: 700; margin-bottom: 1.25rem; }
    .card { background: #fff; border-radius: 10px; box-shadow: 0 1px 4px rgba(0,0,0,0.08), 0 4px 16px rgba(0,0,0,0.04); overflow: hidden; max-width: 720px; }
    table { width: 100%; border-collapse: collapse; }
    thead th { padding: 0.65rem 1rem; text-align: left; font-size: 0.7rem; font-weight: 600; text-transform: uppercase; letter-spacing: 0.06em; color: #888; background: #fafafa; border-bottom: 1px solid #eee; }
    thead th:last-child { width: 40px; }
    tbody tr { border-bottom: 1px solid #f4f4f4; }
    tbody tr:last-child { border-bottom: none; }
    tbody tr:hover { background: #fafcff; }
    td { padding: 0.4rem 0.75rem; }
    td.del-cell { padding: 0.4rem 0.5rem; width: 40px; }
    input { width: 100%; border: 1px solid transparent; border-radius: 5px; padding: 0.45rem 0.6rem; font-size: 0.9rem; font-family: inherit; color: #1a1a1a; background: transparent; outline: none; transition: border-color 0.15s, background 0.15s; }
    input:focus { border-color: #ccc; background: #f8f9ff; }
    input::placeholder { color: #bbb; }
    input[type="number"]::-webkit-inner-spin-button, input[type="number"]::-webkit-outer-spin-button { -webkit-appearance: none; }
    input[type="number"] { -moz-appearance: textfield; }
    .price-wrap { position: relative; display: flex; align-items: center; }
    .price-wrap::before { content: '$'; position: absolute; left: 0.65rem; color: #aaa; font-size: 0.9rem; pointer-events: none; }
    .price-wrap input { padding-left: 1.4rem; }
    .del-btn { display: flex; align-items: center; justify-content: center; width: 28px; height: 28px; background: none; border: none; border-radius: 5px; cursor: pointer; color: #ccc; font-size: 1.1rem; transition: color 0.15s, background 0.15s; }
    .del-btn:hover { color: #e53e3e; background: #fff5f5; }
    tfoot tr { border-top: 2px solid #eee; }
    tfoot td { padding: 0.85rem 1rem; text-align: right; font-size: 0.9rem; color: #666; }
    #total { font-weight: 700; font-size: 1.05rem; color: #2a7a46; margin-left: 0.4rem; }
  </style>
</head>
<body>
  <h1>Sales Tracker</h1>
  <div class="card">
    <table>
      <thead><tr><th>Item</th><th>Listed</th><th>Sold</th><th></th></tr></thead>
      <tbody id="rows"></tbody>
      <tfoot><tr><td colspan="4">Total earned: <span id="total">$0.00</span></td></tr></tfoot>
    </table>
  </div>
  <script>
    const KEY = 'sales-tracker';
    let timer;
    function load() { try { return JSON.parse(localStorage.getItem(KEY)) || []; } catch { return []; } }
    function collect() { return [...document.querySelectorAll('#rows tr')].map(tr => ({ id: tr.dataset.id, name: tr.querySelector('.name').value, listed: tr.querySelector('.listed').value, sold: tr.querySelector('.sold').value })); }
    function persist() { clearTimeout(timer); timer = setTimeout(() => localStorage.setItem(KEY, JSON.stringify(collect())), 300); }
    function updateTotal() { const t = collect().reduce((s,r) => { const v = parseFloat(r.sold); return s + (isNaN(v) ? 0 : v); }, 0); document.getElementById('total').textContent = '$' + t.toFixed(2); }
    function uid() { return (crypto.randomUUID ? crypto.randomUUID() : Math.random().toString(36)).slice(0,8); }
    function makeInput(cls, type, value, placeholder) { const i = document.createElement('input'); i.className = cls; i.type = type; i.value = value || ''; i.placeholder = placeholder; if (type === 'number') { i.min = '0'; i.step = '0.01'; } return i; }
    function makePriceCell(cls, value) { const td = document.createElement('td'); const w = document.createElement('div'); w.className = 'price-wrap'; w.appendChild(makeInput(cls, 'number', value, '0.00')); td.appendChild(w); return td; }
    function addRow(item) {
      const tr = document.createElement('tr'); tr.dataset.id = item.id;
      const nd = document.createElement('td'); nd.appendChild(makeInput('name','text',item.name,'Item name')); tr.appendChild(nd);
      tr.appendChild(makePriceCell('listed', item.listed)); tr.appendChild(makePriceCell('sold', item.sold));
      const dd = document.createElement('td'); dd.className = 'del-cell';
      const btn = document.createElement('button'); btn.className = 'del-btn'; btn.title = 'Remove'; btn.textContent = '×';
      btn.addEventListener('click', () => { tr.remove(); persist(); updateTotal(); });
      dd.appendChild(btn); tr.appendChild(dd);
      document.getElementById('rows').appendChild(tr);
    }
    document.getElementById('rows').addEventListener('input', () => { updateTotal(); persist(); });
    window.addItem = function(name, listedPrice) {
      const lower = String(name || '').trim().toLowerCase();
      if (collect().some(r => r.name.trim().toLowerCase() === lower)) return false;
      addRow({ id: uid(), name: name || '', listed: listedPrice || '', sold: '' });
      persist(); updateTotal(); return true;
    };
    const saved = load();
    const items = saved.length ? saved : [{ id: uid(), name: '', listed: '', sold: '' }, { id: uid(), name: '', listed: '', sold: '' }, { id: uid(), name: '', listed: '', sold: '' }];
    items.forEach(addRow); updateTotal();
  </script>
</body>
</html>
```
