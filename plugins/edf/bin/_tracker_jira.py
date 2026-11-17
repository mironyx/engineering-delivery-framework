"""Jira backend for tracker.py (ADR-0041). Operations are filled in by later E3.2 tasks.

Design reference: plugins/edf/docs/design/v3/lld-v3-e3-2-jira-backend.md §1.2
"""

from __future__ import annotations

import re
from typing import Callable

from _adf import adf_to_md, md_to_adf
from _jira_client import JiraClient
from _tracker_contract import Issue, TrackerError, issue_json, normalise_status

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
                keep: Callable[[dict], bool] = lambda _fields: True) -> list[dict]:
    found: list[dict] = []
    token: str | None = None
    for _ in range(_MAX_PAGES):
        body: dict = {"jql": jql, "fields": fields, "maxResults": min(limit, 100)}
        if token:
            body["nextPageToken"] = token
        _, data = client.request("POST", "/rest/api/3/search/jql", body=body)
        data = data or {}
        found += [i for i in data.get("issues", []) if keep(i.get("fields") or {})]
        token = data.get("nextPageToken")
        if not token or data.get("isLast") or len(found) >= limit:
            break
    return found[:limit]


# Justification: the duplicate check needs the phrase search plus the exact in-code comparison
# (JQL `=` is unsupported on summary); keeping it out of create holds create under the gate.
def _find_open_by_title(client: JiraClient, space: str, title: str) -> str | None:
    jql = f"project = {_jql_str(space)} AND statusCategory != Done AND summary ~ {_jql_phrase(title)}"
    found = _search_all(client, jql, fields=["summary"], limit=100,
                        keep=lambda f: f.get("summary") == title)
    return found[0]["key"] if found else None


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


_FIELDS = ["summary", "description", "labels", "status", "parent", "issuetype"]
_STATUS_NAMES = {"todo": "To Do", "in progress": "In Progress", "blocked": "Blocked", "done": "Done"}
_CATEGORY_STATUS = {"done": "done", "indeterminate": "in progress"}


# Justification: the one place a Jira status becomes an EDF status; view, list --status and
# the printed value must agree (V2, V3), and T7 reads _STATUS_NAMES from here.
def _status_of(fields: dict) -> str:
    current = fields.get("status") or {}
    for edf, name in _STATUS_NAMES.items():
        if current.get("name") == name:
            return edf
    return _CATEGORY_STATUS.get((current.get("statusCategory") or {}).get("key"), "todo")


# Justification: view and list build the seven-key Issue the same way (V1); complexity gate.
def _to_issue(key: str, fields: dict, children: list[str]) -> Issue:
    is_epic = (fields.get("issuetype") or {}).get("name") == "Epic"
    return Issue(ref=key, title=fields.get("summary") or "", body=adf_to_md(fields.get("description")),
                 labels=list(fields.get("labels") or []), status=_status_of(fields),
                 parent=(fields.get("parent") or {}).get("key"), children=children if is_epic else [])


def view(args, ctx) -> int:
    space = _space(ctx)
    key = _parse_ref(args.ref, space)
    client = _client(ctx)
    code, data = client.request("GET", f"/rest/api/3/issue/{key}", query={"fields": ",".join(_FIELDS)})
    if code == 404:
        raise TrackerError(f"{key} not found")
    fields = (data or {}).get("fields")
    if fields is None:
        raise TrackerError("Jira returned an unreadable response")
    children: list[str] = []
    if (fields.get("issuetype") or {}).get("name") == "Epic":
        jql = f"project = {_jql_str(space)} AND parent = {key} ORDER BY Rank ASC"
        children = [i["key"] for i in _search_all(client, jql, fields=["summary"], limit=100)]
    print(issue_json(_to_issue(key, fields, children)))
    return 0


def list_issues(args, ctx) -> int:
    wanted = normalise_status(args.status) if args.status else None
    clauses = [f"project = {_jql_str(_space(ctx))}"]
    if args.label:
        clauses.append(f"labels = {_jql_str(args.label)}")
    clauses.append("statusCategory = Done" if wanted == "done" else "statusCategory != Done")
    jql = " AND ".join(clauses) + " ORDER BY Rank ASC"
    found = _search_all(_client(ctx), jql, fields=_FIELDS, limit=100,
                        keep=lambda f: wanted is None or _status_of(f) == wanted)
    print(issue_json([_to_issue(i["key"], i.get("fields") or {}, []) for i in found]))
    return 0


# Justification: edit, comment, status and close all treat a 404 as "nothing written"; one message.
def _not_found(key: str) -> TrackerError:
    return TrackerError(f"{key} not found")


def edit(args, ctx) -> int:
    key = _parse_ref(args.ref, _space(ctx))
    client = _client(ctx)
    remove = list(args.remove_label or [])
    if remove:
        code, data = client.request("GET", f"/rest/api/3/issue/{key}", query={"fields": "labels"})
        if code == 404:
            raise _not_found(key)
        carried = set(((data or {}).get("fields") or {}).get("labels") or [])
        remove = [label for label in remove if label in carried]
    fields: dict = {}
    if args.title is not None:
        fields["summary"] = args.title
    if args.body is not None:
        fields["description"] = md_to_adf(args.body)
    ops = [{"add": label} for label in args.add_label or []] + [{"remove": label} for label in remove]
    payload: dict = {}
    if fields:
        payload["fields"] = fields
    if ops:
        payload["update"] = {"labels": ops}
    if payload:
        code, _ = client.request("PUT", f"/rest/api/3/issue/{key}", body=payload)
        if code == 404:
            raise _not_found(key)
    print(f"updated:{key}")
    return 0


def comment(args, ctx) -> int:
    key = _parse_ref(args.ref, _space(ctx))
    code, _ = _client(ctx).request("POST", f"/rest/api/3/issue/{key}/comment", body={"body": md_to_adf(args.body)})
    if code == 404:
        raise _not_found(key)
    print(f"commented:{key}")
    return 0


# Justification: status and close share the transition mechanics (LLD §1.5); named errors live here.
def _transition_to(client: JiraClient, space: str, key: str, target: str, fields: dict | None = None) -> bool:
    if fields is None:
        code, data = client.request("GET", f"/rest/api/3/issue/{key}", query={"fields": "status"})
        if code == 404:
            raise _not_found(key)
        fields = (data or {}).get("fields") or {}
    name = _STATUS_NAMES[target]
    current = (fields.get("status") or {}).get("name") or ""
    if current == name:
        return False
    _, data = client.request("GET", f"/rest/api/3/issue/{key}/transitions")
    match = next((t for t in (data or {}).get("transitions", []) if (t.get("to") or {}).get("name") == name), None)
    if match:
        code, _ = client.request("POST", f"/rest/api/3/issue/{key}/transitions", body={"transition": {"id": match["id"]}})
        if code == 404:
            raise _not_found(key)
        return True
    _, listing = client.request("GET", f"/rest/api/3/project/{space}/statuses")
    known = {s.get("name") for group in (listing or []) for s in group.get("statuses", [])}
    if name not in known:
        raise TrackerError(f'space {space} has no "{name}" status — add it to the workflow')
    raise TrackerError(f'no transition from "{current}" to "{name}"')


def status(args, ctx) -> int:
    target = normalise_status(args.status_raw)
    space = _space(ctx)
    key = _parse_ref(args.ref, space)
    _transition_to(_client(ctx), space, key, target)
    print(f"{key} → {target}")
    return 0


def close(args, ctx) -> int:
    space = _space(ctx)
    key = _parse_ref(args.ref, space)
    client = _client(ctx)
    code, data = client.request("GET", f"/rest/api/3/issue/{key}", query={"fields": "status"})
    if code == 404:
        raise _not_found(key)
    fields = (data or {}).get("fields") or {}
    if ((fields.get("status") or {}).get("statusCategory") or {}).get("key") != "done":
        _transition_to(client, space, key, "done", fields=fields)
    print(f"closed:{key}")
    return 0
