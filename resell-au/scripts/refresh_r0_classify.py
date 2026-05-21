#!/usr/bin/env python3
"""
Phase R0 classifier for `/resell-au refresh`.

Walks subfolders of a target directory, parses each listing.md, and prints
a candidate table that classifies every item as one of:

  refresh-eligible — Published + Date ≥7d old + URL present
  too-fresh        — Published + Date <7d old
  no-url           — Published but no **URL:** line (in-memory paste needed)
  sold             — Status: Sold (silently skipped)
  not-published    — no listing.md or unparseable status (silently skipped)

Read-only: writes nothing back to listing.md or anywhere else. Re-running
on the same folder on the same day produces the same table.

Run:
    python3 refresh_r0_classify.py ~/Desktop/things-for-sale/

For deterministic fixture testing, set REFRESH_R0_TODAY=YYYY-MM-DD to
override "today" so age calculations are stable.
"""

import os
import re
import sys
from datetime import date, datetime
from pathlib import Path

STALENESS_DAYS = 7
SESSION_CAP = 5

# Strict regex contracts. listing.md's canonical format is produced by
# Folder Mode Phase 4 — anything that does not match is treated as
# missing rather than guessed at.
RE_STATUS = re.compile(r"^\*\*Status:\*\*\s+(\S+)", re.MULTILINE)
RE_DATE = re.compile(r"^\*\*Date:\*\*\s+(\d{4}-\d{2}-\d{2})", re.MULTILINE)
RE_URL = re.compile(r"^\*\*URL:\*\*\s+(\S+)", re.MULTILINE)
RE_PRICE = re.compile(r"^\*\*Price:\*\*\s+\$(\d+)", re.MULTILINE)
RE_FLOOR = re.compile(r"Floor:\s*\$(\d+)")


def round_price(p: int) -> int:
    """Seller-rounding rules from the Pricing model in SKILL.md."""
    if p < 30:
        return p
    if p < 200:
        return round(p / 5) * 5
    if p < 1000:
        return round(p / 10) * 10
    return round(p / 25) * 25


def proposed_price(current: int, floor: int | None) -> int:
    """−10% clamp-to-floor preview. Sub-task #3 will add override
    handling on top of this default."""
    raw = int(current * 0.9)
    rounded = round_price(raw)
    if floor is None:
        # Absent floor falls back to list_price × 0.85 per Pricing § 5.
        floor = round_price(int(current * 0.85))
    return max(floor, rounded)


def parse_listing(subfolder: Path) -> dict | None:
    """Return parsed fields, or None if listing.md does not exist."""
    listing = subfolder / "listing.md"
    if not listing.exists():
        return None
    text = listing.read_text(encoding="utf-8")
    return {
        "status": (m.group(1) if (m := RE_STATUS.search(text)) else None),
        "date": (m.group(1) if (m := RE_DATE.search(text)) else None),
        "url": (m.group(1) if (m := RE_URL.search(text)) else None),
        "price": int(m.group(1)) if (m := RE_PRICE.search(text)) else None,
        "floor": int(m.group(1)) if (m := RE_FLOOR.search(text)) else None,
    }


def classify(parsed: dict | None, today: date) -> tuple[str, int | None]:
    """Return (classification, age_days_or_None)."""
    if parsed is None:
        return ("not-published", None)
    if parsed["status"] == "Sold":
        return ("sold", None)
    if parsed["status"] != "Published" or not parsed["date"]:
        return ("not-published", None)
    age_days = (today - datetime.strptime(parsed["date"], "%Y-%m-%d").date()).days
    if age_days < STALENESS_DAYS:
        return ("too-fresh", age_days)
    if not parsed["url"]:
        return ("no-url", age_days)
    return ("refresh-eligible", age_days)


def _money(v: int | None) -> str:
    return f"${v}" if v is not None else "—"


def _items(n: int) -> str:
    return f"{n} item" + ("" if n == 1 else "s")


def render_table(rows: list[dict]) -> str:
    out = ["| Item | Age | Current | Proposed | Floor | Action |",
           "|------|-----|---------|----------|-------|--------|"]
    for r in rows:
        age = f"{r['age_days']}d" if r["age_days"] is not None else "—"
        out.append(
            f"| {r['subfolder']} | {age} | {_money(r['price'])} | "
            f"{_money(r['proposed'])} | {_money(r['display_floor'])} | "
            f"{r['action']} |"
        )
    return "\n".join(out)


def today_from_env() -> date:
    override = os.environ.get("REFRESH_R0_TODAY")
    if override:
        return datetime.strptime(override, "%Y-%m-%d").date()
    return date.today()


def main(argv: list[str]) -> int:
    if len(argv) < 2:
        print("usage: refresh_r0_classify.py <folder>", file=sys.stderr)
        return 2
    target = Path(argv[1]).expanduser().resolve()
    if not target.is_dir():
        print(f"not a directory: {target}", file=sys.stderr)
        return 2

    today = today_from_env()
    subfolders = sorted(
        p for p in target.iterdir()
        if p.is_dir() and not p.name.startswith((".", "_"))
    )

    eligible: list[dict] = []
    too_fresh: list[dict] = []
    no_url: list[dict] = []
    silent_skips: list[str] = []  # sold + not-published; not in the table

    for sub in subfolders:
        parsed = parse_listing(sub)
        cls, age = classify(parsed, today)

        if cls in ("sold", "not-published"):
            silent_skips.append(sub.name)
            continue

        row = {
            "subfolder": sub.name,
            "age_days": age,
            "price": parsed["price"] if parsed else None,
            "floor": parsed["floor"] if parsed else None,
            "display_floor": parsed["floor"] if parsed else None,
            "url": parsed["url"] if parsed else None,
            "classification": cls,
        }
        if cls == "refresh-eligible":
            row["proposed"] = (
                proposed_price(row["price"], row["floor"])
                if row["price"] is not None else None
            )
            row["action"] = "refresh"
            eligible.append(row)
        elif cls == "no-url":
            row["proposed"] = (
                proposed_price(row["price"], row["floor"])
                if row["price"] is not None else None
            )
            row["action"] = "no URL — paste required"
            no_url.append(row)
        else:  # too-fresh — hide proposed/floor since no action is taken
            row["proposed"] = None
            row["display_floor"] = None
            row["action"] = "too-fresh, skip"
            too_fresh.append(row)

    # Oldest first so the session cap takes the stalest items.
    eligible.sort(key=lambda r: r["age_days"], reverse=True)
    queued = eligible[:SESSION_CAP]
    deferred = eligible[SESSION_CAP:]
    for r in deferred:
        r["action"] = "deferred to next session"

    # Data-loss warning — prints exactly once per invocation (= per session).
    print("⚠️  Refresh = delete + relist on FB Marketplace.")
    print("    DELETE LOSES: saves, chat history, view count.")
    print("    This is the established tactic for resetting the FB algorithm; the loss is the price.")
    print()
    print(
        f"Found {_items(len(subfolders))}: "
        f"{len(queued)} queued, "
        f"{len(deferred)} deferred, "
        f"{len(no_url)} no-url, "
        f"{len(too_fresh)} too-fresh, "
        f"{len(silent_skips)} silently skipped (sold or no listing.md)."
    )
    print()
    print("## Candidate table")
    print()
    # Order: queued refreshes → no-url → too-fresh → deferred. Visually
    # groups by what the operator can act on first.
    rows = queued + no_url + too_fresh + deferred
    if rows:
        print(render_table(rows))
    else:
        print("(empty — nothing to refresh in this folder.)")
    print()

    if deferred:
        print(f"### Deferred to next session ({_items(len(deferred))})")
        print("Rate-limit hygiene caps refresh at 5 per session.")
        print("Re-run `/resell-au refresh ...` after ≥30 minutes to drain the queue.")

    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
