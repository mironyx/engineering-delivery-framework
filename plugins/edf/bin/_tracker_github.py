"""GitHub backend for tracker.py (ADR-0041).

Stub until E3.1 T2–T4 port the bash scripts: every operation raises TrackerError.

Design reference: plugins/edf/docs/design/v3/lld-v3-e3-1-tracker-script.md §1.2–§1.4
"""

from __future__ import annotations

import argparse

from _tracker_contract import TrackerError

# TODO(#119, #120, #121): replace these stubs with the GitHub implementation.
_NOT_IMPLEMENTED = "not implemented"


def create(args: argparse.Namespace, ctx: object) -> int:
    raise TrackerError(_NOT_IMPLEMENTED)


def view(args: argparse.Namespace, ctx: object) -> int:
    raise TrackerError(_NOT_IMPLEMENTED)


def list_issues(args: argparse.Namespace, ctx: object) -> int:
    raise TrackerError(_NOT_IMPLEMENTED)


def edit(args: argparse.Namespace, ctx: object) -> int:
    raise TrackerError(_NOT_IMPLEMENTED)


def comment(args: argparse.Namespace, ctx: object) -> int:
    raise TrackerError(_NOT_IMPLEMENTED)


def status(args: argparse.Namespace, ctx: object) -> int:
    raise TrackerError(_NOT_IMPLEMENTED)


def close(args: argparse.Namespace, ctx: object) -> int:
    raise TrackerError(_NOT_IMPLEMENTED)
