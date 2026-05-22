---
name: fizzy
description: Use when working with a self-hosted Fizzy kanban board (e.g. fizzy.agentic-worker.store) — install/auth fizzy-cli, list boards/cards, create/update/comment cards, or migrate a Jira issue (description + attachment URLs + comments) into one or more Fizzy cards. Covers Fizzy quirks (NO markdown rendering, silent pagination in comment list, single-account auto-select, magic-link in non-TTY) and Jira ADF → Fizzy plain-text conversion.
---

# fizzy

Operate `tobiasbischoff/fizzy-cli` against a **self-hosted Fizzy instance**. Single skill covers:

1. **Onboarding** — install, base-URL, auth (PAT or magic-link), default account
2. **Daily ops** — board/card/comment CRUD with the markdown gotchas baked in
3. **Jira → Fizzy migration** — pull a Jira issue's description, attachments, and 14-comment thread into a card (+ sub-cards) without losing formatting

## Quick decision

```
Need to set up fizzy-cli from scratch?         → §1 Onboarding
Need to create/update cards or comments?       → §2 Daily ops
Need to import a Jira issue into Fizzy?        → §3 Jira → Fizzy migration
Markdown looks broken after posting to Fizzy?  → §4 Markdown quirks
```

## Inputs (env)

- `FIZZY_HOST` — base URL (e.g. `https://fizzy.agentic-worker.store`)
- `FIZZY_EMAIL` — account email
- `FIZZY_TOKEN` (preferred) OR magic-link from inbox

For Jira import: `acli` must be authenticated to the source site (`acli auth status` → ✓).

---

## §1 Onboarding

### 1.1 Install

Homebrew (documented):
```bash
brew install tobiasbischoff/tap/fizzy-cli
```

If brew is blocked, build from source:
```bash
git clone https://github.com/tobiasbischoff/fizzy-cli.git ~/.local/src/fizzy-cli
cd ~/.local/src/fizzy-cli && go build -o ~/.local/bin/fizzy-cli ./cmd/fizzy-cli
```

> **Pitfall — `go install` does NOT work.** `go.mod` declares `module fizzy-cli` (short form), so `go install github.com/...` fails. Always clone + `go build -o`.

### 1.2 Point at the host
```bash
fizzy-cli config set --base-url "$FIZZY_HOST"
fizzy-cli config show
```
Config: macOS `~/Library/Application Support/fizzy/config.json`, Linux `~/.config/fizzy/config.json`.

### 1.3 Authenticate

**A. PAT (preferred, idempotent):**
```bash
fizzy-cli auth login --token "$FIZZY_TOKEN"
fizzy-cli auth status   # → "Authenticated using token."
```

**B. Magic-link in non-TTY (Claude Code / CI):**
> `fizzy-cli auth login --email --code` is broken in non-TTY — each call re-issues a code, invalidating any pasted one. Workaround: see `references/magic-link-curl-two-step.md`.

### 1.4 Pick default account
```bash
fizzy-cli account list
fizzy-cli account set <SLUG>    # required even with only one account
```

> **Pitfall — single-account auto-select is NOT done by the CLI.** Skipping this makes `board list` etc. error cryptically.

### 1.5 Verify
```bash
fizzy-cli board list
fizzy-cli card create --board-id <ID> --title "fizzy setup test" --description "ok" --status published
fizzy-cli card list --board-id <ID> | head -3
```

---

## §2 Daily ops

| Goal                 | Command |
|----------------------|---------|
| List boards          | `fizzy-cli board list` |
| List cards           | `fizzy-cli card list --board-id <ID>` |
| Get card             | `fizzy-cli card get <N>` |
| Create card          | `fizzy-cli card create --board-id <ID> --title T --description D --status published` |
| Update card          | `fizzy-cli card update <N> --description D` |
| Attach main image    | `fizzy-cli card update <N> --image <local-path>` (one image per card) |
| List comments (JSON) | `fizzy-cli --json comment list <N>` |
| Add comment          | `fizzy-cli comment create <N> --body "text"` |
| Delete comment       | `fizzy-cli comment delete <N> <comment-id>` |

> `--json` is a **global** flag — it must come before the subcommand (`fizzy-cli --json comment list 36`), not after.

### Filter user-only comments

```bash
fizzy-cli --json comment list <N> \
  | jq -r '.[] | select(.creator.name != null) | .id'
```
(Status-change comments have `creator: {name: "System"}`, sort of — filter on a known username instead.)

### Card description / comment body — markdown rules

Fizzy renders **CommonMark** strictly: single `\n` is collapsed; only blank lines start a new paragraph. See §4.

---

## §3 Jira → Fizzy migration

End-to-end migrator: pulls issue + comments via Atlassian MCP, converts ADF → Fizzy-friendly markdown, creates parent card + optional sub-cards, posts every comment, retries on timeout.

```bash
# Prereq: Fizzy authenticated (§1), Atlassian MCP available, acli logged in
python3 ~/.claude/skills/fizzy/scripts/jira_to_fizzy.py \
  --issue A20-783 \
  --board <fizzy-board-id> \
  --site dong-a.atlassian.net \
  --split-numbered   # auto-create sub-cards from "1.", "2.", "3." in description
```

What it does (see `scripts/jira_to_fizzy.py` for the full flow):
1. Fetches the issue + comments JSON via `mcp__claude_ai_Atlassian__getJiraIssue` (or reads a cached JSON file with `--from-json PATH`).
2. Converts every ADF body to Fizzy-friendly markdown via `scripts/adf_to_md.py`.
3. Creates the parent card (compact summary + Jira URL + link to attachments).
4. If `--split-numbered`, creates one sub-card per top-level numbered item in the description.
5. Posts every Jira comment as `**[YYYY-MM-DD] author**\n\n<body>`.
6. Retries each fizzy-cli call up to 3× on `context deadline exceeded`.

**Attachment handling (images):** Atlassian's `acli` OAuth scope lacks `read:attachment-content:jira`, so URL-based downloads return 401. Use a user-issued **Personal Access Token (PAT)** with Basic auth (`scripts/atlassian_attachments.py`).

Setup once:
1. Issue a PAT at `https://id.atlassian.com/manage-profile/security/api-tokens`
2. Save to `~/.config/fizzy/.env` (chmod 600):
   ```
   ATLASSIAN_EMAIL=you@example.com
   ATLASSIAN_PAT=ATATT3...
   ATLASSIAN_SITE=your-site.atlassian.net
   ```

Download + attach:
```bash
# Download every attachment to /tmp/fizzy-attachments/
python3 ~/.claude/skills/fizzy/scripts/atlassian_attachments.py \
    download-issue --from-json /tmp/issue.json

# Then attach a representative image as the card's main image (one per card)
fizzy-cli card update <N> --image /tmp/fizzy-attachments/<id>_<name>.png
```

Note: Fizzy strips `<img>` from description bodies, so embed-in-description is impossible — only the card's main image slot works (one image per card).

**Idempotency:** to re-run cleanly, first wipe stale user comments:
```bash
python3 ~/.claude/skills/fizzy/scripts/jira_to_fizzy.py --card <N> --wipe-user-comments <username>
```

---

## §4 Rendering — Fizzy accepts HTML, NOT markdown

> **CRITICAL discovery (2026-05-21):** Fizzy server takes the body as HTML and auto-converts it to a Fizzy-rendered string. Markdown is NOT parsed — `**bold**` appears as literal asterisks. **Send hybrid HTML** for the best result.

### What Fizzy auto-renders well (use these tags)

| Tag | Result in UI |
|---|---|
| `<p>...</p>` | paragraph with blank-line separation |
| `<ul><li>X</li></ul>` | `• X` (auto bullet) |
| `<ol><li>X</li></ol>` | `1. X` (auto numbering) |
| nested `<ul>` inside `<li>` | `  • X` (auto 2-space indent) |
| `<blockquote>X</blockquote>` | `“X”` (auto curly quotes) |
| `<br>` | line break inside paragraph |

### What Fizzy STRIPS (encode in text yourself)

| Tag | Fizzy behavior | Workaround |
|---|---|---|
| `<h1>`…`<h6>` | shown as plain text, no marker | wrap: `<p>▶ <strong>title</strong></p>` (use emoji prefix as marker) |
| `<strong>` / `<em>` | stripped | use emoji or `「 」` symbols if emphasis matters |
| `<hr>` | disappears | emit `<p>━━━━━━━━━━━━━━━━━━━━</p>` |
| `<a href="X">label</a>` | text only, **URL is gone** | emit `<p>label: X</p>` or `<p>🔗 X</p>` |
| `<img>` | disappears | emit `<p>이미지: <url></p>` (no emoji) |
| `<pre>`/`<code>` | stripped | emit `<p>코드:</p><p>…</p><p>---</p>` |
| `<table>` | all cells concatenated, no structure | emit rows as `<p>\| a \| b \|</p>` |

### Other quirks

| Quirk | Symptom | Fix |
|---|---|---|
| `comment list` silent pagination | Only ~3 items per call; the rest are invisible | Loop list+delete until empty when wiping; never assume `length == total` |
| Bash heredoc + `(` / backtick | `unexpected EOF` or `command not found` | Build bodies in Python with `subprocess.run([cmd, '--description', text])` |
| `--json` after subcommand | Silently ignored | Place it **before** subcommand: `fizzy-cli --json comment list 36` |
| Single-account auto-default | `board list` errors after fresh auth | Run `fizzy-cli account set <SLUG>` even with one account |
| `--image PATH` | Local file path only, one main image per card | Download first; extras → inline URLs in description |

## Recommended layout for migrated cards

> **POLICY — No emoji in deliverables.** Cards, comments, reports are business artifacts.
> Use bracket labels (`[목적]`, `[상세 작업]`) and box-drawing rules (`━`, `·`) only.
> No pictographic emoji (📌 🎯 ✅ 📎 etc.). Geometric arrows (▶ ▸ ■) are also discouraged
> because some clients render them with emoji presentation.

```html
<p>━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━</p>
<p>[KEY] 제목 영역</p>
<p>프로젝트: AIDT  ·  타입: Bug  ·  상태: 진행 중  ·  담당: 홍길동</p>
<p>Jira: https://...</p>
<p>━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━</p>
<p>[개요]</p>
<p>본문 단락 1</p>
<ul><li>핵심 1</li><li>핵심 2</li></ul>
<p>[첨부 (로그인 필요)]</p>
<ul><li>오류 화면: https://...</li></ul>
```

This is what `scripts/adf_to_fizzy.py` + `header_block()` / `section()` produce automatically.

## Common mistakes

- **Sending markdown and hoping it renders** — Fizzy treats `**X**` as literal text. Use HTML or wrap content with `adf_to_fizzy`.
- **Trusting `comment list` length** — it's page 1 (~3 items) only. Loop until empty when wiping.
- **Filtering by `creator.name != "System"`** — some events have empty `creator.name`. Match on a specific username.
- **Posting via `bash -c` with `--description "...\`x\`..."`** — backticks trigger command substitution. Always use Python `subprocess.run([...])`.
- **`<a href>` for important URLs** — Fizzy strips the href. Always print the URL as visible text.
- **`<table>` for important tabular data** — cells get concatenated with no separator. Build the table yourself with `<p>| a | b |</p>` rows.

## Files

- `scripts/adf_to_fizzy.py` — **(recommended)** ADF → Fizzy hybrid HTML with auto-renderable tags + text fallbacks for stripped ones. Provides `adf_to_fizzy()`, `header_block()`, `section()`, `HR`.
- `scripts/adf_to_plain.py` — ADF → pure plain text (use only when you specifically want to avoid HTML).
- `scripts/adf_to_md.py` — ADF → markdown (for non-Fizzy targets; do NOT send to Fizzy).
- `scripts/jira_to_fizzy.py` — end-to-end Jira issue → Fizzy card(s) migrator with retry + pagination-safe wipe, using hybrid HTML.
- `references/magic-link-curl-two-step.md` — non-TTY magic-link workaround.
- `references/operations.md` — extended fizzy-cli command reference.
