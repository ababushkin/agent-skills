#!/usr/bin/env python3
"""
Run-state helper for `/resell-au refresh` Phase R1+R2 multi-item loop.

The Refresh Mode run-state file is `<target_folder>/.resell-au-refresh-<YYYYMMDD-HHMM>.json`
(schema in `references/refresh-strategy.md` § "Refresh Mode run-state file").
This script owns three deterministic, testable behaviours:

  init   — Find latest `.resell-au-refresh-*.json` in the target folder.
           If present AND has at least one non-terminal item → reuse it
           (resume case; the input queued list is ignored). Otherwise
           create a new file from the input queued list.  Prints the
           resolved file path to stdout.

  plan   — Read a run-state file and emit a per-item action plan:
             pending     → action: r1   (start fresh from delete)
             deleted     → action: r2   (resume — recreate without re-deleting)
             recreated   → action: done
             skipped     → action: done (operator chose to skip)
             failed      → action: manual (operator decides next step)
           One JSON object per item, one per line (newline-delimited JSON
           keeps the script grep-friendly for shell debugging).

  update — Mutate a single item's status and related fields. Writes back
           atomically (temp + rename) so a kill mid-write can't corrupt
           the file. Auto-stamps the matching `*_at` field on status
           transitions (deleted_at, recreated_at, failed_at).

Resume policy mirrors `references/refresh-strategy.md`:

  | terminal state | what the next run does                         |
  |----------------|------------------------------------------------|
  | pending        | start at R1 (delete then recreate)             |
  | deleted        | start at R2 (do NOT re-delete — would 404)     |
  | recreated      | skip (item is done)                            |
  | skipped        | skip (operator-decided)                        |
  | failed         | surface for manual decision; never auto-retry  |

Run examples:

    # New run — agent has written queued.json from R0 floor-gate output.
    python3 refresh_runstate.py init ~/Desktop/things-for-sale/ \\
        --queued-json /tmp/queued.json

    # Subsequent restart / resume — no --queued-json needed.
    python3 refresh_runstate.py init ~/Desktop/things-for-sale/

    # Per-item action plan (drives the R1+R2 loop).
    python3 refresh_runstate.py plan <runstate_path>

    # Status update after a phase succeeds.
    python3 refresh_runstate.py update <runstate_path> \\
        --item 0 --status deleted --delete-detection redirect

For deterministic testing, set REFRESH_RUNSTATE_NOW=YYYY-MM-DDTHH:MM:SS to
override "now" for both the filename timestamp and the *_at fields.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime
from pathlib import Path


RUNSTATE_PREFIX = ".resell-au-refresh-"
RUNSTATE_SUFFIX = ".json"
RUNSTATE_GLOB = f"{RUNSTATE_PREFIX}*{RUNSTATE_SUFFIX}"

# Rate-limit hygiene: FB Marketplace allows ~5 reposts/session without
# triggering shadowban flags. This mirrors SESSION_CAP in refresh_r0_classify.py.
SESSION_CAP = 5

TERMINAL_STATES = {"recreated", "skipped"}
RESUMABLE_STATES = {"pending", "deleted", "failed"}
ALL_STATES = TERMINAL_STATES | RESUMABLE_STATES

STATUS_TO_ACTION = {
    "pending": "r1",
    "deleted": "r2",
    "recreated": "done",
    "skipped": "done",
    "failed": "manual",
}


def now_from_env() -> datetime:
    override = os.environ.get("REFRESH_RUNSTATE_NOW")
    if override:
        return datetime.fromisoformat(override)
    return datetime.now()


def runstate_filename(when: datetime) -> str:
    return f"{RUNSTATE_PREFIX}{when.strftime('%Y%m%d-%H%M')}{RUNSTATE_SUFFIX}"


def find_latest_runstate(folder: Path) -> Path | None:
    """Return the lexically-greatest run-state file in `folder`, or None.

    The timestamp embedded in the filename (`YYYYMMDD-HHMM`) sorts
    correctly under plain lexicographic order, so the latest file is
    `max(...)` over the matching glob.
    """
    candidates = sorted(folder.glob(RUNSTATE_GLOB))
    return candidates[-1] if candidates else None


def has_unfinished_work(state: dict) -> bool:
    """True if any item is in a non-terminal status (pending/deleted/failed).

    `failed` counts as unfinished — the operator may resume after fixing
    the underlying issue; auto-restart should still pick up the file.
    """
    return any(item.get("status") in RESUMABLE_STATES for item in state.get("items", []))


def load_state(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as fh:
        return json.load(fh)


def write_state_atomic(path: Path, state: dict) -> None:
    """Write JSON to a sibling temp file then rename — kill-during-write
    safe so a `/compact` or crash never leaves the run-state truncated."""
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8") as fh:
        json.dump(state, fh, indent=2, sort_keys=False)
        fh.write("\n")
    tmp.replace(path)


# --------------------------------------------------------------------------- #
# init
# --------------------------------------------------------------------------- #

def _validate_queued(queued: list[dict]) -> None:
    required = {"subfolder", "old_url", "old_price", "new_price", "floor",
                "age_days", "title"}
    for i, item in enumerate(queued):
        missing = required - set(item.keys())
        if missing:
            raise ValueError(
                f"queued item {i} ({item.get('subfolder', '?')}) "
                f"missing fields: {sorted(missing)}"
            )


def _seed_items(queued: list[dict]) -> list[dict]:
    """Materialise the per-item shape for a fresh run-state."""
    out: list[dict] = []
    for q in queued:
        out.append({
            "subfolder": q["subfolder"],
            "title": q["title"],
            "old_url": q["old_url"],
            "old_price": q["old_price"],
            "new_price": q["new_price"],
            "floor": q["floor"],
            "age_days": q["age_days"],
            "refresh_count_before": q.get("refresh_count_before", 0),
            "status": "pending",
            "delete_detection": None,
            "new_url": None,
            "failure_reason": None,
            "pending_at": None,
            "deleted_at": None,
            "recreated_at": None,
            "failed_at": None,
        })
    return out


def cmd_init(args: argparse.Namespace) -> int:
    folder = args.folder.expanduser().resolve()
    if not folder.is_dir():
        print(f"not a directory: {folder}", file=sys.stderr)
        return 2

    latest = find_latest_runstate(folder)
    if latest is not None:
        try:
            state = load_state(latest)
        except (OSError, json.JSONDecodeError) as e:
            print(f"refusing to use unreadable run-state {latest}: {e}",
                  file=sys.stderr)
            return 3
        if has_unfinished_work(state):
            # Resume: ignore --queued-json on purpose. The agent should
            # read the existing file rather than re-seed from R0.
            print(str(latest))
            return 0

    # New run.
    if args.queued_json is None:
        print(
            "no resumable run-state in folder and --queued-json not provided",
            file=sys.stderr,
        )
        return 2
    queued_path = Path(args.queued_json)
    try:
        queued = json.loads(queued_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as e:
        print(f"could not read --queued-json {queued_path}: {e}",
              file=sys.stderr)
        return 2
    if not isinstance(queued, list):
        print("--queued-json must contain a JSON array of items",
              file=sys.stderr)
        return 2
    if not queued:
        print("--queued-json contains zero items — nothing to do",
              file=sys.stderr)
        return 2
    try:
        _validate_queued(queued)
    except ValueError as e:
        print(f"invalid queued items: {e}", file=sys.stderr)
        return 2
    if len(queued) > SESSION_CAP:
        print(
            f"--queued-json contains {len(queued)} items, "
            f"which exceeds session_cap ({SESSION_CAP}). "
            f"Trim to {SESSION_CAP} before running the loop "
            f"(rate-limit hygiene — see refresh-strategy.md).",
            file=sys.stderr,
        )
        return 2

    when = now_from_env()
    new_path = folder / runstate_filename(when)
    state = {
        "run_started": when.isoformat(timespec="seconds"),
        "target_folder": str(folder),
        "session_cap": 5,
        "items": _seed_items(queued),
    }
    write_state_atomic(new_path, state)
    print(str(new_path))
    return 0


# --------------------------------------------------------------------------- #
# plan
# --------------------------------------------------------------------------- #

def build_plan(state: dict) -> list[dict]:
    """Per-item action plan — pure function for unit testing."""
    plan: list[dict] = []
    for idx, item in enumerate(state.get("items", [])):
        status = item.get("status", "pending")
        action = STATUS_TO_ACTION.get(status, "unknown")
        plan.append({
            "item_index": idx,
            "subfolder": item.get("subfolder"),
            "title": item.get("title"),
            "status": status,
            "action": action,
            "old_url": item.get("old_url"),
            "new_url": item.get("new_url"),
            "old_price": item.get("old_price"),
            "new_price": item.get("new_price"),
            "floor": item.get("floor"),
            "age_days": item.get("age_days"),
            "delete_detection": item.get("delete_detection"),
            "failure_reason": item.get("failure_reason"),
        })
    return plan


def cmd_plan(args: argparse.Namespace) -> int:
    state = load_state(args.runstate)
    plan = build_plan(state)
    for entry in plan:
        json.dump(entry, sys.stdout, sort_keys=False)
        sys.stdout.write("\n")
    return 0


# --------------------------------------------------------------------------- #
# update
# --------------------------------------------------------------------------- #

_STATUS_AT_FIELD = {
    "pending": "pending_at",
    "deleted": "deleted_at",
    "recreated": "recreated_at",
    "failed": "failed_at",
    "skipped": "failed_at",
}


def apply_update(
    state: dict,
    item_index: int,
    *,
    status: str | None,
    delete_detection: str | None,
    new_url: str | None,
    failure_reason: str | None,
    now: datetime,
) -> None:
    """Mutate `state` in place. Raises IndexError / ValueError on misuse."""
    items = state.get("items", [])
    if not 0 <= item_index < len(items):
        raise IndexError(
            f"item_index {item_index} out of range (have {len(items)} items)"
        )
    item = items[item_index]

    if status is not None:
        if status not in ALL_STATES:
            raise ValueError(
                f"unknown status {status!r}; expected one of {sorted(ALL_STATES)}"
            )
        item["status"] = status
        at_field = _STATUS_AT_FIELD.get(status)
        if at_field:
            item[at_field] = now.isoformat(timespec="seconds")
    if delete_detection is not None:
        item["delete_detection"] = delete_detection
    if new_url is not None:
        item["new_url"] = new_url
    if failure_reason is not None:
        item["failure_reason"] = failure_reason


def cmd_update(args: argparse.Namespace) -> int:
    state = load_state(args.runstate)
    try:
        apply_update(
            state,
            args.item,
            status=args.status,
            delete_detection=args.delete_detection,
            new_url=args.new_url,
            failure_reason=args.failure_reason,
            now=now_from_env(),
        )
    except (IndexError, ValueError) as e:
        print(f"refusing to update: {e}", file=sys.stderr)
        return 3
    write_state_atomic(args.runstate, state)
    return 0


# --------------------------------------------------------------------------- #
# main
# --------------------------------------------------------------------------- #

def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    p_init = sub.add_parser("init", help="find or create the run-state file")
    p_init.add_argument("folder", type=Path)
    p_init.add_argument("--queued-json", type=str, default=None,
                        help="Path to a JSON array of queued items (required "
                             "when no resumable run-state exists).")
    p_init.set_defaults(func=cmd_init)

    p_plan = sub.add_parser("plan", help="emit per-item action plan as NDJSON")
    p_plan.add_argument("runstate", type=Path)
    p_plan.set_defaults(func=cmd_plan)

    p_update = sub.add_parser("update", help="mutate one item's status")
    p_update.add_argument("runstate", type=Path)
    p_update.add_argument("--item", type=int, required=True,
                          help="0-indexed item position in the items array.")
    p_update.add_argument("--status", type=str, default=None,
                          choices=sorted(ALL_STATES))
    p_update.add_argument("--delete-detection", type=str, default=None,
                          help="redirect | listing_gone_copy | row_missing | "
                               "timeout_manual")
    p_update.add_argument("--new-url", type=str, default=None)
    p_update.add_argument("--failure-reason", type=str, default=None)
    p_update.set_defaults(func=cmd_update)

    args = parser.parse_args(argv[1:])
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main(sys.argv))
