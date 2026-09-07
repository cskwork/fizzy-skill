# Magic-link in non-TTY (curl two-step)

`fizzy-cli auth login --email X --code Y` is broken in non-TTY contexts (Claude Code, CI, Docker). Internally it does `POST /session` (which **issues a new code and emails it, replacing any previous one**) and then `POST /session/magic_link` with `--code` against the freshly-issued `pending_authentication_token`. The pending token is not persisted, so the user's already-pasted code is invalidated by the time you verify it.

Workaround: do the two HTTP calls yourself, keeping the pending token in shell scope.

```bash
# Inputs
: "${FIZZY_HOST:?}"
: "${FIZZY_EMAIL:?}"

# Step 1 — request magic link, capture pending token (stays in shell scope)
PENDING=$(curl -s -X POST "$FIZZY_HOST/session" \
  -H 'Content-Type: application/json' \
  -H 'User-Agent: fizzy-cli/dev' \
  -H 'Accept: application/json' \
  -d "{\"email_address\":\"$FIZZY_EMAIL\"}" \
  | python3 -c 'import json,sys;print(json.load(sys.stdin)["pending_authentication_token"])')
echo "pending token captured (len=${#PENDING})"

# A 6-character code is now in the user's inbox. Paste it.
read -r CODE

# Step 2 — verify against the SAME pending token (does NOT trigger another email)
SESSION=$(curl -s -X POST "$FIZZY_HOST/session/magic_link" \
  -H 'Content-Type: application/json' \
  -H 'User-Agent: fizzy-cli/dev' \
  -H 'Accept: application/json' \
  -H "Cookie: pending_authentication_token=$PENDING" \
  -d "{\"code\":\"$CODE\"}" \
  | python3 -c 'import json,sys;print(json.load(sys.stdin)["session_token"])')

# Step 3 — write session_token into fizzy-cli's config (CLI accepts it transparently)
CONFIG="$HOME/Library/Application Support/fizzy/config.json"   # Linux: ~/.config/fizzy/config.json
python3 - "$CONFIG" "$SESSION" <<'PY'
import json, sys, pathlib
path = pathlib.Path(sys.argv[1])
cfg = json.loads(path.read_text()) if path.exists() else {}
cfg["session_token"] = sys.argv[2]
cfg["token"] = ""
path.parent.mkdir(parents=True, exist_ok=True)
path.write_text(json.dumps(cfg, indent=2) + "\n")
PY

fizzy-cli auth status   # → "Authenticated using session token."
```

## Pitfalls

| # | Symptom | Fix |
|---|---------|-----|
| 1 | `POST /session` returns `422 Unprocessable Entity` (HTML) | Add `User-Agent: fizzy-cli/dev`. CDN rejects requests without a UA. |
| 2 | `401 {"message":"Try another code."}` from CLI | The pending token mismatched — each `--email` call re-issues. Use the two-step. |
| 3 | Session token works but `board list` errors | Run `fizzy-cli account set <SLUG>` (no auto-default for single accounts). |
