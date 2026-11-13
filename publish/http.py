"""One HTTP client for every platform.

Live mode sends requests with `requests`. Dry-run mode prints the exact request
(method, URL, redacted headers, JSON body) and returns a fake response instead,
so nothing leaves the machine.
"""
from __future__ import annotations

import json
import sys
import time
from typing import Any, Callable
from urllib.parse import urlencode, urlsplit, urlunsplit

import requests
from requests.structures import CaseInsensitiveDict

from .common import PublishError, UncertainError

SECRET_HEADERS = {"authorization"}
SECRET_PARAMS = {"access_token", "client_secret"}


def safe_url(url: str) -> str:
    """URL without its query string, for error messages that end up in git."""
    parts = urlsplit(url)
    return urlunsplit((parts.scheme, parts.netloc, parts.path, "", ""))


def redact_headers(headers: dict | None) -> dict:
    out = {}
    for k, v in (headers or {}).items():
        if k.lower() in SECRET_HEADERS:
            scheme = str(v).split(" ", 1)
            out[k] = f"{scheme[0]} ***" if len(scheme) == 2 else "***"
        else:
            out[k] = v
    return out


def redact_params(params: dict | None) -> dict:
    return {k: ("***" if k in SECRET_PARAMS else v) for k, v in (params or {}).items()}


class FakeResponse:
    """What dry-run (and the tests) hand back instead of a real response."""

    def __init__(self, status_code: int = 200, json_body: Any = None, headers: dict | None = None):
        self.status_code = status_code
        self._json = json_body
        self.headers = CaseInsensitiveDict(headers or {})
        self.text = "" if json_body is None else json.dumps(json_body)
        self.ok = 200 <= status_code < 300

    def json(self):
        if self._json is None:
            raise ValueError("response has no JSON body")
        return self._json


class HttpError(PublishError):
    def __init__(self, what: str, resp):
        self.status = resp.status_code
        body = (getattr(resp, "text", "") or "")[:800]
        super().__init__(f"{what}: HTTP {resp.status_code}: {body}")


class Http:
    def __init__(self, dry_run: bool = False, out=None, sleep: Callable[[float], None] | None = None):
        self.dry_run = dry_run
        self.out = out or sys.stdout
        if sleep is not None:
            self.sleep = sleep
        else:
            self.sleep = (lambda s: None) if dry_run else time.sleep

    def request(self, method: str, url: str, *, headers: dict | None = None, params: dict | None = None,
                json_body: Any = None, data: bytes | None = None, describe: Any = None,
                timeout: float = 60, final: bool = False, allow_redirects: bool = True,
                dry: Any = None, dry_status: int = 200, dry_headers: dict | None = None):
        """Send one request.

        describe: what to print instead of the body in dry-run (for base64 or binary bodies).
        final: this call makes the post go live, so a lost response is "uncertain", not a plain failure.
        dry, dry_status, dry_headers: the fake response used in dry-run.
        """
        if self.dry_run:
            self._print(method, url, headers, params, json_body, data, describe)
            return FakeResponse(dry_status, dry if dry is not None else {}, dry_headers)
        where = f"{method} {safe_url(url)}"
        try:
            return requests.request(method, url, headers=headers, params=params, json=json_body, data=data,
                                    timeout=timeout, allow_redirects=allow_redirects)
        except requests.exceptions.ConnectTimeout as e:
            raise PublishError(f"{where}: could not connect ({type(e).__name__})") from None
        except (requests.exceptions.Timeout, requests.exceptions.ConnectionError) as e:
            if final:
                raise UncertainError(f"{where}: no response to the publish call ({type(e).__name__}). "
                                     "It may or may not have posted.") from None
            raise PublishError(f"{where}: {type(e).__name__}") from None
        except requests.RequestException as e:
            raise PublishError(f"{where}: {type(e).__name__}") from None

    def check(self, resp, what: str, final: bool = False):
        if 200 <= resp.status_code < 300:
            return resp
        if final and resp.status_code >= 500:
            raise UncertainError(f"{what}: HTTP {resp.status_code} on the publish call. "
                                 "It may or may not have posted.")
        raise HttpError(what, resp)

    def poll(self, fn: Callable[[], tuple[bool, Any]], *, interval: float, timeout: float, what: str):
        """Call fn until it returns (True, value). fn may raise to stop early."""
        waited = 0.0
        while True:
            done, value = fn()
            if done:
                return value
            if waited >= timeout:
                raise PublishError(f"{what}: still not ready after {int(timeout)} s (last state: {value})")
            self.sleep(interval)
            waited += interval

    def _print(self, method, url, headers, params, json_body, data, describe):
        w = self.out.write
        full = url + ("?" + urlencode(redact_params(params)) if params else "")
        w(f"\n[dry-run] {method} {full}\n")
        if headers:
            w(f"  headers: {json.dumps(redact_headers(headers))}\n")
        if describe is not None:
            body = describe if isinstance(describe, str) else json.dumps(describe, indent=2, ensure_ascii=False)
            w("  body: " + body.replace("\n", "\n  ") + "\n")
        elif json_body is not None:
            w("  json: " + json.dumps(json_body, indent=2, ensure_ascii=False).replace("\n", "\n  ") + "\n")
        elif data is not None:
            w(f"  body: <{len(data)} bytes>\n")
