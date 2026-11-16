"""Jira backend for tracker.py (ADR-0041). Operations are filled in by later E3.2 tasks.

Design reference: plugins/edf/docs/design/v3/lld-v3-e3-2-jira-backend.md §1.2
"""

from __future__ import annotations

import re

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


def create(args, ctx) -> int:
    raise TrackerError("not implemented")


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
