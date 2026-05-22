#!/usr/bin/env python3
"""Convert ADF (Atlassian Document Format) JSON to Fizzy-optimal hybrid HTML.

Discovery (2026-05-21): Fizzy server accepts HTML in description/comment bodies
and auto-converts a subset to plain text. Auto-handled (well-rendered in UI):
    <p>            → paragraph w/ blank line separation
    <ul><li>       → "• item" (auto bullet)
    <ol><li>       → "1. item" (auto numbering)
    nested <ul>    → "  • item" (auto indent)
    <blockquote>   → '"text"' (auto curly quotes)

NOT preserved (stripped or merged), so we MUST encode them explicitly in text:
    <h1>..<h6>     → text only, no marker     → emit "▶ <strong>title</strong>"
    <strong>/<em>  → text only                → use emoji/prefix when meaningful
    <hr>           → disappears               → emit "<p>━━━━...</p>"
    <a href>       → text only (URL gone!)   → emit "label: URL"
    <img>          → disappears               → emit "📎 이미지: <url>"
    <pre>/<code>   → text only, no fence      → emit "<p>┌─ code:</p>...<p>└─</p>"
    <table>        → all cells concatenated   → emit plain-text table rows

Usage:
    # CLI
    cat issue.json | python3 adf_to_fizzy.py comments
    cat issue.json | python3 adf_to_fizzy.py description

    # Library
    from adf_to_fizzy import adf_to_fizzy, normalize, convert_issue_comments
"""
import json, sys, re, pathlib

HR = "━" * 30


def _html_escape(s):
    return (s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))


def adf_to_fizzy(node, depth=0, attachment_map=None):
    """Convert an ADF node to Fizzy-friendly hybrid HTML.

    attachment_map: optional {filename: url} dict. When a `media` node's
    attrs.alt matches a key, the URL is rendered alongside the image label
    so Fizzy users can click through (Fizzy strips <img> and <a href>)."""
    if not isinstance(node, dict):
        return ""
    t = node.get("type")
    children = node.get("content", []) or []
    attrs = node.get("attrs", {}) or {}

    if t == "text":
        text = node.get("text", "")
        # links: keep URL inline since Fizzy strips href
        for m in node.get("marks", []) or []:
            if m.get("type") == "link":
                href = m.get("attrs", {}).get("href", "")
                if href and href != text:
                    text = f"{text} ({href})"
        return _html_escape(text)

    if t == "paragraph":
        inner = "".join(adf_to_fizzy(c, depth, attachment_map) for c in children).strip()
        return f"<p>{inner}</p>" if inner else ""

    if t == "heading":
        inner = "".join(adf_to_fizzy(c, depth, attachment_map) for c in children).strip()
        # Fizzy strips heading markers; emit bold wrapper (text-only after sanitization, but consistent)
        return f"<p><strong>{inner}</strong></p>"

    if t == "hardBreak":
        return "<br>"

    if t == "mention":
        return _html_escape(attrs.get("text", "@user"))

    if t == "emoji":
        return _html_escape(attrs.get("shortName") or attrs.get("text", ""))

    if t == "bulletList":
        items = "".join(adf_to_fizzy(c, depth, attachment_map) for c in children)
        return f"<ul>{items}</ul>"

    if t == "orderedList":
        items = "".join(adf_to_fizzy(c, depth, attachment_map) for c in children)
        return f"<ol>{items}</ol>"

    if t == "listItem":
        parts = []
        for c in children:
            ct = c.get("type")
            if ct == "paragraph":
                inner = "".join(adf_to_fizzy(cc, depth, attachment_map) for cc in c.get("content", [])).strip()
                parts.append(inner)
            elif ct in ("bulletList", "orderedList"):
                parts.append(adf_to_fizzy(c, depth + 1, attachment_map))
            else:
                parts.append(adf_to_fizzy(c, depth, attachment_map))
        return "<li>" + "".join(parts) + "</li>"

    if t == "codeBlock":
        inner = "".join(adf_to_fizzy(c, depth, attachment_map) for c in children)
        # Use a visual code fence with plain text (Fizzy strips <pre><code>)
        lines = inner.split("\n")
        rendered = "<br>".join(_html_escape(ln) if ln else "" for ln in lines) if not inner.startswith("&lt;") else inner
        return f"<p>┌─ code ─┐</p><p>{rendered}</p><p>└────────┘</p>"

    if t in ("media", "mediaSingle", "mediaGroup", "mediaInline"):
        items = []

        def walk(n):
            if isinstance(n, dict):
                if n.get("type") == "media":
                    a = n.get("attrs", {}) or {}
                    items.append({
                        "id": a.get("id", ""),
                        "alt": a.get("alt", ""),
                    })
                for c in n.get("content", []) or []:
                    walk(c)

        walk(node)
        if not items:
            return ""
        # Resolve URL via attachment_map[alt] when available
        lines = []
        for it in items:
            label = it["alt"] or it["id"]
            url = (attachment_map or {}).get(it["alt"], "")
            if url:
                lines.append(f"{_html_escape(label)}: {url}")
            else:
                lines.append(f"{_html_escape(label)} (id: {it['id']})")
        return "<p>" + "<br>".join(lines) + "</p>"

    if t == "rule":
        return f"<p>{HR}</p>"

    if t in ("inlineCard", "blockCard"):
        url = attrs.get("url", "")
        return f"<p>{url}</p>"

    if t == "table":
        # Fizzy strips <table>/<tr>/<td> markers and merges cells.
        # Best workaround: render every row inside ONE <p>...<br>...</p> so
        # the rows stay together visually (separate <p> per row gets extra spacing).
        row_lines = []
        for i, c in enumerate(children):
            if c.get("type") != "tableRow":
                continue
            line = adf_to_fizzy(c, depth, attachment_map)  # plain "| a | b |"
            row_lines.append(line)
            # Insert a header separator after the first row if it had headers
            if i == 0:
                ncols = line.count("|") - 1
                if ncols > 0:
                    row_lines.append("|" + "|".join([" ─── "] * ncols) + "|")
        joined = "<br>".join(row_lines)
        return f"<p>{joined}</p>"

    if t == "tableRow":
        cells = []
        for c in children:
            cells.append(adf_to_fizzy(c, depth, attachment_map).strip())
        return f"| {' | '.join(cells)} |"

    if t in ("tableHeader", "tableCell"):
        # strip nested <p>/<br> wrappers since we render rows inline
        inner = "".join(adf_to_fizzy(c, depth, attachment_map) for c in children)
        inner = re.sub(r"</?p>", "", inner)
        inner = inner.replace("<br>", " ")
        return inner.strip()

    return "".join(adf_to_fizzy(c, depth, attachment_map) for c in children)


def build_attachment_map(issue_json):
    """{filename: dong-a-direct-url} for use in adf_to_fizzy(..., attachment_map=...)."""
    atts = issue_json["issues"]["nodes"][0]["fields"].get("attachment", []) or []
    # Prefer dong-a.* URLs (Atlassian login redirect works); fall back to api.atlassian.*
    out = {}
    for a in atts:
        url = a.get("content", "")
        if "api.atlassian.com" in url:
            # rewrite to dong-a direct (more user-friendly)
            url = f"https://dong-a.atlassian.net/rest/api/3/attachment/content/{a['id']}"
        out[a.get("filename", "")] = url
    return out


def normalize(text):
    """Strip excess whitespace; ensure no triple newlines."""
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def convert_comment_body(comment, attachment_map=None):
    body = comment.get("body")
    if isinstance(body, str):
        try:
            body = json.loads(body)
        except Exception:
            pass
    if isinstance(body, dict):
        return normalize(adf_to_fizzy(body, attachment_map=attachment_map))
    return normalize(str(body or ""))


def convert_issue_comments(issue_json, attachment_map=None):
    if attachment_map is None:
        attachment_map = build_attachment_map(issue_json)
    comments = issue_json["issues"]["nodes"][0]["fields"]["comment"]["comments"]
    out = []
    for c in comments:
        out.append({
            "id": c.get("id"),
            "author": (c.get("author") or {}).get("displayName", "?"),
            "created": (c.get("created") or "")[:19],
            "body": convert_comment_body(c, attachment_map),
        })
    return out


def convert_description(issue_json, attachment_map=None):
    if attachment_map is None:
        attachment_map = build_attachment_map(issue_json)
    desc = issue_json["issues"]["nodes"][0]["fields"].get("description", "")
    if isinstance(desc, dict):
        return normalize(adf_to_fizzy(desc, attachment_map=attachment_map))
    return normalize(desc or "")


def header_block(title, jira_url=None, badges=None):
    """Build a styled header block for card descriptions (no emoji)."""
    parts = [f"<p>{HR}</p>", f"<p><strong>{_html_escape(title)}</strong></p>"]
    if badges:
        parts.append("<p>" + "  ·  ".join(badges) + "</p>")
    if jira_url:
        parts.append(f"<p>Jira: {jira_url}</p>")
    parts.append(f"<p>{HR}</p>")
    return "".join(parts)


def section(label, emoji=None):  # emoji param kept for back-compat; ignored
    return f"<p>[{_html_escape(label)}]</p>"


def _cli():
    cmd = sys.argv[1] if len(sys.argv) > 1 else "comments"
    src = sys.argv[2] if len(sys.argv) > 2 else "-"
    raw = sys.stdin.read() if src == "-" else pathlib.Path(src).read_text()
    data = json.loads(raw)
    if cmd == "comments":
        print(json.dumps(convert_issue_comments(data), ensure_ascii=False, indent=2))
    elif cmd == "description":
        print(convert_description(data))
    else:
        print(f"unknown command: {cmd}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    _cli()
