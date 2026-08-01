#!/usr/bin/env python3
"""Migrate a Jira issue (description + attachments URL list + comments) into Fizzy.

Prerequisites:
    - fizzy-cli installed, authenticated, default account set (see SKILL.md §1)
    - acli authenticated to the Jira source (for resolving cloudId via env, optional)
    - For live fetch: the calling agent must invoke Atlassian MCP getJiraIssue and pass
      the resulting JSON file via --from-json. (Pure-CLI cannot call MCP tools directly.)

Usage:
    # Migrate from a cached JSON dump (agent fetched it via Atlassian MCP)
    python3 jira_to_fizzy.py --from-json /tmp/PROJ-123.json \\
        --board <fizzy-board-id> --site your-site.atlassian.net

    # Wipe stale user comments before re-running
    python3 jira_to_fizzy.py --card <N> --wipe-user-comments <username>

    # Split top-level numbered items in description into sub-cards
    python3 jira_to_fizzy.py --from-json X.json --board <B> --site <S> --split-numbered
"""
import argparse
import json
import re
import subprocess
import sys
import time
import pathlib

# allow importing sibling module
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
# Use the Fizzy-optimal hybrid HTML converter (recommended).
# adf_to_md (markdown) and adf_to_plain (pure plain text) are also available
# in this folder for non-Fizzy targets.
from adf_to_fizzy import (  # noqa: E402
    adf_to_fizzy, normalize, convert_issue_comments,
    header_block, section, HR, _html_escape,
)


def run(args, retries=3, sleep=2, timeout=60):
    """Run a subprocess with retries on transient timeouts. Returns (rc, out, err)."""
    last = ("", "")
    for _ in range(retries):
        r = subprocess.run(args, capture_output=True, text=True, timeout=timeout)
        if r.returncode == 0:
            return 0, r.stdout, r.stderr
        last = (r.stdout, r.stderr)
        msg = (r.stderr or r.stdout or "").lower()
        if "deadline exceeded" in msg or "timeout" in msg:
            time.sleep(sleep)
            continue
        return r.returncode, r.stdout, r.stderr
    return 1, last[0], last[1]


def list_user_comments(card, username):
    rc, out, _ = run(["fizzy-cli", "--json", "comment", "list", card])
    if rc != 0:
        return []
    items = json.loads(out)
    return [it for it in items if (it.get("creator") or {}).get("name") == username]


def wipe_user_comments(card, username):
    """Delete ALL comments by USERNAME. `comment list` paginates silently
    (returns ~3 per call), so loop until list returns empty."""
    total = 0
    for _ in range(50):  # generous cap for pagination
        items = list_user_comments(card, username)
        if not items:
            break
        for it in items:
            rc, _, err = run(["fizzy-cli", "comment", "delete", card, it["id"]])
            if rc == 0:
                total += 1
            else:
                print(f"  delete fail {it['id']}: {err.strip()[:120]}")
    return total


def post_comment(card, body):
    rc, out, err = run(["fizzy-cli", "comment", "create", card, "--body", body])
    return rc == 0, (out + err).strip()


def update_card(card, **fields):
    args = ["fizzy-cli", "card", "update", card]
    for k, v in fields.items():
        args += [f"--{k.replace('_','-')}", v]
    rc, out, err = run(args)
    return rc == 0, (out + err).strip()


def create_card(board, title, description, status="published"):
    args = ["fizzy-cli", "card", "create", "--board-id", board,
            "--title", title, "--description", description, "--status", status]
    rc, out, err = run(args)
    if rc != 0:
        return None, (out + err).strip()
    # parse "Card created: /1/cards/<N>.json"
    m = re.search(r"/cards/(\d+)\.json", out)
    return (m.group(1) if m else None), out.strip()


def extract_numbered_items(description_md):
    """Split a markdown body by top-level "1.", "2.", ... items.
    Returns [(num, title, body), ...] where title is the first line after the number.
    Returns [] if no numbered list found."""
    pattern = re.compile(r"^(\d+)\.\s+(.+?)(?=^\d+\.\s+|\Z)", re.MULTILINE | re.DOTALL)
    items = []
    for m in pattern.finditer(description_md):
        num = int(m.group(1))
        block = m.group(2).strip()
        title = block.splitlines()[0].strip()
        body = block
        items.append((num, title, body))
    return items


def build_parent_description(issue, site, attachment_urls):
    """Build a Fizzy-optimal hybrid HTML card description."""
    f = issue["fields"]
    summary = f.get("summary", "")
    issue_url = f"https://{site}/browse/{issue['key']}"
    proj = f.get("project", {})
    proj_str = f"{proj.get('key','')} ({proj.get('name','')})"
    itype = (f.get("issuetype") or {}).get("name", "?")
    status = (f.get("status") or {}).get("name", "?")
    assignee = (f.get("assignee") or {}).get("displayName", "(미지정)")

    desc = f.get("description", "")
    if isinstance(desc, dict):
        desc_body = normalize(adf_to_fizzy(desc))
    else:
        desc_body = f"<p>{_html_escape(desc or '(no description)')}</p>"

    parts = [
        header_block(
            f"{issue['key']}  {summary}",
            jira_url=issue_url,
            badges=[
                f"🗂️ {proj_str}",
                f"🏷️ {itype}",
                f"📊 {status}",
                f"👤 {assignee}",
            ],
        ),
        section("개요", "📋"),
        desc_body,
    ]
    if attachment_urls:
        parts.append(section("첨부 (로그인 필요)", "📎"))
        parts.append("<ul>" + "".join(f"<li>{u}</li>" for u in attachment_urls) + "</ul>")
    return "".join(parts)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--from-json", required=False, help="Path to getJiraIssue JSON dump")
    p.add_argument("--board", help="Fizzy board ID (required when creating a card)")
    p.add_argument("--site", required=True, help="Jira site hostname (e.g. your-site.atlassian.net)")
    p.add_argument("--split-numbered", action="store_true",
                   help="Create one sub-card per top-level numbered item in description")
    p.add_argument("--card", help="Existing Fizzy card number (for --wipe-user-comments)")
    p.add_argument("--wipe-user-comments", metavar="USERNAME",
                   help="Delete all comments authored by USERNAME on --card and exit")
    args = p.parse_args()

    if args.wipe_user_comments:
        if not args.card:
            sys.exit("--card is required with --wipe-user-comments")
        n = wipe_user_comments(args.card, args.wipe_user_comments)
        print(f"deleted {n} user comments")
        return

    if not args.from_json or not args.board:
        sys.exit("--from-json and --board are required for migration")

    data = json.loads(pathlib.Path(args.from_json).read_text())
    issue = data["issues"]["nodes"][0]
    key = issue["key"]
    f = issue["fields"]

    attachments = f.get("attachment", []) or []
    attach_urls = [a["content"] for a in attachments if a.get("content")]

    parent_desc = build_parent_description(issue, args.site, attach_urls)
    parent_title = f"[{key}] {f.get('summary','(no summary)')}"

    print(f"=== creating parent card on board {args.board} ===")
    parent_id, msg = create_card(args.board, parent_title, parent_desc)
    print(f"  parent #{parent_id}: {msg.splitlines()[0] if msg else ''}")
    if not parent_id:
        sys.exit(1)

    if args.split_numbered:
        desc_raw = f.get("description", "")
        # extract from plain-text projection of description
        from adf_to_plain import adf_to_plain, normalize as np  # local import
        desc_plain = np(adf_to_plain(desc_raw)) if isinstance(desc_raw, dict) else (desc_raw or "")
        items = extract_numbered_items(desc_plain)
        print(f"=== {len(items)} numbered sub-items found ===")
        for num, title, body in items:
            sub_title = f"[{key}-{num}] {title[:80]}"
            sub_desc = (
                header_block(sub_title, jira_url=f"https://{args.site}/browse/{key}",
                             badges=[f"🔗 Parent: #{parent_id}", f"🏷️ {num}번 항목"])
                + section("내용", "📋")
                + f"<p>{_html_escape(body)}</p>"
            )
            sid, msg = create_card(args.board, sub_title, sub_desc)
            print(f"  sub #{sid}: {msg.splitlines()[0] if msg else ''}")

    # Post comments (hybrid HTML)
    comments = convert_issue_comments(data)
    print(f"=== posting {len(comments)} comments to card #{parent_id} ===")
    ok = 0
    for i, c in enumerate(comments, 1):
        body = c["body"].rstrip()
        full = (
            f"<p>{HR}</p>"
            f"<p>💬 <strong>{_html_escape(c['author'])}</strong>  ·  📅 {c['created']}</p>"
            f"<p>{HR}</p>"
            + body
        )
        success, msg = post_comment(parent_id, full)
        result = "OK" if success else "FAIL"
        print(f"  [{i:2d}/{len(comments)}] {c['author']} @ {c['created']} {result}")
        if success:
            ok += 1
    print(f"\nposted {ok}/{len(comments)} comments")


if __name__ == "__main__":
    main()
