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

from . import instagram, linkedin, zernio
from .common import PublishError, SkipForNow
from .http import Http

# Any public image works; Zernio only validates the request in a dry run.
PREFLIGHT_IMAGE = "https://gsissons2.github.io/pryce-content/previews/pr-1/pipeline-check/slide-01.jpg"

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
        key = os.environ["ZERNIO_API_KEY"]
        try:
            rows = zernio.accounts(http, key)
            for a in rows:
                state = "" if a.get("isActive", True) and not a.get("needsReconnection") else " (NEEDS RECONNECTING)"
                print(f"Zernio: {a.get('platform')} @{a.get('username') or a.get('displayName')} "
                      f"id={a.get('_id') or a.get('id')}{state}")
            for platform in ("tiktok", "youtube"):
                username = os.environ.get(f"ZERNIO_{platform.upper()}_USERNAME", "").strip() or None
                try:
                    acc = os.environ.get(f"ZERNIO_{platform.upper()}_ACCOUNT_ID", "").strip() or \
                        zernio.pick_account(rows, platform, username)
                except SkipForNow as e:
                    problems.append(f"Zernio: {e}. Connect it in the Zernio dashboard (docs/SETUP.md).")
                    continue
                except PublishError as e:
                    problems.append(str(e))
                    continue
                if platform == "tiktok":
                    r = http.request("GET", f"{zernio.BASE}/accounts/{acc}/tiktok/creator-info",
                                     headers={"Authorization": f"Bearer {key}"}, params={"mediaType": "video"})
                    info = http.check(r, "Zernio TikTok creator info").json()
                    levels = [str(x.get("value")) for x in info.get("privacyLevels") or [] if isinstance(x, dict)]
                    can = (info.get("creator") or {}).get("canPostMore")
                    print(f"Zernio: TikTok privacy levels {', '.join(levels) or '(none listed)'}; "
                          f"can post now: {can}")
                    pre = zernio.tiktok_preflight(http, key, acc, PREFLIGHT_IMAGE)
                    verdicts = "; ".join(str(v.get("reason") or v) for v in pre.get("tiktok") or [] if v)
                    print(f"Zernio: TikTok preflight (dry run, nothing posted): can publish {pre.get('canPublish')}"
                          + (f" ({verdicts})" if verdicts else ""))
                    if pre.get("canPublish") is False:
                        problems.append(f"Zernio says TikTok cannot publish right now: {verdicts or 'no reason given'}")
                    if levels and zernio.TIKTOK_PRIVACY not in levels:
                        problems.append(f"TikTok does not offer privacy level {zernio.TIKTOK_PRIVACY} for this "
                                        f"account (it offers {', '.join(levels)}). Set variable "
                                        "ZERNIO_TIKTOK_PRIVACY to one of those.")
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
