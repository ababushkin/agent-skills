# Calendar export — MCP first, ICS fallback

Two ways to get pickups into the user's calendar. Try the Google Calendar MCP
first; fall back to a generated `.ics` the moment it's unavailable or read-only.

## Path A — Google Calendar MCP (`create_event`)

One call per event. Map the captured pickup fields like this:

| `create_event` arg  | Value |
|---------------------|-------|
| `summary`           | `"<Buyer> — <item> ($<price>)"`, e.g. `"Cindy — fog machine ($35)"` |
| `startTime`         | naive local, `"2026-06-04T18:00:00"` |
| `endTime`           | start + 30 min (pickup) or + 60 min (a delivery you drive to) |
| `timeZone`          | `"Australia/Melbourne"` (always — dictates display TZ) |
| `location`          | buyer address for a delivery; seller address (or omit) for a pickup |
| `description`       | agreed price, payment note, and any action ("text before leaving", "have it ready") |
| `overrideReminders` | `[{"method":"popup","minutes":30}]` for pickups; `45` for a delivery drive |
| `colorId`           | optional — `"11"` (tomato) reads well for a delivery you have to leave for |

For a **TBC** event, still create it at a best-guess time, prefix the summary
with the day and `(TBC)`, and put "TIME NOT CONFIRMED — confirm with <buyer>" in
the description so it's obvious when it surfaces.

### The read-only failure to watch for

The claude.ai Google Calendar connector is frequently connected **read-only**.
`list_calendars` / `list_events` succeed, but `create_event` returns:

```
Request had insufficient authentication scopes.
```

If you see this (or there is no Calendar MCP at all), **stop retrying** and
switch to Path B. A `/mcp` reconnect does *not* fix it unless the user re-grants
the calendar *edit* scope on Google's consent screen — so don't loop on it.
Mention the read-only cause once, then hand over the `.ics`.

## Path B — generate a `.ics` with `make_ics.py`

Build a JSON array of event objects and pipe it through the script. Each object:

```json
{
  "uid": "resell-<buyer>-<item>@things-for-sale",
  "summary": "Cindy - fog machine pickup ($35)",
  "start": "2026-06-04T18:00:00",
  "end": "2026-06-04T18:30:00",
  "location": "2/35-37 Grange Road, Caulfield East VIC",
  "description": "Fog machine, fluid included. $35 cash. She'll message when on her way.",
  "alarm_minutes": 30
}
```

Run it (default folder is the resell-au working folder):

```bash
python3 <skill_dir>/scripts/make_ics.py events.json --out ~/Desktop/things-for-sale/pickups.ics
# or stream: cat events.json | python3 <skill_dir>/scripts/make_ics.py > pickups.ics
```

The script emits a single `VCALENDAR` carrying an `Australia/Melbourne`
`VTIMEZONE` (correct year-round, AEST↔AEDT), one `VEVENT` per item, a `VALARM`
for any event with `alarm_minutes`, RFC-5545 text escaping, and 75-octet line
folding. Output is deterministic (fixed `DTSTAMP`, UIDs from input) so it stays
golden-testable. `start`/`end` are naive local Melbourne times — do **not**
pre-convert to UTC.

### Tell the user how to import

1. Open **calendar.google.com** → ⚙️ **Settings** → **Import & Export**.
2. Under *Import*, **Select file** → choose `pickups.ics`.
3. Pick the calendar → **Import** ("N events imported").

(Double-clicking the file on macOS imports into Apple Calendar instead — fine if
that's what they use.)
