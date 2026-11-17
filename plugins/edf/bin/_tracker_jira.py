"""Jira backend for tracker.py (ADR-0041). Operations are filled in by later E3.2 tasks.

Design reference: plugins/edf/docs/design/v3/lld-v3-e3-2-jira-backend.md §1.2
"""

from __future__ import annotations

import re
from typing import Callable

from _adf import md_to_adf
from _jira_client import JiraClient
from _tracker_contract import TrackerError

_SPACE_RE = re.compile(r"^[A-Za-z][A-Za-z0-9_]*$")


# Justification: one client per process call; every operation (T3-T5) builds it the same way.
def _client(ctx) -> JiraClient:
    return JiraClient(ctx.jira)


# Justification: JIRA_SPACE goes into JQL and paths, so it is validated once here (T3-T5 reuse it).
def _space(ctx) -> str:
    if not _SPACE_RE.match(ctx.jira.space):
        raise TrackerError("JIRA_SPACE is not a valid project key")
    return ctx.jira.space


# Justification: one ref normaliser for view/edit/comment/status/close (T4-T5).
def _parse_ref(ref: str, space: str) -> str:
    match = re.fullmatch(r"([A-Za-z][A-Za-z0-9_]*)-([0-9]+)", ref)
    if not match or match.group(1).upper() != space.upper():
        raise TrackerError(f"invalid issue reference '{ref}'")
    return f"{space.upper()}-{match.group(2)}"


_MAX_PAGES = 20  # guard against a repeating nextPageToken (LLD §1.4)
_TYPES = {"task": "Task", "epic": "Epic"}
_TEXT_SEARCH_SPECIALS = re.compile(r'([+\-&|!(){}\[\]^~*?\\:"])')


# Justification: JQL string escaping is shared by every query this backend builds (create, list).
def _jql_str(value: str) -> str:
    escaped = (value.replace("\\", "\\\\").replace('"', '\\"')
               .replace("\n", "\\n").replace("\r", "\\r").replace("\t", "\\t"))
    return f'"{escaped}"'


# Justification: `summary ~` is text search with its own special characters, escaped before the
# JQL string escape; kept apart from _jql_str so each layer is tested on its own (C3).
def _jql_phrase(value: str) -> str:
    return _jql_str('"' + _TEXT_SEARCH_SPECIALS.sub(r"\\\1", value) + '"')


# Justification: pagination loop shared by the duplicate check and list (T6); complexity gate.
def _search_all(client: JiraClient, jql: str, *, fields: list[str], limit: int,
                keep: Callable[[dict], bool] = lambda _fields: True) -> list[str]:
    keys: list[str] = []
    token: str | None = None
    for _ in range(_MAX_PAGES):
        body: dict = {"jql": jql, "fields": fields, "maxResults": min(limit, 100)}
        if token:
            body["nextPageToken"] = token
        _, data = client.request("POST", "/rest/api/3/search/jql", body=body)
        data = data or {}
        keys += [i["key"] for i in data.get("issues", []) if keep(i.get("fields") or {})]
        token = data.get("nextPageToken")
        if not token or data.get("isLast") or len(keys) >= limit:
            break
    return keys[:limit]


# Justification: the duplicate check needs the phrase search plus the exact in-code comparison
# (JQL `=` is unsupported on summary); keeping it out of create holds create under the gate.
def _find_open_by_title(client: JiraClient, space: str, title: str) -> str | None:
    jql = f"project = {_jql_str(space)} AND statusCategory != Done AND summary ~ {_jql_phrase(title)}"
    found = _search_all(client, jql, fields=["summary"], limit=100,
                        keep=lambda f: f.get("summary") == title)
    return found[0] if found else None


# Justification: dry-run block kept out of create's control flow; complexity gate.
def _print_dry_run(args, labels: list[str], parent_key: str | None) -> None:
    print("dry-run: would create issue")
    print(f"  title:  {args.title}")
    print(f"  labels: {','.join(labels) or '<none>'}")
    if parent_key:
        print(f"  parent: {parent_key}")
    print("  body:")
    for line in args.body.split("\n"):
        print(f"    {line}")


def create(args, ctx) -> int:
    if args.type is not None and args.type not in _TYPES:
        raise TrackerError(f"unknown type '{args.type}'. Use: task | epic")
    issue_type = _TYPES[args.type or "task"]
    labels = [name.strip() for name in (args.labels or "").split(",") if name.strip()]
    space = _space(ctx)
    client = _client(ctx)
    parent_key = None
    if args.parent is not None:
        parent_key = _parse_ref(args.parent, space)
        status, _ = client.request("GET", f"/rest/api/3/issue/{parent_key}", query={"fields": "summary"})
        if status == 404:
            raise TrackerError(f"parent {parent_key} not found")
    existing = _find_open_by_title(client, space, args.title)
    if existing:
        print(f"exists:{existing}")
        return 0
    if args.dry_run:
        _print_dry_run(args, labels, parent_key)
        return 0
    fields: dict = {"project": {"key": space}, "issuetype": {"name": issue_type}, "summary": args.title,
                    "description": md_to_adf(args.body), "labels": labels}
    if parent_key:
        fields["parent"] = {"key": parent_key}
    _, data = client.request("POST", "/rest/api/3/issue", body={"fields": fields})
    key = (data or {}).get("key")
    if not key:
        raise TrackerError("Jira returned an unreadable response")
    print(f"created:{key}")
    return 0


def view(args, ctx) -> int:
    raise TrackerError("not implemented")


def list_issues(args, ctx) -> int:
    raise TrackerError("not implemented")


def edit(args, ctx) -> int:
    raise TrackerError("not implemented")


def comment(args, ctx) -> int:
    raise TrackerError("not implemented")


def status(args, ctx) -> int:
    raise TrackerError("not implemented")


def close(args, ctx) -> int:
    raise TrackerError("not implemented")
