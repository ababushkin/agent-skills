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

## Bundled Codex runtime skills

These are general-purpose document skills (not part of the selling toolkit),
kept under `codex-primary-runtime/`:

| Skill | What it does | Use it when |
|-------|--------------|-------------|
| **PowerPoint** (`codex-primary-runtime/slides`) | Create, edit, render, verify, and export editable `.pptx` slide decks. | Building or revising a presentation / slide deck / PPTX. |
| **Excel** (`codex-primary-runtime/spreadsheets`) | Create, modify, analyse, and visualise spreadsheets (`.xlsx`/`.xls`/`.csv`/`.tsv`) with formulas, formatting, charts, and tables. | Building or analysing a spreadsheet, model, dashboard, or tracker. |
