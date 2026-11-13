"""Weekly token check. Prints who each credential belongs to, refreshes the Instagram token,
and writes an issue body when something expires within --warn-days.

    python -m publish.tokens [--warn-days 10] [--issue-body FILE]

Never prints a token. Safe to run any time: it only reads, plus the Instagram refresh call.
"""
from __future__ import annotations

import argparse
import os
import sys
from datetime import date
from pathlib import Path

from . import instagram, linkedin
from .common import PublishError
from .http import Http

ZERNIO_ACCOUNTS = "https://zernio.com/api/v1/accounts"


def whoami(http: Http) -> list[str]:
    """Read-only identity checks. Returns problems found."""
    problems = []
    if os.environ.get("IG_ACCESS_TOKEN"):
        try:
            r = http.request("GET", f"{instagram.HOST}/{instagram.API_VERSION}/me",
                             headers={"Authorization": f"Bearer {os.environ['IG_ACCESS_TOKEN']}"},
                             params={"fields": "user_id,username"})
            me = http.check(r, "Instagram /me").json()
            print(f"Instagram: @{me.get('username')} user_id={me.get('user_id')}")
            if os.environ.get("IG_USER_ID") and str(me.get("user_id")) != os.environ["IG_USER_ID"]:
                problems.append(f"IG_USER_ID does not match the token's user_id ({me.get('user_id')}).")
        except PublishError as e:
            problems.append(f"Instagram token check failed: {e}")
    if os.environ.get("LINKEDIN_ACCESS_TOKEN"):
        try:
            r = http.request("GET", "https://api.linkedin.com/v2/userinfo",
                             headers={"Authorization": f"Bearer {os.environ['LINKEDIN_ACCESS_TOKEN']}"})
            sub = http.check(r, "LinkedIn userinfo").json().get("sub")
            print(f"LinkedIn: person URN is urn:li:person:{sub}")
            want = os.environ.get("LINKEDIN_PERSON_URN", "")
            if want and want not in (sub, f"urn:li:person:{sub}"):
                problems.append(f"LINKEDIN_PERSON_URN does not match the token (expected urn:li:person:{sub}).")
        except PublishError as e:
            problems.append(f"LinkedIn token check failed: {e}")
    if os.environ.get("ZERNIO_API_KEY"):
        try:
            r = http.request("GET", ZERNIO_ACCOUNTS,
                             headers={"Authorization": f"Bearer {os.environ['ZERNIO_API_KEY']}"})
            body = http.check(r, "Zernio accounts").json()
            rows = body if isinstance(body, list) else (body.get("accounts") or body.get("data") or [])
            for a in rows:
                print(f"Zernio: {a.get('platform')} @{a.get('username') or a.get('displayName')} "
                      f"id={a.get('_id') or a.get('id')}")
        except PublishError as e:
            problems.append(f"Zernio key check failed: {e}")
    return problems


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="python -m publish.tokens")
    ap.add_argument("--warn-days", type=int, default=10)
    ap.add_argument("--issue-body", help="write warnings here as markdown (empty file means all good)")
    args = ap.parse_args(argv)
    http = Http()
    warnings = whoami(http)

    left = linkedin.days_left()
    if left is None:
        if os.environ.get("LINKEDIN_ACCESS_TOKEN"):
            warnings.append("LINKEDIN_TOKEN_EXPIRES is not set, so the LinkedIn reminder cannot work. "
                            "Set it to the date 60 days after you made the token.")
    else:
        print(f"LinkedIn token expires {linkedin.token_expires_at()} ({left} days).")
        if left <= args.warn_days:
            warnings.append(f"LinkedIn token expires {linkedin.token_expires_at()} ({left} days). Make a new one "
                            "with the token generator, update LINKEDIN_ACCESS_TOKEN and LINKEDIN_TOKEN_EXPIRES. "
                            "See docs/SETUP.md, LinkedIn steps.")

    if os.environ.get("IG_ACCESS_TOKEN"):
        try:
            res = instagram.refresh_token(http)
            days = res["expires_in"] // 86400
            if res["changed"]:
                warnings.append("Instagram issued a new token string on refresh. Generate a fresh token in the "
                                "Meta dashboard and update IG_ACCESS_TOKEN.")
            if days <= args.warn_days:
                warnings.append(f"Instagram token expires {res['expires_at']} ({days} days).")
        except PublishError as e:
            warnings.append(f"Instagram token refresh failed: {e}. If it says expired, generate a new token "
                            "(docs/SETUP.md, Instagram steps).")

    for w in warnings:
        print(f"::warning::{w}" if os.environ.get("GITHUB_ACTIONS") else f"WARNING: {w}")
    if args.issue_body:
        body = ""
        if warnings:
            body = (f"Token check on {date.today().isoformat()} found:\n\n" + "\n".join(f"- {w}" for w in warnings)
                    + "\n\nPosts to the affected platform will fail once the token expires.\n")
        Path(args.issue_body).write_text(body, encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
