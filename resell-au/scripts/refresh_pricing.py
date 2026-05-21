#!/usr/bin/env python3
"""
Price-drop calculator for `/resell-au refresh`.

Pure-deterministic helper used by:

  - Phase R0 (refresh_r0_classify.py) — proposed price in the candidate
    table.
  - Phase R0 floor gate — operator overrides resolve through this same
    calculator so per-item `$X` and bulk "drop everything N%" stay
    clamped to the listing's floor.
  - Phase R2 (the refresh recreate flow) — final price written to the
    new FB listing and recorded in the listing.md refresh-history
    bullet.

The single source of truth for two rules:

  - Seller rounding (matches Pricing model § 7 in SKILL.md):
      under  $30  → whole dollars (round-half-up)
      $30–$200    → nearest $5
      $200–$1000  → nearest $10
      $1000+      → nearest $25

  - Price-drop: `proposed = max(floor, seller_round(current * (1 - drop)))`
    where `drop` defaults to 0.10 and the floor is non-negotiable.
    Floor absent → falls back to `seller_round(current * 0.85)` (matches
    Pricing model § 5 "floor = target × 0.90" applied to the −15% gap
    between list and target).

Run from the shell for one-off debugging:

    python3 refresh_pricing.py --current 40 --floor 35
    35
    python3 refresh_pricing.py --current 100 --floor 80 --drop 0.15
    85

The CLI prints the proposed price as a single integer.
"""

from __future__ import annotations

import argparse
import sys


DEFAULT_DROP_RATE = 0.10
ABSENT_FLOOR_RATE = 0.85


def round_price(p: float) -> int:
    """Seller rounding from Pricing model § 7. Round-half-up at every band.

    Inputs are treated as positive AUD amounts — the bands are defined
    on positive prices and the rounding shortcut (`int(x + half)`) is
    correct for x ≥ 0 only. Callers should clamp negatives upstream.
    """
    if p < 30:
        return int(p + 0.5)
    if p < 200:
        return int((p + 2.5) / 5) * 5
    if p < 1000:
        return int((p + 5) / 10) * 10
    return int((p + 12.5) / 25) * 25


def proposed_price(
    current: int,
    floor: int | None,
    *,
    drop_rate: float = DEFAULT_DROP_RATE,
) -> int:
    """Return the price-drop proposal: drop, seller-round, then clamp to floor.

    `drop_rate` is the fraction shaved off `current` before rounding.
    The default 0.10 matches the Refresh Mode default in
    `references/refresh-strategy.md`. Bulk overrides ("drop everything
    15%") pass `drop_rate=0.15`; per-item `same` is `drop_rate=0.0`.

    Per-item `$X` overrides do NOT use this function — they call
    `clamp_to_floor(x, floor, current)` instead, since the operator's
    explicit price already encodes the desired drop.
    """
    rounded = round_price(current * (1 - drop_rate))
    return max(_effective_floor(current, floor), rounded)


def clamp_to_floor(price: int, floor: int | None, current: int) -> int:
    """Per-item `$X` override path: trust the operator's number, but never
    let it drop below the floor. `current` is the listing's current price
    used to derive the fallback floor when `floor` is absent."""
    return max(_effective_floor(current, floor), price)


def _effective_floor(current: int, floor: int | None) -> int:
    if floor is not None:
        return floor
    return round_price(current * ABSENT_FLOOR_RATE)


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--current", type=int, required=True,
                        help="Current list price (whole dollars).")
    parser.add_argument("--floor", type=int, default=None,
                        help="Hard floor in whole dollars. Omit to use the "
                             "list_price × 0.85 fallback.")
    parser.add_argument("--drop", type=float, default=DEFAULT_DROP_RATE,
                        help=f"Fraction shaved off current price before "
                             f"rounding (default {DEFAULT_DROP_RATE}).")
    args = parser.parse_args(argv[1:])
    print(proposed_price(args.current, args.floor, drop_rate=args.drop))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
