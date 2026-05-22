#!/usr/bin/env python3
"""Convert Atlassian Document Format (ADF) JSON to plain text for Fizzy.

CRITICAL: Fizzy does NOT render markdown. Card/comment bodies are stored as
    {html: "<div class='action-text-content'>{raw_text}</div>", plain_text: raw_text}
So `**bold**` shows literal asterisks. Use plain text only.

Differences vs adf_to_md.py:
 - No `**bold**`, `*em*`, backticks, or `# heading` markers
 - Headings → `[H1]`, `■ H2`, `▸ H3+`
 - Bullets → `•` with 2-space indent per nesting depth
 - Horizontal rule → `─` × 40
 - Code blocks → fenced with `─` × 40 lines (no triple backticks)
 - Links → plain URL (after the link text, in parens)
 - Media → `[📎 이미지 첨부: <ids>] (원본 참조)`

Usage:
    # CLI
    cat issue.json | python3 adf_to_plain.py comments
    cat issue.json | python3 adf_to_plain.py description

    # Library
    from adf_to_plain import adf_to_plain, normalize, convert_issue_comments
"""
import json, sys, re, pathlib


def adf_to_plain(node, depth=0):
    if not isinstance(node, dict):
        return ""
    t = node.get("type")
    children = node.get("content", []) or []
    attrs = node.get("attrs", {}) or {}

    if t == "text":
        text = node.get("text", "")
        # for links: keep text + url in parens
        for m in node.get("marks", []) or []:
            if m.get("type") == "link":
                href = m.get("attrs", {}).get("href", "")
                if href and href != text:
                    text = f"{text} ({href})"
        return text

    if t == "paragraph":
        inner = "".join(adf_to_plain(c, depth) for c in children).rstrip()
        return inner + "\n\n" if inner else ""

    if t == "heading":
        level = max(1, min(6, attrs.get("level", 2)))
        inner = "".join(adf_to_plain(c, depth) for c in children).strip()
        if level == 1: return f"[{inner}]\n\n"
        if level == 2: return f"■ {inner}\n\n"
        return f"▸ {inner}\n\n"

    if t == "hardBreak":
        return "\n"

    if t == "mention":
        return attrs.get("text", "@user")

    if t == "emoji":
        return attrs.get("shortName") or attrs.get("text", "")

    if t in ("bulletList", "orderedList"):
        return "".join(adf_to_plain(c, depth) for c in children) + ("\n" if depth == 0 else "")

    if t == "listItem":
        indent = "  " * depth
        marker = "• "
        lines = []
        for c in children:
            ct = c.get("type")
            if ct == "paragraph":
                inner = "".join(adf_to_plain(cc, depth) for cc in c.get("content", [])).strip()
                lines.append(indent + marker + inner)
            elif ct in ("bulletList", "orderedList"):
                for sub_item in c.get("content", []):
                    nested = adf_to_plain(sub_item, depth + 1).rstrip("\n")
                    if nested:
                        lines.append(nested)
            else:
                lines.append(indent + marker + adf_to_plain(c, depth).strip())
        return "\n".join(lines) + "\n"

    if t == "codeBlock":
        inner = "".join(adf_to_plain(c, depth) for c in children)
        sep = "─" * 40
        return f"\n{sep}\n{inner}\n{sep}\n\n"

    if t in ("media", "mediaSingle", "mediaGroup", "mediaInline"):
        ids = []

        def walk(n):
            if isinstance(n, dict):
                if n.get("type") == "media":
                    mid = n.get("attrs", {}).get("id")
                    if mid:
                        ids.append(mid)
                for c in n.get("content", []) or []:
                    walk(c)

        walk(node)
        if not ids:
            return ""
        return "\n[📎 이미지 첨부: " + ", ".join(ids) + "] (원본 참조)\n\n"

    if t == "rule":
        return "\n" + ("─" * 40) + "\n\n"

    if t in ("inlineCard", "blockCard"):
        return attrs.get("url", "") + " "

    if t == "table":
        return "\n" + "".join(adf_to_plain(c, depth) for c in children) + "\n"

    if t == "tableRow":
        cells = [adf_to_plain(c, depth).strip().replace("\n", " ") for c in children]
        return " | ".join(cells) + "\n"

    if t in ("tableHeader", "tableCell"):
        return "".join(adf_to_plain(c, depth) for c in children).strip()

    return "".join(adf_to_plain(c, depth) for c in children)


def normalize(text):
    """Collapse 3+ blank lines into 2; ensure trailing newline."""
    return re.sub(r"\n{3,}", "\n\n", text).strip() + "\n"


def convert_comment_body(comment):
    body = comment.get("body")
    if isinstance(body, str):
        try:
            body = json.loads(body)
        except Exception:
            pass
    if isinstance(body, dict):
        return normalize(adf_to_plain(body))
    return normalize(str(body or ""))


def convert_issue_comments(issue_json):
    comments = issue_json["issues"]["nodes"][0]["fields"]["comment"]["comments"]
    out = []
    for c in comments:
        out.append({
            "id": c.get("id"),
            "author": (c.get("author") or {}).get("displayName", "?"),
            "created": (c.get("created") or "")[:19],
            "body": convert_comment_body(c),
        })
    return out


def convert_description(issue_json):
    desc = issue_json["issues"]["nodes"][0]["fields"].get("description", "")
    if isinstance(desc, dict):
        return normalize(adf_to_plain(desc))
    return normalize(desc or "")


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
