"""Shared contract for the tracker script and its backends (ADR-0041).

Every backend raises TrackerError; tracker.main turns it into one ``Error: …``
line on stderr and exit 1. The status vocabulary and the Issue JSON shape are
the same for every tracker.

Design reference: plugins/edf/docs/design/v3/lld-v3-e3-1-tracker-script.md §1.1
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass


STATUSES: tuple[str, ...] = ("todo", "in progress", "blocked", "done")
STATUS_ERROR = "unknown status '{raw}'. Use: todo | blocked | \"in progress\" | done"


class TrackerError(Exception):
    """Message without the 'Error: ' prefix. tracker.main prints it to stderr, exits 1."""


def normalise_status(raw: str) -> str:
    """Lower-case and validate; raises TrackerError(STATUS_ERROR) on anything else."""
    status = raw.lower()
    if status not in STATUSES:
        raise TrackerError(STATUS_ERROR.format(raw=raw))
    return status


@dataclass(frozen=True)
class Issue:
    ref: str
    title: str
    body: str
    labels: list[str]
    status: str
    parent: str | None
    children: list[str]


def issue_json(issue: Issue | list[Issue]) -> str:
    """json.dumps(asdict(...), indent=2, ensure_ascii=False), key order as declared."""
    data = [asdict(i) for i in issue] if isinstance(issue, list) else asdict(issue)
    return json.dumps(data, indent=2, ensure_ascii=False)
