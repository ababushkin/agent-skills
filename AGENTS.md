# AGENTS.md

Instructions for any coding agent (Claude Code, Codex, etc.) working in this repository. Tool-agnostic by design — see `CLAUDE.md` for any Claude-Code-specific additions.

## What this repo is

A personal utility skill pack. Skills live at `<name>/SKILL.md` (flat layout).

## Local dev

Python version is pinned via `.mise.toml`. With [`mise`](https://mise.jdx.dev) installed, run `mise trust` then `mise install` in the repo root to provision it; `python3` then resolves to the pinned version. The resell-au scripts and their goldens were verified against this version.

## Workspace governance

This repo follows the workflow governance in the **Workflow pack** (Claude Code plugin `workflow`): the code-review/completion gate, the comment standard, the Linear initiative/cycle model, and the always-on session index. Entry point is the pack's `rules/GOVERNANCE.md`.

- With the pack installed, a SessionStart hook loads it automatically — no setup here.
- Checked this repo out standalone? Install the Workflow pack to load these rules.

Read it before any workflow work. Do not restate or summarise those rules here — keep only agent-skills-specific instructions (stack, conventions, commands) below.

## Git

Conventional-commit-ish prefixes: `feat:`, `fix:`, `chore:`, `docs:`, `refactor:`. Subject line ≤ 70 chars; details in the body if needed. Do not add `Co-Authored-By` trailers.
