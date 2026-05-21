#!/usr/bin/env python3
"""
Phase R2 listing.md updater for `/resell-au refresh`.

After a successful delete+recreate cycle, mutate the item's `listing.md`
in place along these axes only:

  - **URL:**   → set to the new URL (insert the line if absent).
  - **Date:**  → set to today's date in ISO format.
  - **Price:** → UNCHANGED. The price-drop calculator lives in Sub-task #4.
  - **## Refresh history** → append a bullet, creating the section if it
    does not yet exist. Section is placed between `## Seller notes` and
    `## Comps`.
  - **## Comps** → byte-identical. The script will refuse to write if the
    Comps block (from `## Comps` to end-of-file) is modified.

Everything else (Ad copy, Seller notes body, Comp data) is preserved.

Run:

    python3 refresh_listing_md_update.py <listing.md path>             \\
        --old-url <old_url> --new-url <new_url> --age-days N           \\
        [--old-price X --new-price Y]   # omit both = price unchanged
        [--dry-run]                     # print to stdout instead

For deterministic testing, set REFRESH_R2_TODAY=YYYY-MM-DD.
"""

from __future__ import annotations

import argparse
import os
import re
import sys
from datetime import date, datetime
from pathlib import Path


RE_DATE_LINE = re.compile(r"^(\*\*Date:\*\*\s+)\S+", re.MULTILINE)
RE_URL_LINE = re.compile(r"^(\*\*URL:\*\*\s+)\S+", re.MULTILINE)
RE_PLATFORM_LINE = re.compile(r"^\*\*Platform:\*\*\s+.+$", re.MULTILINE)
RE_REFRESH_HEADING = re.compile(r"^##\s+Refresh history\s*$", re.MULTILINE)
RE_COMPS_HEADING = re.compile(r"^##\s+Comps\b.*$", re.MULTILINE)
RE_REFRESH_BULLET_NUMBER = re.compile(
    r"^-\s+\d{4}-\d{2}-\d{2}\s+\(refresh #(\d+)\):", re.MULTILINE
)
RE_NEXT_HEADING = re.compile(r"^##\s+\S", re.MULTILINE)


def today_from_env() -> date:
    override = os.environ.get("REFRESH_R2_TODAY")
    if override:
        return datetime.strptime(override, "%Y-%m-%d").date()
    return date.today()


def update_listing(
    text: str,
    *,
    new_url: str,
    today: date,
    old_url: str,
    old_price: int | None,
    new_price: int | None,
    age_days: int,
) -> str:
    """Return the updated text. Raises ValueError on contract violations
    (missing **Date:** line, missing both **URL:** and **Platform:**)."""
    original_comps = _extract_comps_block(text)

    if not RE_DATE_LINE.search(text):
        raise ValueError("listing.md has no **Date:** line — refusing to update")
    text = RE_DATE_LINE.sub(
        lambda m: f"{m.group(1)}{today.isoformat()}", text, count=1
    )

    if RE_URL_LINE.search(text):
        text = RE_URL_LINE.sub(lambda m: f"{m.group(1)}{new_url}", text, count=1)
    else:
        platform_match = RE_PLATFORM_LINE.search(text)
        if not platform_match:
            raise ValueError(
                "listing.md has neither **URL:** nor **Platform:** line — "
                "cannot place the URL line"
            )
        insert_at = platform_match.end()
        text = text[:insert_at] + f"\n**URL:** {new_url}" + text[insert_at:]

    bullet = _format_refresh_bullet(
        today=today,
        refresh_n=_next_refresh_number(text),
        old_price=old_price,
        new_price=new_price,
        old_url=old_url,
        new_url=new_url,
        age_days=age_days,
    )
    text = _insert_refresh_bullet(text, bullet)

    # Final guard: Comps must be byte-identical end-to-end.
    if _extract_comps_block(text) != original_comps:
        raise ValueError(
            "internal error: ## Comps block changed during update — refusing to write"
        )
    return text


def _format_refresh_bullet(
    *,
    today: date,
    refresh_n: int,
    old_price: int | None,
    new_price: int | None,
    old_url: str,
    new_url: str,
    age_days: int,
) -> str:
    if old_price is not None and new_price is not None:
        price_part = f"${old_price} → ${new_price}"
    elif old_price is not None:
        price_part = f"${old_price} (price unchanged)"
    else:
        price_part = "price unchanged"
    return (
        f"- {today.isoformat()} (refresh #{refresh_n}): {price_part}. "
        f"Old URL: {old_url}. New URL: {new_url}. "
        f"Age at refresh: {age_days}d."
    )


def _next_refresh_number(text: str) -> int:
    existing = RE_REFRESH_BULLET_NUMBER.findall(text)
    if existing:
        return max(int(n) for n in existing) + 1
    return 1


def _insert_refresh_bullet(text: str, bullet: str) -> str:
    if RE_REFRESH_HEADING.search(text):
        return _append_to_refresh_section(text, bullet)
    return _create_refresh_section(text, bullet)


def _append_to_refresh_section(text: str, bullet: str) -> str:
    heading_match = RE_REFRESH_HEADING.search(text)
    assert heading_match is not None
    after_heading = heading_match.end()
    next_heading = RE_NEXT_HEADING.search(text, pos=after_heading)
    if next_heading:
        section_end = next_heading.start()
        before = text[:section_end].rstrip("\n")
        tail = text[section_end:]
        return before + "\n" + bullet + "\n\n" + tail
    # No following heading — section is at end of file.
    before = text.rstrip("\n")
    return before + "\n" + bullet + "\n"


def _create_refresh_section(text: str, bullet: str) -> str:
    section_body = f"## Refresh history\n\n{bullet}\n\n"
    comps_match = RE_COMPS_HEADING.search(text)
    if comps_match:
        insert_at = comps_match.start()
        head = text[:insert_at].rstrip("\n")
        tail = text[insert_at:]
        return head + "\n\n" + section_body + tail
    # No Comps section — append at end of file.
    return text.rstrip("\n") + "\n\n" + section_body.rstrip("\n") + "\n"


def _extract_comps_block(text: str) -> str:
    """Return the Comps block (from `## Comps` to end-of-file) for
    byte-identical comparison. Empty string if there is no Comps section."""
    match = RE_COMPS_HEADING.search(text)
    if not match:
        return ""
    return text[match.start():]


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("listing_md", type=Path,
                        help="Path to the item's listing.md")
    parser.add_argument("--old-url", required=True,
                        help="The pre-refresh listing URL (for history bullet).")
    parser.add_argument("--new-url", required=True,
                        help="The post-recreate listing URL (writes to **URL:**).")
    parser.add_argument("--age-days", type=int, required=True,
                        help="Days between the previous **Date:** and today.")
    parser.add_argument("--old-price", type=int, default=None,
                        help="Price before refresh. Omit with --new-price for "
                             "price-unchanged bullet wording.")
    parser.add_argument("--new-price", type=int, default=None,
                        help="Price after refresh. In Sub-task #3 (constant "
                             "price), pass the same value as --old-price.")
    parser.add_argument("--dry-run", action="store_true",
                        help="Print updated text to stdout instead of writing.")
    args = parser.parse_args(argv[1:])

    if (args.old_price is None) != (args.new_price is None):
        print("pass --old-price AND --new-price together, or neither", file=sys.stderr)
        return 2

    path = args.listing_md.expanduser().resolve()
    if not path.exists():
        print(f"not found: {path}", file=sys.stderr)
        return 2

    original = path.read_text(encoding="utf-8")
    try:
        updated = update_listing(
            original,
            new_url=args.new_url,
            today=today_from_env(),
            old_url=args.old_url,
            old_price=args.old_price,
            new_price=args.new_price,
            age_days=args.age_days,
        )
    except ValueError as e:
        print(f"refusing to update: {e}", file=sys.stderr)
        return 3

    if args.dry_run:
        sys.stdout.write(updated)
    else:
        path.write_text(updated, encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
