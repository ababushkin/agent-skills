#!/usr/bin/env python3
"""
password_audit.py — local, fully offline de-duplicator for a 1Password -> Apple Passwords migration.

What it does, given ONE OR MORE CSV exports (1Password, Apple Passwords, or both):
  1. Merge         — combines every export and de-duplicates ACROSS them into one clean list
  2. De-duplicated — collapses every subdomain to its registrable domain via the Public Suffix List
                     (au.linkedin.com -> linkedin.com) AND known domain renames (discordapp.com ->
                     discord.com) into one site, while multi-tenant backends (b2clogin.com etc.) stay
                     separate; drops EXACT duplicates; merges a login saved twice under different
                     usernames (same site + same password, keeping the email username); flags
                     near-duplicates and likely title-only look-alikes
  3. Reused        — reports the same password used across more than one site, so you can see what to
                     give unique passwords. Reporting only — nothing is changed or dropped for this.

Local-network credentials (routers, NAS, etc. on 192.168.x / 10.x / *.local) are kept and labelled,
and never treated as a public brand when matching title-only look-alikes.

Outputs:
  report.md    a human-readable de-duplication report. NEVER contains plaintext passwords.
  cleaned.csv  Apple Passwords import format, with exact duplicates removed. Each Title is
               normalized to a consistent "domain (username)" (title-only entries keep their name).

Security model:
  - Fully offline. This tool makes NO network calls at all — every password stays on this machine.
  - report.md identifies entries by title / url / username only — never the password itself.
  - cleaned.csv DOES contain your passwords (it is the import file). Delete it, and the original CSV
    export(s), after importing into Apple Passwords.

Usage:
    python3 password_audit.py <export1.csv> [<export2.csv> ...] [--out-dir DIR]

Stdlib only. Requires Python 3.9+.
"""

import argparse
import csv
import ipaddress
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

APPLE_HEADER = ["Title", "URL", "Username", "Password", "Notes", "OTPAuth"]


def normalize_header(name):
    return (name or "").strip().lower()


# Map of canonical field -> set of accepted header names (lowercased), in priority order.
FIELD_ALIASES = {
    "title": ["title", "name"],
    "url": ["url", "website", "urls", "login_uri"],
    "username": ["username", "login", "user", "email", "login_username"],
    "password": ["password", "login_password"],
    "notes": ["notes", "note"],
    "otp": ["otpauth", "one-time password", "otp", "totp"],
}


def resolve_columns(fieldnames):
    """Return {canonical: actual_header} by matching aliases case-insensitively."""
    normalized = {normalize_header(f): f for f in (fieldnames or [])}
    resolved = {}
    for canonical, aliases in FIELD_ALIASES.items():
        for alias in aliases:
            if alias in normalized:
                resolved[canonical] = normalized[alias]
                break
    return resolved


def domain_of(url, title):
    """Best-effort registrable-ish domain from a url; fall back to the lowercased title."""
    if url:
        u = url.strip()
        u = re.sub(r"^[a-zA-Z][a-zA-Z0-9+.\-]*://", "", u)  # strip scheme
        u = u.split("/", 1)[0].split("?", 1)[0]             # host[:port] only
        u = u.split("@")[-1]                                 # strip userinfo
        u = u.split(":", 1)[0].lower().strip()
        u = re.sub(r"^www\.", "", u)
        if u:
            return u
    return (title or "").strip().lower()


def url_host_of(url):
    """Host strictly derived from the URL (no title fallback). '' if the entry has no URL."""
    return domain_of(url, "")


# A host's dedup key is its registrable domain (eTLD+1), computed from the vendored Public Suffix
# List: signin.ebay.com.au -> ebay.com.au, au.linkedin.com -> linkedin.com. This collapses every
# subdomain variant of a site, while multi-part TLDs (amazon.com.au stays distinct from amazon.com)
# and multi-tenant backends (the PSL's private section) are respected.
PSL_FILE = Path(__file__).with_name("public_suffix_list.dat")

# Multi-tenant login backends the PSL hasn't (yet) marked private. Treated as public suffixes so
# that different tenants (dhvicp.b2clogin.com vs sentosalogin.b2clogin.com) never collapse into one
# site. Extend this set if you hit another backend the PSL doesn't cover.
EXTRA_PRIVATE_SUFFIXES = frozenset({
    "b2clogin.com",     # Azure AD B2C — one tenant per subdomain
    "onmicrosoft.com",  # Microsoft Entra / Azure tenant domains
})


def load_public_suffixes(path=PSL_FILE):
    """Parse the Public Suffix List into (rules, exceptions) sets. '//' comments and blank lines are
    ignored; a leading '!' marks an exception; '*' wildcard labels are kept verbatim. Both the ICANN
    and PRIVATE sections are used, so multi-tenant backends (github.io, myshopify.com) act as
    suffixes too. Missing/unreadable file -> empty sets (registrable_domain() then falls back to the
    last two labels, so dedup still works, just less precisely)."""
    rules, exceptions = set(), set()
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return rules, exceptions
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("//"):
            continue
        rule = line.split()[0]  # the rule is the first token; ignore any trailing comment
        (exceptions if rule.startswith("!") else rules).add(rule.lstrip("!"))
    return rules, exceptions


PSL_RULES, PSL_EXCEPTIONS = load_public_suffixes()


def _public_suffix_labels(labels):
    """Number of trailing labels of `labels` (a host split on '.') that form its public suffix, per
    the PSL algorithm: an exception rule wins (its suffix is the rule minus its first label);
    otherwise the longest matching rule wins (exact, local supplement, or a '*' wildcard); with no
    match the default is the single rightmost label."""
    for i in range(len(labels)):
        if ".".join(labels[i:]) in PSL_EXCEPTIONS:
            return len(labels) - i - 1
    best = 1
    for i in range(len(labels)):
        exact = ".".join(labels[i:])
        wild = ".".join(["*"] + labels[i + 1:])
        if exact in PSL_RULES or exact in EXTRA_PRIVATE_SUFFIXES or wild in PSL_RULES:
            best = max(best, len(labels) - i)
    return best


def registrable_domain(host):
    """Reduce a host to its registrable domain, eTLD+1 (au.linkedin.com -> linkedin.com;
    signin.ebay.com.au -> ebay.com.au; dhvicp.b2clogin.com kept whole). A host that is itself a
    public suffix, or has no dot, is returned unchanged."""
    if not host or "." not in host:
        return host
    try:
        ipaddress.ip_address(host)
        return host  # an IP literal (e.g. a LAN device) is not a domain — leave it whole
    except ValueError:
        pass
    labels = host.split(".")
    suffix_len = _public_suffix_labels(labels)
    if len(labels) <= suffix_len:
        return host
    return ".".join(labels[len(labels) - suffix_len - 1:])


# A well-known domain rename (old registrable domain -> the current one) is treated as ONE site.
# Sourced from Apple's password-manager-resources (the data behind iCloud Keychain); see
# load_domain_aliases() for which part of that file we use and why.
ALIASES_FILE = Path(__file__).with_name("shared-credentials.json")


def load_domain_aliases(path=ALIASES_FILE):
    """Build {old_domain: canonical_domain} from Apple's shared-credentials.json, using ONLY the
    directional 'from'->'to' renames (domains that were retired in favour of another). The file's
    broader 'shared' equivalence groups are intentionally ignored, so genuinely distinct products
    that merely share a credential backend (e.g. Hulu/Disney, Threads/Instagram) are never merged.
    Keys are reduced to their registrable domain so they match what dedup_host() looks up (some
    'from' domains carry a www./login. prefix). Missing/unreadable file -> {} (aliasing no-ops)."""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    aliases = {}
    for group in data:
        if not isinstance(group, dict) or "from" not in group or "to" not in group:
            continue
        to = group["to"]
        canonical = to[0] if isinstance(to, list) else to  # 'to' is sometimes a list of domains
        for old in group["from"]:
            aliases[registrable_domain(old)] = canonical
    return aliases


DOMAIN_ALIASES = load_domain_aliases()


def dedup_host(host):
    """Collapse a host to its dedup key: reduce to the registrable domain (signin.ebay.com.au ->
    ebay.com.au, au.linkedin.com -> linkedin.com), then canonicalise a known rename (discordapp.com
    -> discord.com). The rename target can itself carry a subdomain (login.seek.com), so reduce once
    more after."""
    if not host:
        return ""
    host = registrable_domain(host)
    host = DOMAIN_ALIASES.get(host, host)
    return registrable_domain(host)


def is_local(url_host):
    """
    True if url_host names a local-network target (LAN device, not a public website):
      - a private / loopback / link-local IP (RFC1918, 127/8, 169.254/16, IPv6 equivalents)
      - 'localhost', an mDNS '*.local' name, or a single dotless label (e.g. 'nas', 'router').
    Empty host (title-only entry such as 'Netflix') is NOT local.
    """
    if not url_host:
        return False
    try:
        return ipaddress.ip_address(url_host).is_private
    except ValueError:
        pass
    if url_host == "localhost" or url_host.endswith(".local"):
        return True
    return "." not in url_host  # bare single-label hostname -> LAN


def load_rows(csv_path):
    """Parse one export. Returns (entries, skipped_count). Each entry is a dict with canonical keys."""
    source = Path(csv_path).name
    with open(csv_path, newline="", encoding="utf-8-sig") as fh:
        reader = csv.DictReader(fh)
        cols = resolve_columns(reader.fieldnames)
        if "password" not in cols:
            sys.exit(
                f"ERROR: could not find a 'Password' column in '{source}'.\n"
                f"Headers seen: {reader.fieldnames}\n"
                "Export logins as CSV (1Password: Settings -> Export -> CSV; "
                "Apple Passwords: Passwords app -> Export)."
            )
        entries, skipped = [], 0
        for raw in reader:
            password = (raw.get(cols["password"]) or "").strip()
            if not password:
                skipped += 1
                continue
            title = (raw.get(cols.get("title", "")) or "").strip()
            url = (raw.get(cols.get("url", "")) or "").strip()
            url_host = url_host_of(url)
            entries.append({
                "title": title,
                "url": url,
                "username": (raw.get(cols.get("username", "")) or "").strip(),
                "password": password,
                "notes": (raw.get(cols.get("notes", "")) or "").strip(),
                "otp": (raw.get(cols.get("otp", "")) or "").strip(),
                "domain": domain_of(url, title),
                "site": dedup_host(url_host) if url_host else domain_of(url, title),
                "url_host": url_host,
                "local": is_local(url_host),
                "source": source,
            })
    return entries, skipped


# ---- Reuse + dedup -----------------------------------------------------------------------------

def find_reuse(entries):
    """Return list of (label, [entries]) for passwords used across >1 distinct domain."""
    by_pw = defaultdict(list)
    for e in entries:
        by_pw[e["password"]].append(e)
    groups = []
    for members in by_pw.values():
        if len({m["site"] for m in members}) > 1:
            groups.append(members)
    groups.sort(key=len, reverse=True)
    return groups


def dedup(entries):
    """
    Split entries into (kept, exact_dupes_dropped, near_dupes, alias_merged).
      exact dupe   = same (site, username, password) as an earlier kept entry        -> dropped
      alias merge  = same (site, password) but a DIFFERENT username (one login saved  -> merged
                     under two usernames). Keep the email-style username, drop the rest.
      near dupe    = same (site, username) but DIFFERENT password (credential updated) -> kept, flagged
    `site` collapses login/www subdomain variants and known domain renames, so signin.ebay.com.au
    and www.ebay.com.au for the same user are treated as one site.
    Order is preserved; the first occurrence of each exact key is kept.
    `alias_merged` is a list of (dropped_entry, kept_entry) pairs for the report.
    """
    # Pass 1 — drop exact (site, username, password) duplicates, preserving order.
    seen_exact, survivors, dropped = set(), [], []
    for e in entries:
        exact = (e["site"], e["username"].lower(), e["password"])
        if exact in seen_exact:
            dropped.append(e)
            continue
        seen_exact.add(exact)
        survivors.append(e)

    # Pass 2 — same (site, password) but different username -> one credential saved twice.
    # Keep the email-style username (else the first seen); drop the rest, recording the merge.
    by_sp = defaultdict(list)  # (site, password) -> entries, in order
    for e in survivors:
        by_sp[(e["site"], e["password"])].append(e)
    alias_merged, alias_losers = [], set()  # [(loser, winner)], {id(loser)}
    for group in by_sp.values():
        if len({g["username"].lower() for g in group}) > 1:
            winner = next((g for g in group if "@" in g["username"]), group[0])
            for g in group:
                if g is not winner:
                    alias_merged.append((g, winner))
                    alias_losers.add(id(g))
    kept = [e for e in survivors if id(e) not in alias_losers]

    # Near dupes — same (site, username) but more than one password. Computed over survivors;
    # alias losers have a different username so they never affect a (site, username) bucket.
    by_identity = defaultdict(set)  # (site, username) -> set of passwords seen
    for e in survivors:
        by_identity[(e["site"], e["username"].lower())].add(e["password"])
    near = [(ident, len(pws)) for ident, pws in by_identity.items() if len(pws) > 1]
    near.sort(key=lambda x: x[1], reverse=True)
    return kept, dropped, near, alias_merged


def normalize_title(title):
    """Collapse a free-text title to a comparison token: drop bracketed/parenthesised
    suffixes (e.g. '[ANTON]', '(Anton)'), lowercase, keep alphanumerics only."""
    base = re.sub(r"[\(\[\{].*", "", title)  # drop '... [tag]' / '... (note)'
    return re.sub(r"[^a-z0-9]", "", base.lower())


def find_title_dupes(entries):
    """
    Best-effort: title-only entries (no URL) that probably duplicate a URL entry.
    Returns [(title_entry, [site, ...]), ...]. Flagged for manual review, never dropped.
    Matches a title's token (or its first word) against the brand label (first label of
    `site`, e.g. sonos.com -> 'sonos') of a real URL entry.
    """
    brands = defaultdict(set)  # brand token -> set of site strings
    for e in entries:
        if e["url_host"] and not e["local"]:
            brand = e["site"].split(".", 1)[0]
            if len(brand) >= 3:
                brands[brand].add(e["site"])
    matches = []
    for e in entries:
        if e["url_host"]:
            continue  # only title-only entries (no URL) are ambiguous
        tokens = {normalize_title(e["title"])}
        first_word = re.split(r"[^a-z0-9]+", e["title"].lower(), maxsplit=1)[0]
        tokens.add(first_word)
        sites = sorted({s for tok in tokens if len(tok) >= 3 for s in brands.get(tok, ())})
        if sites:
            matches.append((e, sites))
    matches.sort(key=lambda x: label(x[0]).lower())
    return matches


# ---- Reporting ---------------------------------------------------------------------------------

def display_name(entry):
    """Consistent entry title: collapsed-domain (username).
    Drops the parens when there's no username; for a title-only entry (no URL)
    keeps its original human title, since there's no host to derive a domain from."""
    user = entry["username"]
    base = entry["site"] if entry["url_host"] else (entry["title"] or entry["site"])
    return f"{base} ({user})" if user else base


def label(entry):
    """Identify an entry for the report WITHOUT revealing its password."""
    return display_name(entry) or "(untitled)"


def write_report(path, entries, skipped, reuse_groups, dropped, near, sources, title_dupes,
                 alias_merged):
    local_entries = [e for e in entries if e["local"]]

    lines = []
    lines.append("# Password de-duplication report\n")
    lines.append(f"- Entries analysed: **{len(entries)}**")
    if len(sources) > 1:
        breakdown = ", ".join(f"{name} ({n})" for name, n in sources.items())
        lines.append(f"- Sources merged: **{len(sources)}** — {breakdown}")
    if skipped:
        lines.append(f"- Rows skipped (no password, e.g. secure notes): {skipped}")
    if local_entries:
        lines.append(f"- Local-network entries: {len(local_entries)}")
    lines.append(f"- Reused groups: **{len(reuse_groups)}** · "
                 f"Exact duplicates removed: **{len(dropped)}**")
    lines.append("\n> This report never contains your passwords. `cleaned.csv` does (it is the "
                 "import file) — delete it after importing.\n")

    lines.append("## 🟡 Reused across multiple sites\n")
    if reuse_groups:
        lines.append("Each group below shares one password. Give every account its own.\n")
        for i, members in enumerate(reuse_groups, 1):
            lines.append(f"**Reused password {i}** — used on {len(members)} entries:")
            for e in members:
                lines.append(f"  - {label(e)}")
            lines.append("")
    else:
        lines.append("_None found._\n")

    multi = len(sources) > 1
    lines.append("## ♻️ Exact duplicates removed from `cleaned.csv`\n")
    if dropped:
        lines.append("Same site + username + password as an entry that was kept"
                     + (" (including copies that existed in both vaults).\n" if multi else ".\n"))
        for e in dropped:
            src = f" [{e['source']}]" if multi else ""
            lines.append(f"- {label(e)}{src}")
    else:
        lines.append("_None found._")
    lines.append("")

    lines.append("## ⚠️ Near-duplicates — review manually\n")
    if near:
        lines.append("Same site + username but DIFFERENT passwords. The exports have no timestamps, "
                     "so I kept all of them — decide which is current before importing.\n")
        for (site, user), count in near:
            lines.append(f"- {site or '(no domain)'} · {user or '(no username)'} — "
                         f"{count} different passwords")
    else:
        lines.append("_None found._")
    lines.append("")

    lines.append("## 🔀 Merged — same password, different username\n")
    if alias_merged:
        lines.append("These shared a site AND a password but had different usernames, so I treated "
                     "them as one login and kept the email-style username. Skim them — if any is "
                     "actually a separate account, re-add it.\n")
        for loser, winner in alias_merged:
            site = winner["site"] or "(no domain)"
            kept_user = winner["username"] or "(no username)"
            lost_user = loser["username"] or "(no username)"
            lines.append(f"- {site} — kept `{kept_user}`, dropped `{lost_user}`")
    else:
        lines.append("_None found._")
    lines.append("")

    lines.append("## 🔗 Possible duplicates — review\n")
    if title_dupes:
        lines.append("Title-only entries (no URL — typically from Apple Passwords) that look like "
                     "they duplicate a saved website below. I can't be sure (no URL or username to "
                     "match on), so these are KEPT — merge them by hand in Apple Passwords.\n")
        for e, sites in title_dupes:
            lines.append(f"- {label(e)} — probably the same as: {', '.join(sites)}")
    else:
        lines.append("_None found._")
    lines.append("")

    lines.append("## 🏠 Local network\n")
    if local_entries:
        lines.append("LAN devices (private IPs, `localhost`, `*.local`, bare hostnames). Kept in "
                     "`cleaned.csv` and de-duplicated like any other entry.\n")
        for e in sorted(local_entries, key=lambda x: label(x).lower()):
            lines.append(f"- {label(e)}")
    else:
        lines.append("_None found._")
    lines.append("")

    path.write_text("\n".join(lines), encoding="utf-8")


def write_cleaned_csv(path, kept):
    with open(path, "w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh)
        writer.writerow(APPLE_HEADER)
        for e in kept:
            writer.writerow([display_name(e), e["url"], e["username"], e["password"], e["notes"], e["otp"]])


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Merge one or more password CSV exports (1Password / Apple), de-duplicate "
                    "them, and emit a cleaned CSV ready to import into Apple Passwords.")
    parser.add_argument("csv_paths", nargs="+",
                        help="One or more CSV exports (e.g. 1password.csv apple.csv)")
    parser.add_argument("--out-dir", default=".", help="Where to write report.md and cleaned.csv (default: .)")
    args = parser.parse_args(argv)

    out_dir = Path(args.out_dir).expanduser()
    out_dir.mkdir(parents=True, exist_ok=True)

    entries, skipped = [], 0
    sources = {}
    for raw_path in args.csv_paths:
        csv_path = Path(raw_path).expanduser()
        if not csv_path.is_file():
            sys.exit(f"ERROR: no such file: {csv_path}")
        file_entries, file_skipped = load_rows(csv_path)
        entries.extend(file_entries)
        skipped += file_skipped
        sources[csv_path.name] = len(file_entries)
    if not entries:
        sys.exit("No password entries found in the CSV(s) (every row had an empty password).")

    reuse_groups = find_reuse(entries)
    kept, dropped, near, alias_merged = dedup(entries)
    title_dupes = find_title_dupes(entries)

    report_path = out_dir / "report.md"
    cleaned_path = out_dir / "cleaned.csv"
    write_report(report_path, entries, skipped, reuse_groups, dropped, near, sources, title_dupes,
                 alias_merged)
    write_cleaned_csv(cleaned_path, kept)

    merged = f" from {len(sources)} exports" if len(sources) > 1 else ""
    sys.stderr.write(
        f"\nDone. Wrote:\n  {report_path}\n  {cleaned_path}  ({len(kept)} entries{merged}, "
        f"{len(dropped)} exact duplicates removed)\n\n"
        "SECURITY REMINDER:\n"
        f"  - '{cleaned_path.name}' contains your passwords in plaintext. Import it into Apple\n"
        "    Passwords, then DELETE it.\n"
        "  - DELETE the original CSV export(s) you fed in too.\n"
        "  - (macOS SSDs can't be reliably secure-erased; a normal delete is the practical step.)\n"
    )


if __name__ == "__main__":
    main()
