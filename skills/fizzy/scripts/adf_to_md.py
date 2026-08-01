#!/usr/bin/env python3
"""Convert Atlassian Document Format (ADF) JSON to Fizzy-friendly markdown.

Fizzy's renderer is strict CommonMark:
- single `\\n` is collapsed; only blank lines start a new paragraph
- soft-break (`  \\n`) is also collapsed → use `\\n\\n` everywhere
- nested lists need 2-space indent per level

Usage:
    # As a CLI
    cat issue.json | python3 adf_to_md.py comments
    cat issue.json | python3 adf_to_md.py description

    # As a library
    from adf_to_md import adf_to_md, normalize_md, convert_issue_comments
"""
import json, sys, re, pathlib


def _apply_marks(text, marks):
    for m in marks or []:
        mt = m.get("type")
        if mt == "strong":
            text = f"**{text}**"
        elif mt == "em":
            text = f"*{text}*"
        elif mt == "code":
            text = f"`{text}`"
        elif mt == "strike":
            text = f"~~{text}~~"
        elif mt == "link":
            href = m.get("attrs", {}).get("href", "")
            text = f"[{text}]({href})"
    return text


def adf_to_md(node, depth=0):
    """Recursively convert an ADF node tree to markdown safe for Fizzy."""
    if not isinstance(node, dict):
        return ""
    t = node.get("type")
    children = node.get("content", []) or []
    attrs = node.get("attrs", {}) or {}

    if t == "text":
        return _apply_marks(node.get("text", ""), node.get("marks", []))

    if t == "paragraph":
        inner = "".join(adf_to_md(c, depth) for c in children).strip()
        return inner + "\n\n" if inner else ""

    if t == "heading":
        level = max(1, min(6, attrs.get("level", 2)))
        inner = "".join(adf_to_md(c, depth) for c in children).strip()
        return "#" * level + " " + inner + "\n\n"

    if t == "hardBreak":
        return "\n\n"  # fizzy ignores soft break; force paragraph

    if t == "mention":
        return attrs.get("text", "@user")

    if t == "emoji":
        return attrs.get("shortName") or attrs.get("text", "")

    if t in ("bulletList", "orderedList"):
        out = "".join(adf_to_md(c, depth) for c in children)
        return out + ("\n" if depth == 0 else "")

    if t == "listItem":
        indent = "  " * depth
        marker = "- "
        lines = []
        for c in children:
            ct = c.get("type")
            if ct == "paragraph":
                inner_p = "".join(adf_to_md(cc, depth) for cc in c.get("content", [])).strip()
                lines.append(indent + marker + inner_p)
            elif ct in ("bulletList", "orderedList"):
                for sub_item in c.get("content", []):
                    sub_md = adf_to_md(sub_item, depth + 1).rstrip("\n")
                    if sub_md:
                        lines.append(sub_md)
            else:
                lines.append(indent + marker + adf_to_md(c, depth).strip())
        return "\n".join(lines) + "\n"

    if t == "codeBlock":
        lang = attrs.get("language", "")
        inner = "".join(adf_to_md(c, depth) for c in children)
        return f"```{lang}\n{inner}\n```\n\n"

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
        labels = ", ".join(f"`{i}`" for i in ids)
        return f"\n_📎 이미지 첨부 ({labels}) — 원본 참조_\n\n"

    if t == "rule":
        return "\n---\n\n"

    if t in ("inlineCard", "blockCard"):
        url = attrs.get("url", "")
        return f"<{url}> "

    if t == "table":
        inner = "".join(adf_to_md(c, depth) for c in children)
        return "\n" + inner + "\n"

    if t == "tableRow":
        cells = []
        for c in children:
            cells.append(adf_to_md(c, depth).strip().replace("\n", " "))
        return "| " + " | ".join(cells) + " |\n"

    if t in ("tableHeader", "tableCell"):
        return "".join(adf_to_md(c, depth) for c in children).strip()

    # default: concat children
    return "".join(adf_to_md(c, depth) for c in children)


def normalize_md(text):
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
        return normalize_md(adf_to_md(body))
    return normalize_md(str(body or ""))


def convert_issue_comments(issue_json):
    """Take the full getJiraIssue response, return list of {id, author, created, body_md}."""
    comments = issue_json["issues"]["nodes"][0]["fields"]["comment"]["comments"]
    out = []
    for c in comments:
        out.append({
            "id": c.get("id"),
            "author": (c.get("author") or {}).get("displayName", "?"),
            "created": (c.get("created") or "")[:19],
            "body_md": convert_comment_body(c),
        })
    return out


def convert_description(issue_json):
    desc = issue_json["issues"]["nodes"][0]["fields"].get("description", "")
    if isinstance(desc, dict):
        return normalize_md(adf_to_md(desc))
    return normalize_md(desc or "")


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
