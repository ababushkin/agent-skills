"""
Unit tests for scripts/refresh_pricing.py.

Each test maps to an acceptance criterion in ABA-156 (Sub-task #4 of the
Refresh Mode parent design, ABA-152). The calculator is pure, so unit
tests are the right granularity — Phase R0's golden-file regression at
tests/check_refresh_r0.sh covers the integration path that uses it.

Run:
    bash tests/check_refresh_pricing.sh
    # or directly:
    python3 -m unittest tests.test_refresh_pricing -v
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

from refresh_pricing import (  # noqa: E402
    clamp_to_floor,
    proposed_price,
    round_price,
)


class AcceptanceCriteria(unittest.TestCase):
    """The four worked examples from the ABA-156 acceptance criteria."""

    def test_40_floor_35_drops_to_35(self):
        # 10% drop = $36 → rounds to $35 in the $30–$200 band;
        # floor clamp would also catch it. Both layers agree.
        self.assertEqual(proposed_price(40, 35), 35)

    def test_40_floor_30_drops_to_35(self):
        # 10% drop = $36 → $35; floor at $30 is below, so rounding wins.
        self.assertEqual(proposed_price(40, 30), 35)

    def test_100_floor_80_drops_to_90(self):
        # 10% drop = $90 (already a $5-band number); floor at $80 below.
        self.assertEqual(proposed_price(100, 80), 90)

    def test_25_floor_20_drops_to_23(self):
        # Whole-dollar rounding under $30: 25 × 0.9 = 22.5 → round-half-up
        # → $23. Floor at $20 below.
        self.assertEqual(proposed_price(25, 20), 23)


class PerItemOverrides(unittest.TestCase):
    """AC: User typing `same` keeps the current price.
        AC: User typing `$X` sets that price (clamped to floor)."""

    def test_same_keeps_current_price(self):
        # `same` is modelled as drop_rate=0.0 — no shave, but the rounding
        # band still applies. $40 is already on the $5 grid so it stays
        # exact; the floor is below.
        self.assertEqual(proposed_price(40, 35, drop_rate=0.0), 40)

    def test_dollar_override_above_floor_passes_through(self):
        self.assertEqual(clamp_to_floor(38, 35, 40), 38)

    def test_dollar_override_below_floor_clamps_up(self):
        self.assertEqual(clamp_to_floor(28, 30, 40), 30)

    def test_dollar_override_with_absent_floor_uses_fallback(self):
        # Fallback floor = round_price($40 × 0.85) = round_price($34) = $35.
        # Operator's $30 is below → clamps up to $35.
        self.assertEqual(clamp_to_floor(30, None, 40), 35)


class BulkOverride(unittest.TestCase):
    """AC: User typing 'drop everything 15%' applies −15% to all eligible
    items (still clamped to floor)."""

    def test_drop_15pct_above_floor(self):
        # $100 × 0.85 = $85, on $5 grid, above $80 floor.
        self.assertEqual(proposed_price(100, 80, drop_rate=0.15), 85)

    def test_drop_15pct_clamps_to_floor(self):
        # $40 × 0.85 = $34 → rounds to $35; floor at $35 → result $35.
        # Push the floor up to $38 and the clamp must catch the result.
        self.assertEqual(proposed_price(40, 38, drop_rate=0.15), 38)

    def test_keep_all_prices_is_drop_zero(self):
        # "keep all prices" passes drop_rate=0.0 to every item.
        self.assertEqual(proposed_price(100, 80, drop_rate=0.0), 100)
        self.assertEqual(proposed_price(25, 20, drop_rate=0.0), 25)


class RoundingBands(unittest.TestCase):
    """Sanity tests on the rounding bands themselves, independent of the
    drop. These guard against silent regressions in `round_price`."""

    def test_under_30_round_half_up(self):
        self.assertEqual(round_price(22.5), 23)
        self.assertEqual(round_price(22.49), 22)
        self.assertEqual(round_price(15), 15)

    def test_30_to_200_nearest_five(self):
        self.assertEqual(round_price(36), 35)
        self.assertEqual(round_price(37.5), 40)  # round-half-up
        self.assertEqual(round_price(42), 40)
        self.assertEqual(round_price(45), 45)
        self.assertEqual(round_price(54), 55)
        self.assertEqual(round_price(72), 70)

    def test_200_to_1000_nearest_ten(self):
        self.assertEqual(round_price(234), 230)
        self.assertEqual(round_price(235), 240)  # round-half-up
        self.assertEqual(round_price(350), 350)
        self.assertEqual(round_price(999), 1000)  # crosses band on output

    def test_1000_plus_nearest_twentyfive(self):
        self.assertEqual(round_price(1234), 1225)
        self.assertEqual(round_price(1237.5), 1250)  # round-half-up
        self.assertEqual(round_price(1250), 1250)


class AbsentFloorFallback(unittest.TestCase):
    """Pricing model § 5 fallback: floor = list_price × 0.85 (rounded)."""

    def test_absent_floor_does_not_block_drop(self):
        # $100 × 0.9 = $90 (rounded), above the $85 fallback floor.
        self.assertEqual(proposed_price(100, None), 90)

    def test_absent_floor_clamps_low_drop(self):
        # Drop everything 30%: $100 × 0.70 = $70 → rounded to $70.
        # Fallback floor = $85. Clamp catches it.
        self.assertEqual(proposed_price(100, None, drop_rate=0.30), 85)


class R0ClassifierGoldenStability(unittest.TestCase):
    """The R0 candidate-table golden uses these proposed prices. Keep them
    here so a future change to the calculator that breaks the golden gets
    a clear targeted failure before the golden diff fires."""

    EXPECTED = {
        (50, 35): 45,    # eligible-60d
        (100, 70): 90,   # eligible-30d
        (40, 35): 35,    # eligible-20d
        (80, 60): 70,    # eligible-14d
        (30, 25): 27,    # eligible-10d
        (60, 45): 55,    # no-url-15d
        (25, 20): 23,    # eligible-8d (deferred) — round-half-up fix
    }

    def test_r0_fixture_prices(self):
        for (current, floor), expected in self.EXPECTED.items():
            with self.subTest(current=current, floor=floor):
                self.assertEqual(proposed_price(current, floor), expected)


if __name__ == "__main__":
    unittest.main()
