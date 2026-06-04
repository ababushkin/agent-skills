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
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import password_audit  # noqa: E402  (module handle for patching DOMAIN_ALIASES in tests)
from password_audit import (  # noqa: E402
    dedup,
    dedup_host,
    display_name,
    find_reuse,
    find_title_dupes,
    load_domain_aliases,
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
        kept, dropped, near, _ = dedup(entries)
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
        kept, dropped, _, _ = dedup(entries)
        self.assertEqual(len(kept), 1)
        self.assertEqual(len(dropped), 1)


class StaysSeparate(unittest.TestCase):
    """Cases the collapse must NOT merge."""

    def test_different_users_on_same_subdomain_both_kept(self):
        entries, _ = make_entries([
            ("Shopmart A", "https://signin.shopmart.com.au/login", "user_a", "Aaa!Pw111"),
            ("Shopmart C", "https://signin.shopmart.com.au/login", "user_c@example.com", "Ccc!Pw222"),
        ])
        kept, dropped, near, _ = dedup(entries)
        self.assertEqual(len(kept), 2)
        self.assertEqual(dropped, [])
        self.assertEqual(near, [])

    def test_same_site_user_different_password_is_near_dup_not_dropped(self):
        entries, _ = make_entries([
            ("Shopmart new", "https://signin.shopmart.com.au/login", "user_a", "Sh4r3d!Pw99a"),
            ("Shopmart old", "https://www.shopmart.com.au/", "user_a", "0ldPw!2019aa"),
        ])
        kept, dropped, near, _ = dedup(entries)
        # Both kept — we never guess which password is current.
        self.assertEqual(len(kept), 2)
        self.assertEqual(dropped, [])
        self.assertEqual(near, [(("shopmart.com.au", "user_a"), 2)])

    def test_different_tenants_not_merged(self):
        entries, _ = make_entries([
            ("Tenant one", "https://alphaco.authportal.com/", "user_a@example.com", "One!Pw11a"),
            ("Tenant two", "https://betaco.authportal.com/", "user_a@example.com", "Two!Pw22b"),
        ])
        kept, dropped, near, _ = dedup(entries)
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
        kept, dropped, _, _ = dedup(entries)
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


class DisplayName(unittest.TestCase):
    """The consistent 'site (username)' title written to cleaned.csv and the report."""

    def _one(self, title, url, user, pw="Disp!Pw99a"):
        entries, _ = make_entries([(title, url, user, pw)])
        return display_name(entries[0])

    def test_url_with_email_username(self):
        self.assertEqual(
            self._one("Shopmart", "https://www.shopmart.com.au/", "user_a@example.com"),
            "shopmart.com.au (user_a@example.com)",
        )

    def test_subdomain_collapses_into_the_name(self):
        self.assertEqual(
            self._one("Shopmart signin", "https://signin.shopmart.com.au/", "user_a"),
            "shopmart.com.au (user_a)",
        )

    def test_www_prefix_collapses(self):
        self.assertEqual(
            self._one("Taskhub", "https://www.taskhub.com/", "user_b"),
            "taskhub.com (user_b)",
        )

    def test_no_username_drops_the_parens(self):
        self.assertEqual(
            self._one("Taskhub", "https://www.taskhub.com/", ""),
            "taskhub.com",
        )

    def test_title_only_entry_keeps_original_human_title(self):
        # No URL to derive a domain from, no username -> keep the name verbatim.
        self.assertEqual(self._one("Soundbox", "", ""), "Soundbox")

    def test_lan_ip_renders_consistently(self):
        self.assertEqual(
            self._one("Router", "http://10.0.0.1/", "admin"),
            "10.0.0.1 (admin)",
        )


class SkippedRows(unittest.TestCase):
    """Empty-password rows (secure notes etc.) are skipped, not entries."""

    def test_empty_password_row_skipped(self):
        entries, skipped = make_entries([
            ("Real login", "https://www.shopmart.com.au/", "user_a", "ShopPw!22a"),
            ("Secure note", "", "", ""),
        ])
        self.assertEqual(len(entries), 1)
        self.assertEqual(skipped, 1)


class DomainAliases(unittest.TestCase):
    """Known domain renames (Apple's shared-credentials.json 'from'->'to') collapse to one site."""

    def setUp(self):
        self._saved = password_audit.DOMAIN_ALIASES

    def tearDown(self):
        password_audit.DOMAIN_ALIASES = self._saved

    def test_load_uses_renames_only_and_ignores_shared_groups(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "sc.json"
            path.write_text(json.dumps([
                {"from": ["oldbrand.example"], "to": ["newbrand.example"]},
                {"from": ["alt.example"], "to": ["canonical.example", "second.example"]},
                {"shared": ["hulu.example", "disney.example"]},
            ]), encoding="utf-8")
            aliases = load_domain_aliases(path)
        self.assertEqual(aliases.get("oldbrand.example"), "newbrand.example")
        self.assertEqual(aliases.get("alt.example"), "canonical.example")  # first of a list 'to'
        self.assertNotIn("hulu.example", aliases)   # 'shared' equivalence groups are ignored
        self.assertNotIn("disney.example", aliases)

    def test_missing_file_yields_empty_map(self):
        self.assertEqual(load_domain_aliases(Path("/no/such/aliases.json")), {})

    def test_dedup_host_applies_injected_rename(self):
        password_audit.DOMAIN_ALIASES = {"discordapp.com": "discord.com"}
        self.assertEqual(dedup_host("discordapp.com"), "discord.com")
        self.assertEqual(dedup_host("www.discordapp.com"), "discord.com")

    def test_dedup_host_recollapses_subdomained_canonical(self):
        # A rename target can carry a generic prefix; the result is stripped again.
        password_audit.DOMAIN_ALIASES = {"seek.com.au": "login.seek.com"}
        self.assertEqual(dedup_host("seek.com.au"), "seek.com")

    def test_alias_collapses_two_registrable_domains_in_dedup(self):
        password_audit.DOMAIN_ALIASES = {"discordapp.com": "discord.com"}
        entries, _ = make_entries([
            ("Discord", "https://discord.com/", "user_a@example.com", "D!scord99a"),
            ("Discord old", "https://discordapp.com/", "user_a@example.com", "D!scord99a"),
        ])
        kept, dropped, _, _ = dedup(entries)
        self.assertEqual(len(kept), 1)
        self.assertEqual(len(dropped), 1)

    def test_vendored_snapshot_maps_discord(self):
        # Smoke check that the committed shared-credentials.json loads and carries the discord
        # rename — guards against a broken or empty vendored file.
        self.assertEqual(load_domain_aliases().get("discordapp.com"), "discord.com")


class AliasUsernameMerge(unittest.TestCase):
    """Same site + same password but different usernames -> one credential (email username kept)."""

    def test_same_site_password_different_user_merges_keeping_email(self):
        # Handle listed first, email second — the email must still win.
        entries, _ = make_entries([
            ("Bikes handle", "https://www.bikeshop.example/", "rider_handle", "B!keP4ss77z"),
            ("Bikes email", "https://www.bikeshop.example/", "rider@example.com", "B!keP4ss77z"),
        ])
        kept, dropped, near, alias_merged = dedup(entries)
        self.assertEqual(len(kept), 1)
        self.assertEqual(dropped, [])
        self.assertEqual(near, [])
        self.assertEqual(len(alias_merged), 1)
        loser, winner = alias_merged[0]
        self.assertEqual(winner["username"], "rider@example.com")
        self.assertEqual(loser["username"], "rider_handle")
        self.assertEqual(kept[0]["username"], "rider@example.com")

    def test_no_email_keeps_first_seen(self):
        entries, _ = make_entries([
            ("Forum one", "https://www.forum.example/", "handle_one", "F0rum!Pw22a"),
            ("Forum two", "https://www.forum.example/", "handle_two", "F0rum!Pw22a"),
        ])
        kept, dropped, near, alias_merged = dedup(entries)
        self.assertEqual(len(kept), 1)
        self.assertEqual(len(alias_merged), 1)
        self.assertEqual(kept[0]["username"], "handle_one")  # first seen wins absent an email

    def test_different_passwords_never_merge(self):
        # Two genuinely separate accounts on one site with DIFFERENT passwords must both survive.
        entries, _ = make_entries([
            ("Acct A", "https://www.shop.example/", "alice@example.com", "Al!cePw11a"),
            ("Acct B", "https://www.shop.example/", "bob@example.com", "B0bPw!22bb"),
        ])
        kept, dropped, near, alias_merged = dedup(entries)
        self.assertEqual(len(kept), 2)
        self.assertEqual(alias_merged, [])
        self.assertEqual(dropped, [])


if __name__ == "__main__":
    unittest.main()
