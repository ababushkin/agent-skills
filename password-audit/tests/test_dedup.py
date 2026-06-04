"""
Unit tests for password_audit.py — the dedup / merge logic.

Covers the behaviour that motivated the smarter-dedup change: login/www
subdomain variants of one site collapsing to a single entry, while genuinely
distinct accounts (different user, different stored password, different
registrable domain) stay separate. All fixtures are invented — generic brand
names and example.com users — so this is safe to commit and run anywhere.

Run:
    bash tests/check_dedup.sh
    # or directly:
    python3 -m unittest tests.test_dedup -v
"""

from __future__ import annotations

import csv
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from password_audit import (  # noqa: E402
    dedup,
    dedup_host,
    find_reuse,
    find_title_dupes,
    load_rows,
)


def make_entries(rows):
    """Build entries through the real load path (so each gets its 'site' key).
    `rows` is a list of (title, url, username, password) tuples."""
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "vault.csv"
        with open(path, "w", newline="", encoding="utf-8") as fh:
            writer = csv.writer(fh)
            writer.writerow(["Title", "URL", "Username", "Password", "Notes", "OTPAuth"])
            for title, url, user, pw in rows:
                writer.writerow([title, url, user, pw, "", ""])
        entries, skipped = load_rows(path)
    return entries, skipped


class DedupHost(unittest.TestCase):
    """The leading-label stripper that produces the dedup key."""

    def test_strips_login_www_auth_prefixes(self):
        self.assertEqual(dedup_host("signin.shopmart.com.au"), "shopmart.com.au")
        self.assertEqual(dedup_host("www.shopmart.com.au"), "shopmart.com.au")
        self.assertEqual(dedup_host("accounts.shopmart.com.au"), "shopmart.com.au")
        self.assertEqual(dedup_host("id.taskhub.com"), "taskhub.com")
        self.assertEqual(dedup_host("login.mailbox.com"), "mailbox.com")
        self.assertEqual(dedup_host("auth.techstore.com.au"), "techstore.com.au")

    def test_two_label_floor_never_eats_the_suffix(self):
        # Must never collapse down to a bare public suffix like com.au.
        self.assertEqual(dedup_host("www.taskhub.com"), "taskhub.com")
        self.assertEqual(dedup_host("taskhub.com"), "taskhub.com")

    def test_non_generic_labels_are_kept(self):
        # Different multi-tenant subdomains / sandboxes are real, distinct sites.
        self.assertEqual(dedup_host("alphaco.authportal.com"), "alphaco.authportal.com")
        self.assertEqual(dedup_host("betaco.authportal.com"), "betaco.authportal.com")
        self.assertEqual(dedup_host("www.sandbox.paywave.com"), "sandbox.paywave.com")

    def test_empty_host(self):
        self.assertEqual(dedup_host(""), "")


class SubdomainCollapse(unittest.TestCase):
    """Same site + same user + same password across subdomains -> one entry."""

    def test_three_subdomains_of_one_site_collapse_to_one(self):
        entries, _ = make_entries([
            ("Shopmart signin", "https://signin.shopmart.com.au/login", "user_a", "Sh4r3d!Pw99a"),
            ("Shopmart www", "https://www.shopmart.com.au/", "user_a", "Sh4r3d!Pw99a"),
            ("Shopmart accounts", "https://accounts.shopmart.com.au/", "user_a", "Sh4r3d!Pw99a"),
        ])
        kept, dropped, near = dedup(entries)
        self.assertEqual(len(kept), 1)
        self.assertEqual(len(dropped), 2)
        self.assertEqual(near, [])
        # First occurrence is the one kept — a real working URL, not invented.
        self.assertEqual(kept[0]["url"], "https://signin.shopmart.com.au/login")

    def test_id_and_www_subdomains_collapse(self):
        entries, _ = make_entries([
            ("Taskhub id", "https://id.taskhub.com/", "user_b", "T4sk!Pw99b"),
            ("Taskhub www", "https://www.taskhub.com/", "user_b", "T4sk!Pw99b"),
        ])
        kept, dropped, _ = dedup(entries)
        self.assertEqual(len(kept), 1)
        self.assertEqual(len(dropped), 1)


class StaysSeparate(unittest.TestCase):
    """Cases the collapse must NOT merge."""

    def test_different_users_on_same_subdomain_both_kept(self):
        entries, _ = make_entries([
            ("Shopmart A", "https://signin.shopmart.com.au/login", "user_a", "Aaa!Pw111"),
            ("Shopmart C", "https://signin.shopmart.com.au/login", "user_c@example.com", "Ccc!Pw222"),
        ])
        kept, dropped, near = dedup(entries)
        self.assertEqual(len(kept), 2)
        self.assertEqual(dropped, [])
        self.assertEqual(near, [])

    def test_same_site_user_different_password_is_near_dup_not_dropped(self):
        entries, _ = make_entries([
            ("Shopmart new", "https://signin.shopmart.com.au/login", "user_a", "Sh4r3d!Pw99a"),
            ("Shopmart old", "https://www.shopmart.com.au/", "user_a", "0ldPw!2019aa"),
        ])
        kept, dropped, near = dedup(entries)
        # Both kept — we never guess which password is current.
        self.assertEqual(len(kept), 2)
        self.assertEqual(dropped, [])
        self.assertEqual(near, [(("shopmart.com.au", "user_a"), 2)])

    def test_different_tenants_not_merged(self):
        entries, _ = make_entries([
            ("Tenant one", "https://alphaco.authportal.com/", "user_a@example.com", "One!Pw11a"),
            ("Tenant two", "https://betaco.authportal.com/", "user_a@example.com", "Two!Pw22b"),
        ])
        kept, dropped, near = dedup(entries)
        self.assertEqual(len(kept), 2)
        self.assertEqual(dropped, [])
        self.assertEqual(near, [])


class Reuse(unittest.TestCase):
    """find_reuse keys on `site`, so subdomain spread isn't mis-flagged."""

    def test_same_password_across_one_site_is_not_reuse(self):
        entries, _ = make_entries([
            ("Shopmart signin", "https://signin.shopmart.com.au/", "user_a", "OnePw!shared9"),
            ("Shopmart www", "https://www.shopmart.com.au/", "user_a", "OnePw!shared9"),
        ])
        self.assertEqual(find_reuse(entries), [])

    def test_same_password_across_two_sites_is_reuse(self):
        entries, _ = make_entries([
            ("Shopmart", "https://www.shopmart.com.au/", "user_a", "OnePw!shared9"),
            ("Taskhub", "https://www.taskhub.com/", "user_a", "OnePw!shared9"),
        ])
        groups = find_reuse(entries)
        self.assertEqual(len(groups), 1)
        self.assertEqual(len(groups[0]), 2)


class TitleOnlyDupes(unittest.TestCase):
    """Bare title entries (no URL) flagged against a matching URL entry."""

    def test_title_only_matches_url_brand(self):
        entries, _ = make_entries([
            ("Soundbox", "", "", "Z9q!Lmn2pdx"),
            ("Soundbox web", "https://login.soundbox.com/", "user_b", "S0und!Pw7"),
        ])
        matches = find_title_dupes(entries)
        self.assertEqual(len(matches), 1)
        title_entry, sites = matches[0]
        self.assertEqual(title_entry["title"], "Soundbox")
        self.assertEqual(sites, ["soundbox.com"])
        # Flagged only — never removed from the kept set.
        kept, dropped, _ = dedup(entries)
        self.assertEqual(len(kept), 2)
        self.assertEqual(dropped, [])

    def test_bracket_tag_is_stripped_before_matching(self):
        entries, _ = make_entries([
            ("Streamflix [TAG]", "", "", "N0tFlix!aa1"),
            ("Streamflix", "https://www.streamflix.com/", "user_b", "Str3am!Pw2"),
        ])
        matches = find_title_dupes(entries)
        self.assertEqual(len(matches), 1)
        self.assertEqual(matches[0][1], ["streamflix.com"])

    def test_no_false_match_for_unrelated_title(self):
        entries, _ = make_entries([
            ("Stargaze", "", "", "Astr0!gaze9"),
            ("Shopmart", "https://www.shopmart.com.au/", "user_a", "ShopPw!22a"),
        ])
        self.assertEqual(find_title_dupes(entries), [])


class SkippedRows(unittest.TestCase):
    """Empty-password rows (secure notes etc.) are skipped, not entries."""

    def test_empty_password_row_skipped(self):
        entries, skipped = make_entries([
            ("Real login", "https://www.shopmart.com.au/", "user_a", "ShopPw!22a"),
            ("Secure note", "", "", ""),
        ])
        self.assertEqual(len(entries), 1)
        self.assertEqual(skipped, 1)


if __name__ == "__main__":
    unittest.main()
