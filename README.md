# agent-skills

A personal pack of [Claude Code](https://docs.claude.com/en/docs/claude-code) /
agent skills. Each skill is a folder with a `SKILL.md` at its root (flat layout):
the YAML front-matter says *when* the skill triggers, and the body is the
step-by-step workflow the agent follows.

Most of the pack is a **secondhand-selling toolkit** built around Facebook
Marketplace and the Melbourne, Australia market (prices in AUD). The skills are
designed to hand off to each other across the life of a sale — list it, track it,
arrange the handover, refresh it if it goes stale, and clear the rest at a garage
sale.

> Tooling, conventions, and governance for working *in* this repo live in
> [`AGENTS.md`](AGENTS.md) (and `CLAUDE.md`, which imports it).

## How skills are wired up

- Source of truth is this repo. The skills are symlinked into
  `~/.claude/skills/<name>` so edits here are live immediately. A new skill needs
  a one-time symlink, e.g.
  `ln -s "$PWD/<name>" ~/.claude/skills/<name>`.
- Invoke a skill explicitly with its slash command (`/resell-au`), or just
  describe the task — the `description` field is written so Claude picks the
  right one on its own.
- Python scripts are pinned via [`mise`](https://mise.jdx.dev): run `mise trust`
  then `mise install` once. Skills that ship scripts also ship golden tests under
  `tests/` (e.g. `resell-au-pickups/tests/check_make_ics.sh`).

## The selling toolkit

| Skill | What it does | Use it when | Invoke |
|-------|--------------|-------------|--------|
| **resell-au** | Prices secondhand items against live comps and writes ready-to-post listings; can drive a real Chrome session to fill the Marketplace form so you only click Post. Also has a **refresh** mode that delete-and-relists stale listings to reset the algorithm's visibility window. | You want to sell / declutter something, ask what it's worth, want an ad written, or point at a folder of item photos to list in bulk. Refresh mode: listings have gone quiet and you want them re-boosted. | `/resell-au [folder]` · `/resell-au refresh [folder]` |
| **resell-au-pickups** | Sweeps your Marketplace inbox, reads every buyer chat, and summarises **who is collecting what, on what day/time, for how much, and where** (pickup vs delivery) — then optionally adds those handovers to your calendar (Google Calendar, with a Melbourne-timezone `.ics` fallback). | You want to check your FB messages, see which buyers you've agreed pickups with and when, or "put my pickups in my calendar". | `/resell-au-pickups` |
| **resell-au-tracker** | Syncs published `listing.md` files into `tracker.json` so the HTML sales tracker shows them. Non-destructive — never touches existing rows or sold prices. | After listing new items, or any time you say "sync the tracker" / "add my listings to the tracker". | `/resell-au-tracker` |
| **garage-sale** | Generates a print-ready A4 HTML label sheet from your `listing.md` files, showing each item's original price next to its marked-down garage-sale price. | You're running a garage sale, want price tags, or say "mark everything down" / "print labels". | `/garage-sale [folder]` |

### A typical flow

```
resell-au            → price + post listings (writes listing.md per item)
   ↓
resell-au-tracker    → add the new listings to tracker.json
   ↓
resell-au-pickups    → read buyer messages, summarise agreed pickups, add to calendar
   ↓
resell-au refresh    → relist anything that's gone stale to re-boost it
   ↓
garage-sale          → print labels and clear whatever's left
```

The selling skills share a working folder (default `~/Desktop/things-for-sale/`),
where each item is a subfolder holding its photos and a `listing.md` record.

## Housing

| Skill | What it does | Use it when | Invoke |
|-------|--------------|-------------|--------|
| **apartment-hunt-nl** | Sweeps the Facebook housing groups you've joined for temporary rentals in Haarlem and Amsterdam, drops everything already seen or screened, collapses the same apartment cross-posted to several groups into one row, and lays the rest out in a comparison table — price, size, furnishing, registration, dates, and scam flags side by side. Reads and reports only; it never messages a poster. | You want to see what's new in the housing groups without re-reading the same posts every few days, or want your candidates compared and shortlisted. | `/apartment-hunt-nl` |

State lives in `~/Desktop/apartment-hunt/`: `groups.json` (which groups to
sweep), `seen.json` (one record per apartment, with every post ID it has been
seen under and its verdict), and `shortlist.md` (the keepers). Mark a listing
`rejected` and it never comes back. `groups.json` and `shortlist.md` are yours
to edit freely; change a verdict with
`triage.py verdict <folder> <post_id> rejected --reason "..."` rather than by
hand, so the write stays atomic and keeps a `.bak`.

## Standalone utilities

Not every folder here is a skill. Some are plain scripts you run directly.

| Tool | What it does |
|------|--------------|
| **[password-audit](password-audit/)** | A single-module, stdlib-only, fully offline password de-duplicator for migrating to Apple Passwords. Merges one or more CSV exports (1Password, Apple, or both) and de-duplicates across them — collapsing subdomain and known domain-rename variants of a site to one entry via the Public Suffix List, while keeping multi-tenant backends and multi-part TLDs distinct. Merges logins saved twice under different usernames, flags near-/title-only duplicates for review, and reports reused passwords. Makes no network calls. Writes a report plus an import-ready CSV. See [`password-audit/README.md`](password-audit/README.md). |
