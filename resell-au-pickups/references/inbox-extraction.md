# Inbox extraction — Facebook Marketplace messages

How to read every buyer conversation out of the Marketplace inbox with the
Chrome DevTools MCP, and how to classify what you find. These are the
hard-won details — the inbox does not behave like a normal page.

All snippets run via `evaluate_script` on the attached Chrome (port 9222).

## The inbox is a dock, not a reading pane

Navigating to `https://www.facebook.com/marketplace/inbox` shows the list of
conversations on the left. **Clicking a conversation does NOT open an inline
reading pane** — it opens a docked Messenger chat window (a "chat head") at the
bottom of the screen. Two consequences:

1. The thread text lives in that docked window, anchored by its message
   composer, not in `[role="main"]`.
2. **The dock caps at ~5 open windows.** Once five are open, clicking a sixth
   silently does nothing. So you must **close docked windows between reads** or
   the sweep stalls with no error.

Work **one conversation at a time**: close all docked windows → click the next
row → wait ~3 s → extract → repeat.

### Close all docked windows

```js
() => { Array.from(document.querySelectorAll('[aria-label^="Close chat"]'))
  .forEach(b => { try { b.click() } catch (e) {} }); return 'closed'; }
```

## Click a row by buyer name (never by snapshot uid)

The inbox **reorders the moment a new message arrives** mid-sweep, so any `uid`
captured from an earlier `take_snapshot` goes stale and you will open the wrong
thread. Click rows by buyer name via a DOM query instead:

```js
() => {
  const name = 'Cindy';                       // buyer's display name
  const el = Array.from(document.querySelectorAll('[role="button"],button'))
    .find(b => (b.getAttribute('aria-label') || b.innerText || '').trim().startsWith(name));
  if (!el) return { err: 'not found' };
  el.click();
  return { clicked: true };
}
```

To get the list of names to iterate, take ONE snapshot of the inbox up front and
read the row labels (each row reads `"<Name>   <listing title> <last-msg> <time>"`).
Treat that list as your work-queue, but always click by name, and if a new row
appears at the top (a fresh message) re-read the queue.

## Extract a thread

After clicking, the docked window mounts a composer with
`aria-label="Write to <Name> · <listing title>"`. Anchor on it, walk up ~15
ancestors to the window root, and parse the message lines. Facebook renders each
message with a hidden label `Enter, Message sent <when> by <who>: <text>`:

```js
() => {
  const composers = Array.from(document.querySelectorAll('[contenteditable="true"],[role="textbox"]'))
    .filter(e => (e.getAttribute('aria-label') || '').startsWith('Write to '));
  if (!composers.length) return { err: 'no open chat' };
  const composer = composers[0];
  const thread = composer.getAttribute('aria-label').replace(/^Write to /, '');
  let big = composer;
  for (let i = 0; i < 15; i++) { if (big.parentElement) big = big.parentElement; }
  const lines = (big.innerText || '').split('\n');
  const msgs = [];
  const re = /^Enter, Message sent (.+?) by ([^:]+?): ([\s\S]*)$/;
  for (const ln of lines) { const m = ln.match(re); if (m) msgs.push(m[1] + ' — ' + m[2] + ': ' + m[3]); }
  const price = lines.find(l => /AU\$/.test(l));   // listing price header, e.g. "AU$35 – <title>"
  return { thread, price, msgs };
}
```

Notes:
- `msgs` comes out in chronological order: `"<when> — <You|Buyer>: <text>"`.
  `<when>` is FB's own relative/absolute stamp ("Tuesday 7:45pm", "8:38 AM",
  "May 27, 2026, 11:55 AM") — keep it; it anchors date resolution.
- `price` is the **listing** price (the AU$ header). The agreed price may differ
  if they haggled — read the messages for the final figure.
- If `msgs` is empty but a composer exists, the thread is still loading — wait
  another 2 s and re-run.
- If there is **no** composer at all, the click didn't land (dock full, or the
  name matched a stale row) — close all windows and re-click by name.

## One thing to avoid

Don't try to read threads from the top-bar Messenger drawer or the Notifications
flyout — those are separate overlays and contain your general Messenger chats,
not the Marketplace buyer threads. If `evaluate_script` starts returning
"Notifications" / "Chats" text, press `Escape` and re-navigate to
`/marketplace/inbox`.

## Classification rubric

Bucket each thread from its messages:

- **confirmed** — a day AND a time are agreed by both sides ("Saturday ~9am?" →
  "yeah that's fine"). Goes in the calendar.
- **agreed-time-TBC** — both want to trade and a day is loosely set but no firm
  time ("tomorrow morning" with no hour, or you proposed and they haven't
  replied with a time). Worth a calendar hold marked TBC + a nudge.
- **declined / dead** — haggle stalled below your floor, buyer bought elsewhere,
  or either side said no.
- **inquiry-only** — "is this still available?" with no arrangement.

For each confirmed/TBC item capture: **buyer**, **item**, **date** (resolved —
see below), **time**, **agreed price**, **location**, and any **action note**
("text before leaving", "have it ready by the door", "leaving cash in the
drawer / PayID").

### Resolve relative dates

FB stamps and buyer phrasing are relative. Resolve against **today in
Melbourne**:

- "tonight" → today's date.
- "tomorrow" → today + 1.
- a weekday name ("Friday") → the next occurrence of that weekday (today if it
  *is* that weekday and the time is still ahead).
- A stamp like "Tuesday 7:45pm" on a message is when it was *sent* — use it only
  to order messages, not as the pickup date; the pickup date comes from the
  agreement text.

### Pickup vs delivery location

- **Delivery** (buyer asked you to drop off) → location is the **buyer's
  address**, which they'll have pasted in the thread.
- **Pickup** (buyer collects) → location is the **seller's address** if it
  appears in the thread; otherwise leave it as "your place" — **never hardcode
  an address**.
