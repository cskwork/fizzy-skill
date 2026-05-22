# fizzy-cli operations reference

## Global flags (must come BEFORE the subcommand)

| Flag | Purpose |
|------|---------|
| `--json` | JSON output (machine-readable) |
| `--plain` | Plain, line-oriented output |
| `--base-url URL` | Override base URL (env: `FIZZY_BASE_URL`) |
| `--token T` | PAT inline (env: `FIZZY_TOKEN`) |
| `--account SLUG` | Override default account (env: `FIZZY_ACCOUNT`) |
| `--no-color` | Disable color output |

> Putting `--json` *after* the subcommand silently fails. Always: `fizzy-cli --json comment list 36`.

## Board

```bash
fizzy-cli board list                    # tabular; ID is first column
fizzy-cli board get <board-id>          # full details
```

## Card

```bash
fizzy-cli card list --board-id <ID> [--sorted-by latest|newest|oldest]
fizzy-cli card list --board-id <ID> --term "keyword"        # search
fizzy-cli card list --indexed-by closed|not_now|stalled     # filter
fizzy-cli card list --all                                   # follow pagination

fizzy-cli card get <N>
fizzy-cli card create --board-id <ID> --title T --description D [--status drafted|published] [--tag-id ID ...] [--image PATH]
fizzy-cli card update <N> [--title T] [--description D] [--status ...] [--tag-id ID ...] [--image PATH]
fizzy-cli card delete <N>

fizzy-cli card close <N>            # mark closed
fizzy-cli card reopen <N>
fizzy-cli card not-now <N>          # postpone
fizzy-cli card triage <N> --column-id <C>
fizzy-cli card untriage <N>
fizzy-cli card tag <N> --title <tag-title>
fizzy-cli card assign <N> --assignee-id <user-id>
fizzy-cli card watch <N>   /  unwatch <N>
```

### Card creation pitfalls

- **`--description` with backticks**: in bash, backtick inside double-quoted string triggers command substitution. Use single-quoted variables, here-docs with `\\` escapes, or — easiest — drive fizzy-cli from Python with `subprocess.run([...])`.
- **`--image PATH`** accepts a **local file path**, not a URL. Remote URLs need to be downloaded first.
- **One main image per card.** Additional images can only be linked inline via markdown URLs.

## Comment

```bash
fizzy-cli comment list <N>                        # plain
fizzy-cli --json comment list <N>                 # JSON for scripting
fizzy-cli comment get <N> <comment-id>
fizzy-cli comment create <N> --body "text"
fizzy-cli comment update <N> <comment-id> --body "text"
fizzy-cli comment delete <N> <comment-id>
```

### Comment pitfalls

- Status-change events show up as comments with `creator.name == "System"` (or empty). When deleting user comments, filter by your specific username — `!= "System"` may miss some system events.
- The API occasionally returns `context deadline exceeded`. Wrap calls in a retry loop (3 attempts, 2 s back-off) — the migrator script does this.

## Tag / User / Notification

```bash
fizzy-cli tag list
fizzy-cli user list
fizzy-cli notification list [--unread]
```

## Config

```bash
fizzy-cli config show
fizzy-cli config set --base-url <URL>
fizzy-cli config set --account <SLUG>
```

Config file paths:
- macOS: `~/Library/Application Support/fizzy/config.json`
- Linux: `~/.config/fizzy/config.json`

## Auth

```bash
fizzy-cli auth status                 # check current auth
fizzy-cli auth login --token <PAT>    # preferred
fizzy-cli auth login --email <addr>   # only works in real TTY
fizzy-cli auth logout
```

For non-TTY magic-link, see `magic-link-curl-two-step.md`.
