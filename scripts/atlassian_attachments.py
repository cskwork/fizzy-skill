#!/usr/bin/env python3
"""Download Atlassian Jira attachments via PAT.

Atlassian's `acli` OAuth scope does NOT include `read:attachment-content:jira`,
so attachment URLs return 401 with the acli token. A user-issued Personal
Access Token (PAT) with Basic auth works.

Setup:
    1. Create a PAT at https://id.atlassian.com/manage-profile/security/api-tokens
    2. Save credentials to ~/.config/fizzy/.env:
        ATLASSIAN_EMAIL=you@example.com
        ATLASSIAN_PAT=ATATT3...
        ATLASSIAN_SITE=your-site.atlassian.net
    3. chmod 600 ~/.config/fizzy/.env

Usage:
    # CLI: download attachment by id
    python3 atlassian_attachments.py download 42052
    python3 atlassian_attachments.py download-issue A20-783 --from-json issue.json

    # Library
    from atlassian_attachments import load_env, download_attachment, download_all
"""
import argparse, base64, json, mimetypes, pathlib, sys, urllib.error, urllib.request

DEFAULT_ENV = pathlib.Path.home() / ".config/fizzy/.env"
DEFAULT_CACHE = pathlib.Path("/tmp/fizzy-attachments")


def load_env(path=DEFAULT_ENV):
    """Parse a simple KEY=value .env file. Returns dict."""
    env = {}
    if not path.exists():
        raise FileNotFoundError(f"{path} not found. See module docstring for setup.")
    for ln in path.read_text().splitlines():
        ln = ln.strip()
        if not ln or ln.startswith("#") or "=" not in ln:
            continue
        k, v = ln.split("=", 1)
        env[k.strip()] = v.strip()
    for required in ("ATLASSIAN_EMAIL", "ATLASSIAN_PAT", "ATLASSIAN_SITE"):
        if not env.get(required):
            raise ValueError(f"{path} is missing {required}")
    return env


def _basic_auth(email, pat):
    return base64.b64encode(f"{email}:{pat}".encode()).decode()


def download_attachment(att_id, env=None, cache_dir=DEFAULT_CACHE, filename=None, timeout=30):
    """Download one attachment by id. Returns the local Path or None on failure."""
    env = env or load_env()
    cache_dir = pathlib.Path(cache_dir)
    cache_dir.mkdir(parents=True, exist_ok=True)
    name = filename or f"{att_id}.bin"
    out = cache_dir / f"{att_id}_{name}"
    if out.exists() and out.stat().st_size > 0:
        return out
    url = f"https://{env['ATLASSIAN_SITE']}/rest/api/3/attachment/content/{att_id}"
    req = urllib.request.Request(url, headers={
        "Authorization": f"Basic {_basic_auth(env['ATLASSIAN_EMAIL'], env['ATLASSIAN_PAT'])}",
        "Accept": "*/*",
        "User-Agent": "fizzy-attachments/1.0",
    })
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            out.write_bytes(r.read())
        return out
    except urllib.error.HTTPError as e:
        print(f"  ! HTTP {e.code} for {att_id}", file=sys.stderr)
        return None


def download_all(issue_json, env=None, cache_dir=DEFAULT_CACHE):
    """Download every attachment on a Jira issue (from getJiraIssue JSON).
    Returns {att_id: (Path, filename, mime_type)}."""
    env = env or load_env()
    if isinstance(issue_json, (str, pathlib.Path)):
        issue_json = json.loads(pathlib.Path(issue_json).read_text())
    atts = issue_json["issues"]["nodes"][0]["fields"].get("attachment", []) or []
    out = {}
    for a in atts:
        p = download_attachment(a["id"], env=env, cache_dir=cache_dir, filename=a.get("filename"))
        if p:
            out[a["id"]] = (p, a.get("filename", ""), a.get("mimeType", ""))
    return out


def is_image(path):
    mime, _ = mimetypes.guess_type(str(path))
    return (mime or "").startswith("image/")


def _cli():
    p = argparse.ArgumentParser()
    sub = p.add_subparsers(dest="cmd", required=True)
    one = sub.add_parser("download", help="Download a single attachment by id")
    one.add_argument("att_id")
    one.add_argument("--filename")
    full = sub.add_parser("download-issue", help="Download all attachments on a Jira issue")
    full.add_argument("--from-json", required=True)
    args = p.parse_args()

    env = load_env()
    if args.cmd == "download":
        p = download_attachment(args.att_id, env=env, filename=args.filename)
        print(p if p else "FAILED")
    elif args.cmd == "download-issue":
        results = download_all(args.from_json, env=env)
        for aid, (path, name, mime) in results.items():
            print(f"{aid}\t{path.stat().st_size}\t{mime}\t{path}")


if __name__ == "__main__":
    _cli()
