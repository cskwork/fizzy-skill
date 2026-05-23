# fizzy-skill

A Claude Code / Codex CLI **skill** for operating a self-hosted [Fizzy](https://github.com/tobiasbischoff/fizzy-cli) kanban board — onboarding, daily card/comment CRUD, and end-to-end Jira-to-Fizzy migration.

**Landing page:** https://cskwork.github.io/fizzy-skill/

## Why this exists

Fizzy is a Basecamp-style kanban tool. Its CLI works well, but the server's renderer has subtle quirks that bite every first-time integrator:

- **Fizzy is NOT a markdown renderer.** `**bold**` stays as literal asterisks. The server accepts HTML but silently strips `<h*>`, `<strong>`, `<hr>`, `<a href>`, `<img>`, `<pre>`, `<table>`.
- **`--json` is a global flag** — it must come *before* the subcommand, or it is silently ignored.
- **`comment list` paginates silently** — page 1 returns roughly 3 items; the rest are invisible unless you loop.
- **Single-account auto-default is NOT done by the CLI** — `fizzy-cli account set <SLUG>` is required even when only one account exists.
- **`auth login --email --code` in non-TTY** re-issues a code on every call, invalidating the one already in the user's inbox.

This skill bakes those traps into one decision-tree document so an agent can hit the ground running.

## What's in the box

| Path | Purpose |
|---|---|
| `SKILL.md` | The skill itself — onboarding, daily ops, Jira migration, Fizzy HTML quirks |
| `scripts/adf_to_fizzy.py` | ADF → Fizzy-optimal hybrid HTML (recommended for cards/comments) |
| `scripts/adf_to_md.py` | ADF → markdown (for non-Fizzy targets) |
| `scripts/adf_to_plain.py` | ADF → pure plain text |
| `scripts/jira_to_fizzy.py` | End-to-end Jira issue → Fizzy card(s) migrator with retry + pagination-safe wipe |
| `scripts/atlassian_attachments.py` | PAT-based attachment downloader (acli OAuth scope can't fetch attachment content) |
| `references/magic-link-curl-two-step.md` | Non-TTY magic-link workaround |
| `references/operations.md` | Extended fizzy-cli command reference |

## Install

The repo is a single SKILL.md plus a `scripts/` folder. Drop it into your skills directory:

```bash
# Claude Code
git clone https://github.com/cskwork/fizzy-skill.git ~/.claude/skills/fizzy

# Codex CLI (same SKILL.md format)
git clone https://github.com/cskwork/fizzy-skill.git ~/.codex/skills/fizzy
```

Both ecosystems read the YAML front matter and Markdown body identically, so a single clone serves either CLI.

## Quick start

```bash
export FIZZY_HOST="https://fizzy.example.com"
export FIZZY_TOKEN="..."          # PAT from your Fizzy account settings

fizzy-cli config set --base-url "$FIZZY_HOST"
fizzy-cli auth   login --token "$FIZZY_TOKEN"
fizzy-cli account set <SLUG>      # required even with one account
fizzy-cli board list
```

For migration:

```bash
python3 scripts/jira_to_fizzy.py \
  --from-json /tmp/PROJ-123.json \
  --board <fizzy-board-id> \
  --site your-site.atlassian.net \
  --split-numbered
```

See [`SKILL.md`](./SKILL.md) for the full guide and the [landing page](https://cskwork.github.io/fizzy-skill/) for a quick visual overview.

## License

[MIT](./LICENSE) — use freely, including in commercial projects. No warranty.

## Acknowledgements

- [`tobiasbischoff/fizzy-cli`](https://github.com/tobiasbischoff/fizzy-cli) — the upstream CLI this skill operates.
- Atlassian Document Format spec — the source of truth for the ADF → HTML/plain converters.
