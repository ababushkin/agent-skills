#!/usr/bin/env python3
"""Triage scraped Facebook housing posts into a comparison table.

Phase 4 of the apartment-hunt-nl skill. Everything here is the deterministic
half of the job: what counts as already-seen, which posts are the same
apartment cross-posted to several groups, and how each listing measures against
the standing criteria. The agent does the language work (reading a Dutch post
and filling in the fields); this script does the bookkeeping, so two runs over
the same input always produce the same table.

Usage:
    python3 triage.py triage <working_folder> <run_file>
    python3 triage.py triage <wf> <run> --dry-run       # table only, write nothing
    python3 triage.py triage <wf> <run> --max-rent 3000 # override a criterion
    python3 triage.py verdict <wf> <post_id> shortlisted
    python3 triage.py verdict <wf> <post_id> rejected --reason "no registration"

`triage` reads <working_folder>/seen.json, prints the markdown table to stdout,
and appends the new listings to seen.json unless --dry-run.

`verdict` is the only supported way to change a listing's verdict, because
seen.json is also hand-edited: it rewrites the file atomically and keeps a .bak.

Run file input:
    {
      "run_started": "2026-07-27T10:15",     # required; dates derive from this
      "groups": [ { "name": "...", "url": "...", "status": "swept" } ],
      "posts": [ {
          "post_id":  "1234567890",           # FB permalink id — primary dedup key
          "url":      "https://www.facebook.com/groups/.../posts/1234567890/",
          "group":    "Huren in Haarlem",
          "author":   "Jan de Vries",
          "posted":   "2026-07-25",
          "photos":   6,
          "text":     "full post body",
          "fields": {                          # filled by the agent in Phase 3
            "price_eur": 1850, "price_basis": "all-in|excl|unknown",
            "city": "Haarlem", "area": "Centrum",
            "size_m2": 55, "rooms": 2,
            "furnished": "yes|no|unknown",
            "registration": "yes|no|unknown",
            "self_contained": "yes|no|unknown",
            "available_from": "2026-09-01", "available_until": "2027-02-28",
            "min_months": 3, "max_months": 6,
            "scam_signals": ["deposit before viewing"]
          }
      } ]
    }

Any field the post does not state is "unknown" (text fields) or null (numbers
and lists). A missing field is never an automatic rejection — it is reported as
`?` so the user can ask.

seen.json holds one record per apartment, not per post. A cross-posted
apartment accumulates every id and every fingerprint it has appeared under, so
that a later run recognises it even if the agent extracts a field differently.
"""

from __future__ import annotations

import argparse
import datetime
import hashlib
import json
import os
import re
import shutil
import sys
import unicodedata
from pathlib import Path
from typing import Any
from urllib.parse import quote

# 2: one record per apartment, keyed by post_ids[] and fingerprints[], replacing
# the singular post_id/fingerprint of version 1. load_seen migrates 1 to 2.
SEEN_VERSION = 2

# Standing criteria. Overridable per run via the CLI flags below.
DEFAULT_MAX_RENT = 2500
DEFAULT_CITIES = ["Haarlem", "Amsterdam"]
DEFAULT_STAY_MIN = 3
DEFAULT_STAY_MAX = 4
# The dates the user actually needs. A duration band alone is not enough: a
# five-month let starting the month they move out fits "3-6 months" perfectly
# and is still useless.
DEFAULT_NEED_FROM = "2026-08-15"
DEFAULT_NEED_UNTIL = "2026-12-05"
REQUIREMENTS = ["furnished", "registration", "self_contained"]

# A post can offer a place, ask for one, or be neither. Only offers belong in
# the comparison table; the groups are full of people advertising themselves.
POST_KINDS = ("offer", "wanted", "other")

REQUIREMENT_LABELS = {
    "furnished": "Furnished",
    "registration": "Registration",
    "self_contained": "Self-contained",
}

# Verdicts the user sets by hand. A record carrying one is never reopened and
# never overwritten.
VERDICTS = ("new", "screened", "shortlisted", "rejected")
USER_VERDICTS = frozenset(VERDICTS[1:])

YES_WORDS = frozenset({"yes", "y", "true", "ja", "j"})
NO_WORDS = frozenset({"no", "n", "false", "nee"})
# Words the agent writes when a post says nothing. Treated as absent, never as
# a value — "unknown" is not a city and not a scam signal.
NULL_WORDS = frozenset({"unknown", "unstated", "none", "null", "n/a", ""})


# --------------------------------------------------------------------------
# Value coercion
#
# Every field here was filled in by a language model reading free text, so each
# reader tolerates the shapes that actually turn up: "Yes" for true, "1500" for
# 1500, a bare string where a list belongs.
# --------------------------------------------------------------------------


def fields_of(post: dict[str, Any]) -> dict[str, Any]:
    fields = post.get("fields")
    return fields if isinstance(fields, dict) else {}


def as_number(value: Any) -> float | int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return value
    if isinstance(value, str) and re.fullmatch(r"\d+(\.\d+)?", value.strip()):
        text = value.strip()
        return float(text) if "." in text else int(text)
    return None


def as_text(value: Any) -> str:
    """A stated string value, or '' when the field says nothing."""
    if not isinstance(value, str):
        return ""
    text = value.strip()
    return "" if text.casefold() in NULL_WORDS else text


def as_signal_list(value: Any) -> list[str]:
    """Scam signals, tolerating a bare string where a list belongs.

    Without the isinstance guard a string is iterable and each character
    becomes its own flag.
    """
    if isinstance(value, str):
        value = [value]
    if not isinstance(value, list):
        return []
    return [as_text(item) or "" for item in value if as_text(item)]


def as_date(value: Any) -> datetime.date | None:
    text = as_text(value)
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", text):
        return None
    try:
        return datetime.date.fromisoformat(text)
    except ValueError:
        return None


def post_kind(post: dict[str, Any]) -> str:
    """Whether the post offers a place, wants one, or is neither.

    Defaults to "offer" when unset, so a run file that predates this field still
    triages as before rather than silently emptying the table.
    """
    kind = as_text(fields_of(post).get("post_kind")).casefold()
    return kind if kind in POST_KINDS else "offer"


def check_requirement(value: Any) -> str:
    """Normalise a tri-state field to pass / fail / unknown."""
    if value is True:
        return "pass"
    if value is False:
        return "fail"
    if isinstance(value, str):
        word = value.strip().casefold()
        if word in YES_WORDS:
            return "pass"
        if word in NO_WORDS:
            return "fail"
    return "unknown"


# --------------------------------------------------------------------------
# Fingerprinting
# --------------------------------------------------------------------------


def normalise_text(text: str) -> str:
    """Fold accents, drop punctuation, casefold.

    Unicode-aware on purpose: the names in these groups are Dutch, Turkish,
    Arabic, Polish, and Russian. An ASCII-only filter erases a Cyrillic or
    Arabic name to the empty string, which would fingerprint several unrelated
    landlords identically and silently merge their listings into one row.
    """
    decomposed = unicodedata.normalize("NFKD", text)
    unaccented = "".join(c for c in decomposed if not unicodedata.combining(c))
    return re.sub(r"[^\w]+", " ", unaccented).strip().casefold()


def num_part(value: Any) -> str:
    number = as_number(value)
    return f"{number:g}" if number is not None else "?"


def fingerprint(post: dict[str, Any]) -> str:
    """Identify the apartment, not the post.

    Built from the extracted fields rather than the post body: the same person
    advertising the same rent, address and size is one apartment, however
    differently they word it for each group. Body text is the wrong basis —
    cross-posters add a greeting, emoji, or group hashtags every time.
    """
    fields = fields_of(post)
    author = normalise_text(str(post.get("author") or ""))
    parts = [
        author,
        num_part(fields.get("price_eur")),
        normalise_text(as_text(fields.get("city"))),
        normalise_text(as_text(fields.get("area"))),
        num_part(fields.get("size_m2")),
        num_part(fields.get("rooms")),
    ]
    # With no author, or with neither rent nor size, a post has too little
    # identity to match on. Fall back to the body: showing a duplicate row is a
    # far cheaper mistake than hiding a real listing.
    if not author or (parts[1] == "?" and parts[4] == "?"):
        parts.append(normalise_text(str(post.get("text") or ""))[:120])
    return "|".join(parts)


def synthetic_id(fp: str) -> str:
    """A stable id for a post whose permalink could not be read.

    Every listing needs an id, because the id is how the user names it when
    setting a verdict. Derived from the fingerprint, so it is the same on every
    run over the same post.
    """
    return "fp:" + hashlib.blake2s(fp.encode("utf-8"), digest_size=6).hexdigest()


# --------------------------------------------------------------------------
# seen.json
# --------------------------------------------------------------------------


class SeenError(Exception):
    """seen.json exists but cannot be used. Never overwrite it in this case."""


def empty_seen() -> dict[str, Any]:
    return {"version": SEEN_VERSION, "last_run": None, "posts": []}


def load_seen(path: Path) -> dict[str, Any]:
    """Read seen.json, tolerating the shapes a hand-edit leaves behind."""
    if not path.exists():
        backup = path.with_name(path.name + ".bak")
        if backup.exists():
            # Starting fresh here would report every listing as new and, one run
            # later, overwrite the backup that still holds the user's verdicts.
            raise SeenError(
                f"{path} is missing but {backup.name} is here — a previous write "
                f"was interrupted. Restore it first:  mv '{backup}' '{path}'"
            )
        return empty_seen()
    if path.is_dir():
        raise SeenError(f"{path} is a directory, not a file")

    raw = path.read_text(encoding="utf-8").strip()
    if not raw:
        return empty_seen()
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise SeenError(f"{path} is not valid JSON ({exc}). Fix it by hand.") from exc

    if isinstance(data, list):
        data = {"posts": data}
    if not isinstance(data, dict):
        raise SeenError(f"{path} must hold an object or an array, not {type(data).__name__}")

    posts = data.get("posts", [])
    if not isinstance(posts, list):
        raise SeenError(f"{path}: 'posts' must be an array, not {type(posts).__name__}")
    data["posts"] = [record for record in posts if isinstance(record, dict)]
    data.setdefault("last_run", None)

    for record in data["posts"]:
        migrate_record(record)
    data["version"] = SEEN_VERSION
    return data


def migrate_record(record: dict[str, Any]) -> None:
    """Fold the singular legacy keys into the list form, in place."""
    ids = record.setdefault("post_ids", [])
    if not isinstance(ids, list):
        record["post_ids"] = ids = []
    legacy_id = record.pop("post_id", None)
    if legacy_id and str(legacy_id) not in ids:
        ids.insert(0, str(legacy_id))
    record["post_ids"] = [str(i) for i in ids if str(i)]

    prints = record.setdefault("fingerprints", [])
    if not isinstance(prints, list):
        record["fingerprints"] = prints = []
    legacy_fp = record.pop("fingerprint", None)
    if legacy_fp and legacy_fp not in prints:
        prints.insert(0, legacy_fp)

    groups = record.get("groups")
    if not isinstance(groups, list):
        record["groups"] = [groups] if isinstance(groups, str) else []


def prefer(current: dict | None, candidate: dict) -> dict:
    """On a duplicate key in seen.json, keep the record the user judged."""
    if current is None:
        return candidate
    if current.get("verdict") in USER_VERDICTS:
        return current
    if candidate.get("verdict") in USER_VERDICTS:
        return candidate
    return current


def index_seen(seen: dict[str, Any]) -> tuple[dict[str, dict], dict[str, dict]]:
    """Map every known post id and every known fingerprint to its record."""
    by_id: dict[str, dict] = {}
    by_fp: dict[str, dict] = {}
    for record in seen["posts"]:
        for post_id in record.get("post_ids", []):
            by_id[post_id] = prefer(by_id.get(post_id), record)
        for fp in record.get("fingerprints", []):
            by_fp[fp] = prefer(by_fp.get(fp), record)
    return by_id, by_fp


def save_seen(path: Path, seen: dict[str, Any]) -> None:
    """Write seen.json atomically, keeping the previous copy as .bak.

    The user edits this file by hand and it is the only record of which
    listings they have already judged. A truncated write loses that for good,
    so the new content lands in a temp file alongside it and replaces the
    original in one step.

    The backup is a copy, not a rename: renaming would leave an instant where
    seen.json does not exist at all, and a kill in that window looks to the next
    run like a first run.
    """
    if not path.parent.is_dir():
        raise SeenError(f"cannot write {path}: {path.parent} is not a directory")

    body = json.dumps(seen, indent=2, ensure_ascii=False) + "\n"
    tmp = path.with_name(path.name + ".tmp")
    try:
        tmp.write_text(body, encoding="utf-8")
        if path.exists():
            shutil.copy2(path, path.with_name(path.name + ".bak"))
        os.replace(tmp, path)
    except OSError:
        tmp.unlink(missing_ok=True)
        raise


# --------------------------------------------------------------------------
# Scoring
# --------------------------------------------------------------------------


def fmt_eur(amount: float | int) -> str:
    return f"€{amount:,.0f}".replace(",", ".")


def city_status(fields: dict[str, Any], cities: list[str]) -> str:
    name = as_text(fields.get("city"))
    if not name:
        return "unknown"
    targets = {c.strip().casefold() for c in cities}
    return "pass" if name.casefold() in targets else "fail"


def fmt_day(day: datetime.date) -> str:
    return day.strftime("%-d %b")


def check_dates(fields: dict[str, Any], crit: dict[str, Any]) -> tuple[list[str], list[str]]:
    """Compare the listing's availability against the dates the user needs.

    Returns (fails, warns). A listing whose window does not reach the user's
    window is a fail however well it scores on everything else — this is the
    check that separates "3 to 6 months" from "the 3 to 6 months I need".
    """
    need_from, need_until = crit.get("need_from"), crit.get("need_until")
    if not need_from or not need_until:
        return [], []

    start = as_date(fields.get("available_from"))
    end = as_date(fields.get("available_until"))
    if start is None and end is None:
        return [], ["dates unstated"]

    # An unstated side is open-ended, not absent: "from 1 September" with no end
    # is a place that may well still be free in December.
    lo = max(start or need_from, need_from)
    hi = min(end or need_until, need_until)
    if lo > hi:
        if start is not None and start > need_until:
            return [f"free from {fmt_day(start)}, after you leave"], []
        return [f"ends {fmt_day(end)}, before you arrive"], []

    covered = (hi - lo).days + 1
    needed = (need_until - need_from).days + 1
    if covered < 28:
        return [f"only covers {covered}d of your window"], []
    if covered < needed:
        return [], [f"covers {fmt_day(lo)}–{fmt_day(hi)} of your window"]
    return [], []


def evaluate(post: dict[str, Any], crit: dict[str, Any]) -> dict[str, Any]:
    """Measure one post against the criteria. Flags, never drops."""
    fields = fields_of(post)
    fails: list[str] = []
    warns: list[str] = []

    price = as_number(fields.get("price_eur"))
    if price is None:
        warns.append("no price")
    elif price > crit["max_rent"]:
        fails.append(f"{fmt_eur(price)} over budget")

    if as_text(fields.get("price_basis")).casefold() == "excl":
        warns.append("excl. servicekosten")

    city = city_status(fields, crit["cities"])
    if city == "fail":
        fails.append(f"city: {as_text(fields.get('city'))}")
    elif city == "unknown":
        warns.append("city unstated")

    checks = {name: check_requirement(fields.get(name)) for name in REQUIREMENTS}
    for name, result in checks.items():
        if result == "fail":
            fails.append(REQUIREMENT_LABELS[name].lower() + ": no")

    # Stay length. The landlord's window has to overlap the user's. A post
    # stating only one side of its window can still work, so it stays silent;
    # only a stated bound that rules the user out is a fail.
    stay_min = as_number(fields.get("min_months"))
    stay_max = as_number(fields.get("max_months"))
    if stay_min is not None and stay_min > crit["stay_max"]:
        fails.append(f"min stay {stay_min:g}mo")
    if stay_max is not None and stay_max < crit["stay_min"]:
        fails.append(f"max stay {stay_max:g}mo")
    if stay_min is None and stay_max is None:
        warns.append("stay length unstated")

    date_fails, date_warns = check_dates(fields, crit)
    fails += date_fails
    warns += date_warns

    if as_number(post.get("photos")) == 0:
        warns.append("no photos")

    for signal in as_signal_list(fields.get("scam_signals")):
        warns.append(f"⚠ {signal}")

    unknowns = sum(1 for result in checks.values() if result == "unknown")
    return {"checks": checks, "fails": fails, "warns": warns, "unknowns": unknowns}


def rank_key(row: dict[str, Any]) -> tuple:
    price = as_number(fields_of(row["post"]).get("price_eur"))
    return (
        len(row["score"]["fails"]),
        row["score"]["unknowns"],
        len(row["score"]["warns"]),
        price if price is not None else float("inf"),
        row["post_ids"][0],
    )


# --------------------------------------------------------------------------
# Rendering
# --------------------------------------------------------------------------

MARK = {"pass": "✓", "fail": "✗", "unknown": "?"}

COLUMNS = [
    "Price €/mo",
    "City / area",
    "m²",
    "Rooms",
    "Furn",
    "Reg",
    "Self-cont",
    "Available",
    "Posted",
    "Group(s)",
    "Flags",
    "Link",
]

# Control characters, plus the bidi marks, overrides and isolates. All of these
# come from the post text, which a stranger wrote: left in place they can break
# the table apart or reorder what the user reads. Written as escapes because the
# characters themselves are invisible in an editor.
UNSAFE_CHARS = re.compile(
    "[\x00-\x1f\x7f-\x9f\u200e\u200f\u202a-\u202e\u2066-\u2069]"
)

# Everything a URL may keep. Brackets, parentheses, quotes, backslash, pipe and
# whitespace are escaped, so the link cannot end early and smuggle in markdown.
URL_SAFE = ":/?#@!$&*+,;=~-._%"


def escape_cell(value: Any) -> str:
    text = UNSAFE_CHARS.sub(" ", str(value))
    text = text.replace("\\", "\\\\").replace("|", "\\|")
    return " ".join(text.split()) or "—"


def fmt_link(url: Any) -> str:
    if not isinstance(url, str):
        return "—"
    cleaned = UNSAFE_CHARS.sub("", url).strip()
    if not re.match(r"^https?://", cleaned, re.IGNORECASE):
        return "—"
    return f"[post]({quote(cleaned, safe=URL_SAFE)})"


def fmt_price(fields: dict[str, Any]) -> str:
    price = as_number(fields.get("price_eur"))
    if price is None:
        return "unknown"
    basis = as_text(fields.get("price_basis")).casefold()
    if basis == "all-in":
        return f"{fmt_eur(price)} all-in"
    if basis == "excl":
        return f"{fmt_eur(price)} excl."
    return f"{fmt_eur(price)} (?)"


def fmt_place(fields: dict[str, Any]) -> str:
    city = as_text(fields.get("city")) or "unknown"
    area = as_text(fields.get("area"))
    return f"{city} / {area}" if area else city


def fmt_available(fields: dict[str, Any]) -> str:
    start = as_text(fields.get("available_from"))
    end = as_text(fields.get("available_until"))
    if start and end:
        return f"{start} → {end}"
    if start:
        return f"from {start}"
    if end:
        return f"until {end}"
    return "?"


def fmt_number(value: Any) -> str:
    number = as_number(value)
    return f"{number:g}" if number is not None else "?"


def render_row(row: dict[str, Any]) -> str:
    post = row["post"]
    fields = fields_of(post)
    checks = row["score"]["checks"]
    flags = row["score"]["fails"] + row["score"]["warns"]
    if len(row["groups"]) > 1:
        flags = [f"cross-posted ×{len(row['groups'])}"] + flags
    cells = [
        fmt_price(fields),
        fmt_place(fields),
        fmt_number(fields.get("size_m2")),
        fmt_number(fields.get("rooms")),
        MARK[checks["furnished"]],
        MARK[checks["registration"]],
        MARK[checks["self_contained"]],
        fmt_available(fields),
        as_text(post.get("posted")) or "?",
        ", ".join(row["groups"]),
        "; ".join(flags),
    ]
    rendered = [escape_cell(cell) for cell in cells]
    rendered.append(fmt_link(post.get("url")))
    return "| " + " | ".join(rendered) + " |"


def plural(count: int, noun: str) -> str:
    return f"{count} {noun}" if count == 1 else f"{count} {noun}s"


def render(rows: list[dict], stats: dict[str, int], crit: dict[str, Any], pending: list[str]) -> str:
    lines: list[str] = []
    if rows:
        lines.append("| " + " | ".join(COLUMNS) + " |")
        lines.append("|" + "|".join(["---"] * len(COLUMNS)) + "|")
        lines += [render_row(row) for row in rows]
    else:
        lines.append("_No new listings._")
    lines.append("")
    lines.append(
        "_Criteria: ≤ {rent} all-in · {cities}{window} · {stay_min}–{stay_max} months · "
        "furnished, registration, self-contained._".format(
            rent=fmt_eur(crit["max_rent"]),
            cities=" / ".join(crit["cities"]),
            window=(
                " · needs {}–{}".format(
                    fmt_day(crit["need_from"]),
                    crit["need_until"].strftime("%-d %b %Y"),
                )
                if crit.get("need_from") and crit.get("need_until")
                else ""
            ),
            stay_min=crit["stay_min"],
            stay_max=crit["stay_max"],
        )
    )
    lines.append(
        "_Swept {scanned}: {new} new, {seen} already seen, {merged} merged as "
        "cross-posts, {not_listing} not listings (people looking)._".format(
            scanned=plural(stats["scanned"], "post"),
            new=stats["new"],
            seen=stats["seen"],
            merged=stats["merged"],
            not_listing=stats["not_listing"],
        )
    )
    if pending:
        lines.append(
            "_Incomplete run: {count} still pending ({names}). Finish the sweep "
            "before relying on this table; last_run was not advanced._".format(
                count=plural(len(pending), "group"), names=", ".join(pending)
            )
        )
    return "\n".join(lines) + "\n"


# --------------------------------------------------------------------------
# Triage
# --------------------------------------------------------------------------


def triage(run: dict[str, Any], seen: dict[str, Any], crit: dict[str, Any]) -> tuple[list, dict]:
    by_id, by_fp = index_seen(seen)
    rows: list[dict[str, Any]] = []
    rows_by_fp: dict[str, dict[str, Any]] = {}
    others: list[dict[str, Any]] = []
    stats = {"scanned": 0, "new": 0, "seen": 0, "merged": 0, "not_listing": 0}

    posts = run.get("posts")
    for post in posts if isinstance(posts, list) else []:
        if not isinstance(post, dict):
            continue
        stats["scanned"] += 1
        fp = fingerprint(post)
        post_id = str(post.get("post_id") or "").strip() or synthetic_id(fp)
        group = as_text(post.get("group")) or "unknown group"

        known = by_id.get(post_id) or by_fp.get(fp)
        if known is not None:
            stats["seen"] += 1
            # Record the id and fingerprint this apartment turned up under, so
            # the match survives the agent extracting a field differently next
            # time. Without this, a verdict the user set is one re-read away
            # from being forgotten.
            if post_id not in known["post_ids"]:
                known["post_ids"].append(post_id)
                by_id[post_id] = known
            if fp not in known["fingerprints"]:
                known["fingerprints"].append(fp)
                by_fp[fp] = known
            if group not in known["groups"]:
                known["groups"].append(group)
            continue

        existing = rows_by_fp.get(fp)
        if existing is not None:
            stats["merged"] += 1
            if post_id not in existing["post_ids"]:
                existing["post_ids"].append(post_id)
            if group not in existing["groups"]:
                existing["groups"].append(group)
            continue

        row = {
            "post": post,
            "post_ids": [post_id],
            "fingerprints": [fp],
            "groups": [group],
        }
        kind = post_kind(post)
        if kind != "offer":
            # Someone advertising themselves as a tenant, or a general question.
            # Recorded so it is not re-read every run, never tabled.
            stats["not_listing"] += 1
            row["kind"] = kind
            others.append(row)
            rows_by_fp[fp] = row
            continue

        stats["new"] += 1
        row["score"] = evaluate(post, crit)
        rows.append(row)
        rows_by_fp[fp] = row

    rows.sort(key=rank_key)
    return rows, stats, others


def title_for(post: dict[str, Any]) -> str:
    fields = fields_of(post)
    parts = [fmt_place(fields), fmt_price(fields)]
    size = as_number(fields.get("size_m2"))
    if size is not None:
        parts.append(f"{size:g}m²")
    return " · ".join(parts)


def commit(
    seen: dict[str, Any],
    rows: list[dict[str, Any]],
    others: list[dict[str, Any]],
    run_date: str,
) -> None:
    """Append the new listings. Existing records keep whatever verdict they have."""
    for row in rows + others:
        post = row["post"]
        kind = row.get("kind")
        seen["posts"].append(
            {
                "post_ids": list(row["post_ids"]),
                "fingerprints": list(row["fingerprints"]),
                "url": post.get("url"),
                "author": post.get("author"),
                "posted": post.get("posted"),
                "groups": list(row["groups"]),
                "title": title_for(post) if kind is None else f"[{kind}] {post.get('author')}",
                "first_seen": run_date,
                "verdict": "new" if kind is None else "not_a_listing",
            }
        )


def pending_groups(run: dict[str, Any]) -> list[str]:
    groups = run.get("groups")
    if not isinstance(groups, list):
        return []
    return [
        as_text(g.get("name")) or "unnamed group"
        for g in groups
        if isinstance(g, dict) and as_text(g.get("status")).casefold() != "swept"
    ]


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------


def resolve_seen_path(working: Path, override: str | None) -> Path:
    """Locate seen.json, refusing a path whose directory does not exist.

    A folder is never created here. Silently making one turns a typo'd path into
    a second, empty history while the real one sits untouched.
    """
    path = Path(override).expanduser() if override else working / "seen.json"
    if not path.parent.is_dir():
        raise SeenError(f"no such directory: {path.parent}")
    return path


def require_folder(path: Path, what: str) -> str | None:
    if not path.exists():
        return f"{what} not found: {path}. Phase 0 creates the working folder."
    if not path.is_dir():
        return f"{what} is not a directory: {path}"
    return None


def cmd_triage(args: argparse.Namespace) -> int:
    working = Path(args.working_folder).expanduser()
    problem = require_folder(working, "working folder")
    if problem:
        print(f"error: {problem}", file=sys.stderr)
        return 1

    run_path = Path(args.run_file).expanduser()
    if not run_path.is_absolute() and not run_path.exists():
        run_path = working / args.run_file
    if not run_path.exists():
        print(f"error: run file not found: {run_path}", file=sys.stderr)
        return 1

    if args.max_rent <= 0:
        print("error: --max-rent must be positive", file=sys.stderr)
        return 1
    cities = [c.strip() for c in args.cities.split(",") if c.strip()]
    if not cities:
        print("error: --cities must name at least one city", file=sys.stderr)
        return 1
    if args.stay_min < 0 or args.stay_max < args.stay_min:
        print("error: --stay-min must be >= 0 and <= --stay-max", file=sys.stderr)
        return 1

    try:
        run = json.loads(run_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        print(f"error: {run_path} is not valid JSON ({exc})", file=sys.stderr)
        return 1
    if not isinstance(run, dict):
        print(f"error: {run_path} must hold an object", file=sys.stderr)
        return 1

    run_date = str(run.get("run_started") or "")[:10]
    if not run_date:
        print(
            f"error: {run_path} has no 'run_started'. Phase 2 must record it — "
            "every date in seen.json derives from it.",
            file=sys.stderr,
        )
        return 1

    try:
        seen_path = resolve_seen_path(working, args.seen)
        seen = load_seen(seen_path)
    except SeenError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    need_from = as_date(args.need_from) if args.need_from else None
    need_until = as_date(args.need_until) if args.need_until else None
    for flag, raw, parsed in (
        ("--need-from", args.need_from, need_from),
        ("--need-until", args.need_until, need_until),
    ):
        if raw and parsed is None:
            print(f"error: {flag} must be a YYYY-MM-DD date, got {raw!r}", file=sys.stderr)
            return 1
    if need_from and need_until and need_from > need_until:
        print("error: --need-from must be on or before --need-until", file=sys.stderr)
        return 1

    crit = {
        "max_rent": args.max_rent,
        "cities": cities,
        "stay_min": args.stay_min,
        "stay_max": args.stay_max,
        "need_from": need_from,
        "need_until": need_until,
    }
    pending = pending_groups(run)
    rows, stats, others = triage(run, seen, crit)
    sys.stdout.write(render(rows, stats, crit, pending))

    if not args.dry_run:
        commit(seen, rows, others, run_date)
        # A half-swept run must not move the watermark, or the next run's
        # lookback skips whatever the unfinished groups posted.
        if not pending:
            seen["last_run"] = run_date
        try:
            save_seen(seen_path, seen)
        except (SeenError, OSError) as exc:
            print(f"error: could not write {seen_path}: {exc}", file=sys.stderr)
            return 1
    return 0


def cmd_verdict(args: argparse.Namespace) -> int:
    working = Path(args.working_folder).expanduser()
    problem = require_folder(working, "working folder")
    if problem:
        print(f"error: {problem}", file=sys.stderr)
        return 1

    try:
        seen_path = resolve_seen_path(working, args.seen)
        seen = load_seen(seen_path)
    except SeenError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    by_id, by_fp = index_seen(seen)
    wanted = str(args.post_id)
    record = by_id.get(wanted) or by_fp.get(wanted)
    if record is None:
        print(f"error: no listing in {seen_path} with post id {wanted}", file=sys.stderr)
        return 1

    record["verdict"] = args.verdict
    if args.reason:
        record["reject_reason"] = args.reason
    elif args.verdict != "rejected":
        record.pop("reject_reason", None)
    try:
        save_seen(seen_path, seen)
    except (SeenError, OSError) as exc:
        print(f"error: could not write {seen_path}: {exc}", file=sys.stderr)
        return 1
    print(f"{record.get('title') or wanted} → {args.verdict}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Scraped FB housing posts -> a de-duplicated comparison table"
    )
    sub = parser.add_subparsers(dest="command", required=True)

    run_cmd = sub.add_parser("triage", help="triage a run file into a comparison table")
    run_cmd.add_argument("working_folder", help="folder holding seen.json")
    run_cmd.add_argument("run_file", help="run-state JSON written in Phase 2/3")
    run_cmd.add_argument("--max-rent", type=int, default=DEFAULT_MAX_RENT)
    run_cmd.add_argument(
        "--cities",
        default=",".join(DEFAULT_CITIES),
        help="comma-separated list of acceptable cities",
    )
    run_cmd.add_argument("--stay-min", type=int, default=DEFAULT_STAY_MIN)
    run_cmd.add_argument("--stay-max", type=int, default=DEFAULT_STAY_MAX)
    run_cmd.add_argument(
        "--need-from",
        default=DEFAULT_NEED_FROM,
        help="first day the user needs a place (YYYY-MM-DD); '' disables the check",
    )
    run_cmd.add_argument(
        "--need-until",
        default=DEFAULT_NEED_UNTIL,
        help="last day the user needs a place (YYYY-MM-DD); '' disables the check",
    )
    run_cmd.add_argument("--seen", help="override the seen.json path")
    run_cmd.add_argument(
        "--dry-run", action="store_true", help="print the table without writing seen.json"
    )
    run_cmd.set_defaults(func=cmd_triage)

    set_cmd = sub.add_parser("verdict", help="set a listing's verdict in seen.json")
    set_cmd.add_argument("working_folder", help="folder holding seen.json")
    set_cmd.add_argument("post_id", help="any post id the listing has appeared under")
    set_cmd.add_argument("verdict", choices=VERDICTS)
    set_cmd.add_argument("--reason", help="why it was rejected")
    set_cmd.add_argument("--seen", help="override the seen.json path")
    set_cmd.set_defaults(func=cmd_verdict)

    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(sys.argv[1:] if argv is None else argv)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
