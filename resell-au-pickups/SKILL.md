---
name: resell-au-pickups
description: >-
  Sweep your Facebook Marketplace inbox, read every buyer conversation, and
  summarise which items are being collected — who, what day and time, for how
  much, and where (pickup vs delivery) — then optionally add the pickups to your
  calendar. Use this skill WHENEVER the user wants to check their Marketplace / FB
  messages, asks who is picking up what and when, wants pickup or delivery times
  pulled out of their chats, or says things like "go through my messages", "what
  have I agreed to", "which items are people picking up and on what dates", or
  "put my pickups in my calendar". Defaults to Melbourne, Australia timezone and
  AUD. Pairs with the resell-au skill.
---

# Resell AU — Pickups

Read the user's Facebook Marketplace buyer conversations and turn them into a
clear picture of what's being collected, by whom, when, where, and for how much —
then, on request, drop those pickups into their calendar.

The user is in **Melbourne, Australia**: times are **AEST/AEDT**, money is
**AUD**, and most trades are local cash/PayID pickups (sometimes a paid drop-off).

Standing preferences (already decided — don't re-ask):

- **Melbourne timezone** for every time you report or schedule.
- **Never hardcode an address.** Read the pickup/delivery address out of the
  thread. If a pickup has no stated address, say "your place" rather than guess.
- **Be honest about certainty.** Separate what's actually agreed from what's
  still loose — don't promote a "maybe" into a booking.

This is a read-and-summarise skill. It does **not** mark items sold, reply to
buyers, or change listings unless the user explicitly asks (then defer to the
`resell-au` skill for listing changes).

---

## Workflow

### Phase 0 — Pre-flight

1. Confirm Chrome is attached on port 9222 via a `list_pages` MCP call. If it
   isn't, surface the `resell-au` skill's `references/chrome-setup.md` and stop.
2. Navigate to `https://www.facebook.com/marketplace/inbox` and confirm the user
   is logged in (you'll see the Selling/Buying tabs and a list of
   conversations). If not, ask them to log in once in the attached Chrome.

### Phase 1 — Sweep the inbox

Read **every** conversation that looks like it could involve an arrangement
(skip pure "is this available?" with no reply only at classification time, not
now — read them so you can classify accurately).

Per the full recipe in `references/inbox-extraction.md`:

1. Take one snapshot to get the list of buyer names + listing titles — this is
   your work-queue.
2. For each buyer, **one at a time**: close all docked chat windows → click the
   row **by buyer name** (not by snapshot uid) → wait ~3 s → run the
   composer-anchored extractor to pull the message history + listing price.
3. If the inbox reorders (a new message jumps to the top), re-read the queue.

Key gotchas (all covered in the reference): clicking opens a docked Messenger
window, the dock caps at ~5 so you must close between reads, and snapshot uids
go stale on reorder so you click by name.

### Phase 2 — Classify & resolve

For each thread, bucket it: **confirmed** (day + time agreed), **agreed-time-TBC**,
**declined/dead**, or **inquiry-only**. For every confirmed / TBC item capture:

- **buyer**, **item**, **agreed price** (the negotiated figure if they haggled,
  not just the listing price),
- **date** — resolve relative phrasing ("tonight", "tomorrow", "Friday")
  to an absolute Melbourne date from today,
- **time** (or "morning/daytime — TBC"),
- **location** — buyer's address for a delivery, seller's address (or "your
  place") for a pickup,
- **action note** — "text before leaving", "have it ready by the door", cash /
  PayID instructions.

The classification rubric and date-resolution rules live in
`references/inbox-extraction.md`.

### Phase 3 — Summary

Present a tight, scannable summary grouped by day, newest first, Melbourne times.
Use these sections (drop any that are empty):

- **🔴 Locked-in — happening soon** — the next 1–2 confirmed trades, with the
  action note called out (e.g. "you drive — text before leaving").
- **Per-day tables** — one small table per day: Time · Item · Buyer · $ ·
  (pickup/deliver). Put pickups at the same address together.
- **🟡 Agreed but time TBC — needs a nudge** — who to message to pin a time.
- **⚪ Done / dead** — already collected, declined, or bought elsewhere — one line
  each so the user knows you saw them.

Close with a one-line **week at a glance**. Flag clashes (two pickups at the same
address within an hour) and anything that needs the user to leave the house.

### Phase 4 — Calendar (optional — ask first)

Ask whether to add the pickups to their calendar. If yes, build the event list
and follow `references/calendar-export.md`:

- **Try the Google Calendar MCP `create_event`** first — one event per pickup,
  `timeZone: "Australia/Melbourne"`, a popup reminder (30 min for a pickup, 45
  min for a delivery you drive to), price + action note in the description.
- **If `create_event` returns `insufficient authentication scopes`** (the
  connector is read-only) or there's no Calendar MCP, **stop retrying** and fall
  back to `scripts/make_ics.py`: write `pickups.ics` into the target folder
  (default `~/Desktop/things-for-sale`) and give the import steps.

Mark TBC events clearly (prefix the day + `(TBC)`, note "confirm time" in the
description) so they're unmistakable when they pop up.

Offer, but don't assume: replying to buyers to lock TBC times is a separate
action — only do it if the user says so.

---

## Files

- `references/inbox-extraction.md` — the browser/DOM technique for reading
  threads, dock management, click-by-name, the extractor, and the classification
  + date-resolution rules.
- `references/calendar-export.md` — `create_event` field mapping, the read-only
  fallback, and the `make_ics.py` interface.
- `scripts/make_ics.py` — JSON pickup events → a valid `Australia/Melbourne`
  `.ics` with reminders. Deterministic; covered by `tests/check_make_ics.sh`.
