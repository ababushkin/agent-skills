# password_audit.py

A single-file, stdlib-only tool for cleaning up passwords when migrating to Apple
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
5. **De-duplicated** — collapses login/`www` subdomain variants of one site
   (`signin.ebay.com.au`, `www.ebay.com.au`, `accounts.ebay.com.au` → one `ebay.com.au`)
   so same-site, same-username, same-password rows merge. Drops exact duplicates from
   the output; flags *near*-duplicates (same site + username, different password) for
   you to review rather than guessing which is current. Title-only entries with no URL
   (e.g. a bare `Sonos` from Apple that likely matches `login.sonos.com`) are **flagged
   for manual review, never auto-dropped** — there's no URL or username to merge on safely.
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
  Weak/compromised/reused/dead/LAN entries are **kept** — you still need those
  accounts; the report tells you what to rotate or delete after importing.

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

## Requirements

Python 3.9+. Standard library only — nothing to install.
