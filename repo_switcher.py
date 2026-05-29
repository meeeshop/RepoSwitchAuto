#!/usr/bin/env python3
"""
repo_switcher.py — Change GitHub repo visibility using a double-encrypted PAT.

Usage:
    python repo_switcher.py --repos all --visibility public
    python repo_switcher.py --repos seo,pinterest --visibility private --delay-minutes 5

Repos shorthand (aliases resolved from secrets.enc at runtime):
    all        → all repos defined in secrets.enc
    seo        → REPO_SEO value in secrets.enc
    pinterest  → REPO_PINTEREST value in secrets.enc
    youtube    → REPO_YOUTUBE value in secrets.enc
"""

import argparse
import sys
import time
import logging
import urllib.request
import urllib.error
import json
from datetime import datetime, timezone

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%SZ",
)
log = logging.getLogger(__name__)


def _load_config():
    from secrets_manager import get_secret
    return {
        "owner": get_secret("GITHUB_OWNER"),
        "token": get_secret("GITHUB_PAT"),
        "repo_map": {
            "seo":       get_secret("REPO_SEO"),
            "pinterest": get_secret("REPO_PINTEREST"),
            "youtube":   get_secret("REPO_YOUTUBE"),
        },
    }


def parse_args():
    p = argparse.ArgumentParser(description="Toggle GitHub repo visibility")
    p.add_argument(
        "--repos",
        default="all",
        help="Comma-separated: seo,pinterest,youtube or 'all'",
    )
    p.add_argument(
        "--visibility",
        choices=["public", "private"],
        required=True,
        help="Target visibility",
    )
    p.add_argument(
        "--delay-minutes",
        type=float,
        default=0,
        help="Wait N minutes before applying the change (for manual on-demand use)",
    )
    return p.parse_args()


def resolve_repos(repos_arg: str, repo_map: dict) -> list[str]:
    if repos_arg.strip().lower() == "all":
        return list(repo_map.values())
    names = [r.strip().lower() for r in repos_arg.split(",")]
    resolved = []
    for name in names:
        if name not in repo_map:
            log.error("Unknown repo alias '%s'. Valid: %s", name, list(repo_map.keys()))
            sys.exit(1)
        resolved.append(repo_map[name])
    return resolved


def set_visibility(owner: str, repo: str, visibility: str, token: str) -> bool:
    url = f"https://api.github.com/repos/{owner}/{repo}"
    payload = json.dumps({"visibility": visibility}).encode()
    req = urllib.request.Request(
        url,
        data=payload,
        method="PATCH",
        headers={
            "Authorization": f"token {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "Content-Type": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(req) as resp:
            body = json.loads(resp.read().decode())
            actual = body.get("visibility", "unknown")
            log.info("[OK] %s/%s → %s", owner, repo, actual)
            return True
    except urllib.error.HTTPError as e:
        body = e.read().decode()
        log.error("[FAIL] %s/%s — HTTP %s: %s", owner, repo, e.code, body)
        return False


def main():
    args = parse_args()
    cfg = _load_config()
    owner, token, repo_map = cfg["owner"], cfg["token"], cfg["repo_map"]

    repos = resolve_repos(args.repos, repo_map)

    if args.delay_minutes > 0:
        fire_at = datetime.now(timezone.utc)
        wait_secs = args.delay_minutes * 60
        log.info(
            "Delaying %.1f minute(s) before setting %s to %s...",
            args.delay_minutes, repos, args.visibility,
        )
        log.info("Will fire at approximately %s UTC", fire_at.strftime("%H:%M:%S"))
        time.sleep(wait_secs)

    log.info("Setting %d repo(s) to '%s': %s", len(repos), args.visibility, repos)

    results = {}
    for repo in repos:
        results[repo] = set_visibility(owner, repo, args.visibility, token)

    failed = [r for r, ok in results.items() if not ok]
    if failed:
        log.error("Failed repos: %s", failed)
        sys.exit(1)

    log.info("Done. All repos set to '%s'.", args.visibility)


if __name__ == "__main__":
    main()
