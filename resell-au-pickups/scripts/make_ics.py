#!/usr/bin/env python3
"""Turn a JSON array of pickup events into a valid iCalendar (.ics) file.

This is the fallback path for the resell-au-pickups skill: when the Google
Calendar MCP connector is read-only (or absent), we hand the user a .ics they
can import in one click instead.

Usage:
    python3 make_ics.py events.json                 # write .ics to stdout
    python3 make_ics.py events.json --out file.ics  # write to a file
    cat events.json | python3 make_ics.py           # read from stdin

Input: a JSON array of event objects. Each object:
    {
      "uid":            "stable-id@resell-au-pickups",   # optional; derived from summary if absent
      "summary":        "Cindy - fog machine pickup ($35)",
      "start":          "2026-06-04T18:00:00",           # naive local Melbourne time
      "end":            "2026-06-04T18:30:00",
      "location":       "2/35-37 Grange Road, Caulfield East VIC",  # optional
      "description":    "Free-text notes. May contain, commas; and newlines.",  # optional
      "alarm_minutes":  30                                # optional; popup reminder lead time
    }

Times are emitted against an Australia/Melbourne VTIMEZONE block so the file is
correct year-round (AEST/AEDT), not just during the current season. Output is
deterministic — no clock reads, no random UIDs — so it is golden-testable.
"""

import argparse
import json
import re
import sys

# Fixed stamp so output is reproducible (golden tests). Calendar clients only
# use DTSTAMP for change-tracking, not for display, so a constant is harmless.
FIXED_DTSTAMP = "20200101T000000Z"

VTIMEZONE = [
    "BEGIN:VTIMEZONE",
    "TZID:Australia/Melbourne",
    "BEGIN:STANDARD",
    "DTSTART:19700405T030000",
    "RRULE:FREQ=YEARLY;BYMONTH=4;BYDAY=1SU",
    "TZOFFSETFROM:+1100",
    "TZOFFSETTO:+1000",
    "TZNAME:AEST",
    "END:STANDARD",
    "BEGIN:DAYLIGHT",
    "DTSTART:19701004T020000",
    "RRULE:FREQ=YEARLY;BYMONTH=10;BYDAY=1SU",
    "TZOFFSETFROM:+1000",
    "TZOFFSETTO:+1100",
    "TZNAME:AEDT",
    "END:DAYLIGHT",
    "END:VTIMEZONE",
]


def slugify(text):
    s = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return s or "event"


def escape_text(value):
    """Escape a text value per RFC 5545 (backslash, semicolon, comma, newline)."""
    return (
        value.replace("\\", "\\\\")
        .replace(";", "\\;")
        .replace(",", "\\,")
        .replace("\r\n", "\\n")
        .replace("\n", "\\n")
        .replace("\r", "\\n")
    )


def fold(line):
    """Fold a content line to 75 octets per RFC 5545, continuation lines start
    with a single space."""
    encoded = line.encode("utf-8")
    if len(encoded) <= 75:
        return line
    out = []
    chunk = encoded[:75]
    out.append(chunk.decode("utf-8"))
    rest = encoded[75:]
    while rest:
        # 74 because the leading space counts toward the 75-octet limit.
        out.append(" " + rest[:74].decode("utf-8"))
        rest = rest[74:]
    return "\r\n".join(out)


def local_stamp(value):
    """'2026-06-04T18:00:00' -> '20260604T180000' (ICS local form)."""
    digits = re.sub(r"[-:]", "", value)
    return digits.replace("T", "T")


def event_lines(ev):
    uid = ev.get("uid") or (slugify(ev["summary"]) + "@resell-au-pickups")
    lines = [
        "BEGIN:VEVENT",
        "UID:" + uid,
        "DTSTAMP:" + ev.get("dtstamp", FIXED_DTSTAMP),
        "DTSTART;TZID=Australia/Melbourne:" + local_stamp(ev["start"]),
        "DTEND;TZID=Australia/Melbourne:" + local_stamp(ev["end"]),
        "SUMMARY:" + escape_text(ev["summary"]),
    ]
    if ev.get("location"):
        lines.append("LOCATION:" + escape_text(ev["location"]))
    if ev.get("description"):
        lines.append("DESCRIPTION:" + escape_text(ev["description"]))
    alarm = ev.get("alarm_minutes")
    if alarm:
        lines += [
            "BEGIN:VALARM",
            "TRIGGER:-PT{}M".format(int(alarm)),
            "ACTION:DISPLAY",
            "DESCRIPTION:" + escape_text(ev["summary"]),
            "END:VALARM",
        ]
    lines.append("END:VEVENT")
    return lines


def build_calendar(events):
    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//resell-au-pickups//make_ics//EN",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
    ]
    lines += VTIMEZONE
    for ev in events:
        lines += event_lines(ev)
    lines.append("END:VCALENDAR")
    return "\r\n".join(fold(ln) for ln in lines) + "\r\n"


def main():
    parser = argparse.ArgumentParser(description="JSON pickup events -> .ics")
    parser.add_argument("input", nargs="?", help="JSON file (default: stdin)")
    parser.add_argument("--out", help="output .ics path (default: stdout)")
    args = parser.parse_args()

    raw = open(args.input, encoding="utf-8").read() if args.input else sys.stdin.read()
    events = json.loads(raw)
    if not isinstance(events, list):
        sys.exit("error: input JSON must be an array of event objects")

    ics = build_calendar(events)
    if args.out:
        with open(args.out, "w", encoding="utf-8", newline="") as fh:
            fh.write(ics)
    else:
        sys.stdout.write(ics)


if __name__ == "__main__":
    main()
