# password_audit.py

A single-module, stdlib-only tool for cleaning up passwords when migrating to Apple
Passwords. Point it at one or more CSV exports (1Password, Apple Passwords, or
both) and it merges them, removes duplicates, flags weak/compromised/reused
passwords, and — optionally — flags accounts whose website is gone. It writes a
human-readable report plus a deduplicated CSV ready to import into Apple Passwords.

It is meant to be run **once** for a migration. After you've migrated, Apple
Passwords does compromised/weak/reused monitoring natively and continuously
(Settings → Passwords → Security Recommendations), so the lasting value here is
the one-shot consolidated report and the cross-vault de-duplication Apple doesn't do.

## What it does

1. **Merge** — combines every CSV you pass and de-duplicates across them, so a
   login that exists in both 1Password and Apple collapses to one entry.
2. **Compromised** — checks each password against HaveIBeenPwned (see the security
   note below — your passwords never leave the machine).
3. **Weak** — local heuristics: length, character variety, a ~150-entry
   common-password list, keyboard walks/sequences, and repeated patterns.
4. **Reused** — the same password used across more than one site.
5. **De-duplicated** — collapses every subdomain of a site to its **registrable domain**
   (`signin.ebay.com.au`, `www.ebay.com.au`, `au.linkedin.com` → `ebay.com.au` / `linkedin.com`),
   computed from the **Public Suffix List** so multi-part TLDs survive (`amazon.com.au` stays
   distinct from `amazon.com`) and **multi-tenant login backends stay separate** (two
   `*.b2clogin.com` Azure tenants are different accounts, not one). It also applies **known domain
   renames** (`discordapp.com` → `discord.com`, `twitter.com` → `x.com`) so same-site,
   same-username, same-password rows merge, and drops exact duplicates from the output. Also
   **merges a login saved twice under different usernames** (same site + same password — e.g. a
   handle and an email) into one entry, keeping the email-style username and listing every such
   merge in the report so you can undo it. Flags *near*-duplicates (same site + username, different
   password) for you to review rather than guessing which is current. Title-only entries with no
   URL (e.g. a bare `Sonos` from Apple that likely matches `login.sonos.com`) are **flagged for
   manual review, never auto-dropped** — there's no URL or username to merge on safely.
6. **Dead sites** *(opt-in)* — flags accounts whose website looks gone so you can
   delete them.

**Local-network credentials are exempt.** Anything on a private IP
(`192.168.x`, `10.x`, `172.16–31.x`, loopback), `localhost`, an `*.local` name, or
a bare hostname like `nas`/`router` is kept in the output but skipped for the
compromised/weak checks — those passwords aren't meaningfully "breached", and you
set them yourself. They're listed in their own section so the exemption is visible.

## Usage

```bash
python3 password_audit.py <export1.csv> [<export2.csv> ...] [--out-dir DIR] [--offline] [--check-dead]
```

Export each vault to CSV first:
- **Apple Passwords**: open the Passwords app → File/⋯ menu → Export.
- **1Password**: Settings → Export → your account → CSV.

Then run it on both at once:

```bash
python3 password_audit.py 1password.csv apple.csv --out-dir ~/Desktop --check-dead
```

### Options

| Flag | Effect |
|------|--------|
| `--out-dir DIR` | Where to write `report.md` and `cleaned.csv` (default: current directory). |
| `--offline` | Skip **all** network — both the HaveIBeenPwned check and the dead-site check. Weak/reuse/dedup still run. |
| `--check-dead` | Probe each public site (DNS + an anonymous HTTP request) and flag the ones that look gone. Off by default. |

### Outputs

- **`report.md`** — a ranked, human-readable report. It **never contains your
  passwords**; entries are identified by title / URL / username only.
- **`cleaned.csv`** — Apple Passwords import format
  (`Title,URL,Username,Password,Notes,OTPAuth`) with exact duplicates removed.
  Each `Title` is rewritten to a consistent `domain (username)` (e.g.
  `ebay.com.au (you@example.com)`) so the imported vault reads cleanly — every
  subdomain variant renders as the same registrable domain, and entries with no URL keep
  their original name. Weak/compromised/reused/dead/LAN entries are **kept** — you still
  need those accounts; the report tells you what to rotate or delete after importing.

## Security model

- **Your passwords never leave the machine.** The only password-derived network
  call is the HaveIBeenPwned *Pwned Passwords* range API using k-anonymity: each
  password is SHA-1 hashed locally and only the **first 5 hex characters** of the
  hash are sent. The 35-character suffix is matched offline. This is the same
  method 1Password and Apple use internally.
- **Merge / weak / reuse / dedup checks are 100% local** — no network at all.
- **`--check-dead` is the only feature that puts site identities on the wire.** It
  does a DNS lookup (to your resolver) plus an unauthenticated GET to each live
  host — no usernames, passwords, or cookies are ever sent. It's off by default
  precisely for that reason. Dead-site detection is deliberately conservative:
  only an unresolvable domain, an unreachable host, or an explicit HTTP 410 counts
  as "dead", so it won't tell you to delete a live account on a hunch.
- **`cleaned.csv` does contain passwords** — it's the import file. After you import
  it, delete it, and delete the original CSV exports too. (macOS SSDs can't be
  reliably secure-erased, so a normal delete is the practical step, not a guarantee.)

## Data sources

Two reference lists are **vendored** (not fetched at runtime) so de-duplication stays fully offline.

**Public Suffix List** — used to reduce each host to its registrable domain
(`au.linkedin.com` → `linkedin.com`) while keeping multi-part TLDs (`amazon.com.au`) and
multi-tenant backends (`*.myshopify.com`, `*.github.io`) distinct. Vendored as
`public_suffix_list.dat` from [publicsuffix.org](https://publicsuffix.org/list/) (Mozilla, MPL 2.0;
notice in `public_suffix_list.LICENSE`). A few Azure tenant backends the PSL doesn't list yet
(`b2clogin.com`, `onmicrosoft.com`) are added in `EXTRA_PRIVATE_SUFFIXES` in `password_audit.py` so
different tenants on them never merge. To refresh:

```bash
curl -fsSL https://publicsuffix.org/list/public_suffix_list.dat > public_suffix_list.dat
```

**Domain renames** (`discordapp.com` → `discord.com`, etc.) come from Apple's
[`password-manager-resources`](https://github.com/apple/password-manager-resources) —
`quirks/shared-credentials.json`, the same data behind iCloud Keychain (MIT-licensed). Vendored as
`shared-credentials.json` (commit `6857f10`, 2026-05-21). Only the directional `from`→`to` renames are
used; the file's broader "shared credential backend" groups are deliberately ignored, so distinct
products that merely share a login backend (Hulu/Disney, Threads/Instagram) are never merged. Apple's
MIT notice is kept in `shared-credentials.LICENSE`. To refresh:

```bash
gh api repos/apple/password-manager-resources/contents/quirks/shared-credentials.json \
  --jq .content | base64 -d > shared-credentials.json
```

## Requirements

Python 3.9+. Standard library only — nothing to install.
