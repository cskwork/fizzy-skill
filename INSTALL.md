# Install fizzy

<details>
<summary><strong>Claude Code</strong></summary>

### Install

```bash
claude plugin marketplace add cskwork/fizzy-skill
claude plugin install fizzy@fizzy
```

Type `/fizzy`.

### Verify

```bash
claude plugin list
```

### Update

```bash
claude plugin marketplace update fizzy
```

### Uninstall

```bash
claude plugin uninstall fizzy
claude plugin marketplace remove fizzy
```

</details>

<details>
<summary><strong>Codex</strong></summary>

### Install

```bash
codex plugin marketplace add cskwork/fizzy-skill --ref main
codex plugin add fizzy@fizzy
```

Type `$fizzy`.

### Verify

```bash
codex plugin list
```

### Uninstall

```bash
codex plugin remove fizzy
codex plugin marketplace remove fizzy
```

</details>

<details>
<summary><strong>Gemini CLI</strong></summary>

### Install (extension, always-on)

```bash
gemini extensions install https://github.com/cskwork/fizzy-skill
```

### Install (command, opt-in)

```bash
mkdir -p ~/.gemini/commands
curl -fsSL https://raw.githubusercontent.com/cskwork/fizzy-skill/main/skills/fizzy-skill/agents/gemini.toml \
  -o ~/.gemini/commands/fizzy.toml
```

Type `/fizzy` in a new session.

### Verify

```bash
gemini extensions list
```

### Uninstall

```bash
gemini extensions uninstall fizzy
```

</details>

<details>
<summary><strong>Cursor, OpenCode, Amp, and other agent-skills harnesses</strong></summary>

### Install

```bash
npx skills add cskwork/fizzy-skill
npx skills add cskwork/fizzy-skill -g
```

Type `/fizzy` in a new agent chat.

### Verify

```bash
npx skills list
```

### Update

```bash
npx skills update fizzy
```

### Uninstall

```bash
npx skills remove fizzy
```

</details>

<details>
<summary><strong>Antigravity (agy)</strong></summary>

### Install

```bash
agy plugin install https://github.com/cskwork/fizzy-skill
```

### Verify

```bash
agy plugin list
```

### Uninstall

```bash
agy plugin uninstall fizzy
```

</details>
