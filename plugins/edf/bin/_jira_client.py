"""Jira Cloud REST client — the only tracker code that sends credentials (ADR-0041).

Turns HTTP failures into named TrackerErrors, never echoes the token, never retries and
never follows a redirect. Configuration arrives as a JiraConfig; this module reads no
environment (tracker.py owns that, and the https check).

Design reference: plugins/edf/docs/design/v3/lld-v3-e3-2-jira-backend.md §1.2
"""

from __future__ import annotations

import base64
import http.client
import json
import urllib.error
import urllib.parse
import urllib.request

from _tracker_contract import TrackerError

_API_PREFIX = "/rest/api/3/"
_DETAIL_LIMIT = 200


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    """A redirect would carry the Authorization header to another host (invariant J2)."""

    def redirect_request(self, *args, **kwargs):
        return None


class JiraClient:
    def __init__(self, cfg, *, timeout: float = 30.0):
        self._base = cfg.host.rstrip("/")
        self._netloc = urllib.parse.urlsplit(self._base).netloc
        self._token = cfg.token
        self._credential = base64.b64encode(f"{cfg.email}:{cfg.token}".encode()).decode()
        self._timeout = timeout
        self._opener = urllib.request.build_opener(_NoRedirect())

    def __repr__(self) -> str:
        return f"JiraClient(host={self._base!r})"

    def request(self, method: str, path: str, *, query: dict[str, str] | None = None,
                body: dict | None = None) -> tuple[int, dict | None]:
        """(status, parsed JSON or None) for 2xx and 404; TrackerError for everything else."""
        if not path.startswith(_API_PREFIX):
            raise TrackerError(f"Jira request failed: unsupported path '{path}'")
        url = self._base + path + (f"?{urllib.parse.urlencode(query)}" if query else "")
        req = urllib.request.Request(url, method=method, headers={
            "Authorization": f"Basic {self._credential}",
            "Accept": "application/json",
            "Content-Type": "application/json",
        }, data=None if body is None else json.dumps(body).encode())
        try:
            with self._opener.open(req, timeout=self._timeout) as resp:
                return resp.status, self._parse(resp.read())
        except urllib.error.HTTPError as e:
            return self._http_error(e)
        except (urllib.error.URLError, OSError, http.client.HTTPException) as e:
            raise TrackerError(f"Jira request failed: cannot reach {self._netloc}") from e

    # Justification: keeps request() under the complexity gate; owns the status-to-error table.
    def _http_error(self, e: urllib.error.HTTPError) -> tuple[int, dict | None]:
        status = e.code
        if status == 404:
            return 404, None
        if status in (401, 403):
            raise TrackerError(f"Jira authentication failed ({status})")
        if status == 429 or status >= 500 or status < 400:
            raise TrackerError(f"Jira request failed ({status})")
        detail = self._detail(e)
        raise TrackerError(f"Jira request failed ({status}): {detail}" if detail
                           else f"Jira request failed ({status})")

    # Justification: separates untrusted error-body parsing and redaction from status mapping.
    def _detail(self, e: urllib.error.HTTPError) -> str:
        try:
            payload = json.loads(e.read())
        except (ValueError, OSError, http.client.HTTPException):
            return ""
        if not isinstance(payload, dict):
            return ""
        messages = list(payload.get("errorMessages") or []) + list((payload.get("errors") or {}).values())
        return self._redact(str(messages[0]))[:_DETAIL_LIMIT] if messages else ""

    # Justification: one place that turns an undecodable 2xx body into the named error.
    @staticmethod
    def _parse(raw: bytes) -> dict | None:
        if not raw:
            return None
        try:
            return json.loads(raw)
        except ValueError as e:
            raise TrackerError("Jira returned an unreadable response") from e

    def _redact(self, text: str) -> str:
        return text.replace(self._credential, "***").replace(self._token, "***")
