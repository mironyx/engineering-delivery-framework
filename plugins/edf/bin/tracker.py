#!/usr/bin/env python3
"""Tracker-agnostic issue CLI (ADR-0041).

Design reference: plugins/edf/docs/design/v3/lld-v3-e3-1-tracker-script.md §1.1

Parses every operation, resolves configuration (OS env, then the main
checkout's .env), selects the backend and dispatches. Never calls an API itself.

Grammar:
  tracker.py tracker
  tracker.py create  --title T --body MD [--labels a,b] [--type task|epic] [--parent REF]
                     [--add-to-board] [--board-status S] [--dry-run]
  tracker.py view    REF
  tracker.py list    [--status S] [--label L]
  tracker.py edit    REF [--title T] [--body MD] [--add-label L]... [--remove-label L]...
  tracker.py comment REF --body MD
  tracker.py status  REF S [--add-to-board]
  tracker.py close   REF
"""

from __future__ import annotations

import argparse
import importlib
import pathlib
import subprocess
import sys
from dataclasses import dataclass, field
from types import ModuleType
from typing import Literal, NoReturn

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

import _edf_env  # noqa: E402
from _tracker_contract import TrackerError  # noqa: E402

_OPS = ("tracker", "create", "view", "list", "edit", "comment", "status", "close")
_OP_FUNCS = {"create": "create", "view": "view", "list": "list_issues", "edit": "edit",
             "comment": "comment", "status": "status", "close": "close"}
_BACKENDS = {"github": "_tracker_github"}  # E3.2 adds "jira": "_tracker_jira"
_JIRA_COMPANIONS = ("JIRA_EMAIL", "JIRA_API_TOKEN", "JIRA_SPACE")
_CREATE_VALUE_FLAGS = {"--title": "title", "--body": "body", "--labels": "labels", "--type": "type",
                       "--parent": "parent", "--board-status": "board_status"}
_CREATE_BOOL_FLAGS = {"--add-to-board": "add_to_board", "--dry-run": "dry_run"}
_EDIT_CHANGE_FLAGS = ("title", "body", "add_label", "remove_label")


@dataclass(frozen=True)
class JiraConfig:
    host: str
    email: str
    token: str = field(repr=False)
    space: str


@dataclass(frozen=True)
class TrackerContext:
    env_root: pathlib.Path
    repo_root: pathlib.Path | None
    tracker: Literal["github", "jira"]
    jira: JiraConfig | None


# ---------------------------------------------------------------- grammar


class _ArgumentParser(argparse.ArgumentParser):
    """argparse that reports through the Error contract instead of usage + exit 2."""

    def error(self, message: str) -> NoReturn:
        raise TrackerError(message)


# Justification: one builder for the argparse-backed ops (view, list, edit, comment and close)
# keeps their shared settings (no abbreviations, Error-contract errors) in one place.
def _argparser(op: str) -> _ArgumentParser:
    parser = _ArgumentParser(prog=f"tracker.py {op}", add_help=False, allow_abbrev=False)
    if op != "list":
        parser.add_argument("ref")
    if op == "list":
        parser.add_argument("--status")
        parser.add_argument("--label")
    elif op == "edit":
        parser.add_argument("--title")
        parser.add_argument("--body")
        parser.add_argument("--add-label", action="append", default=[])
        parser.add_argument("--remove-label", action="append", default=[])
    elif op == "comment":
        parser.add_argument("--body", required=True)
    return parser


# Justification: create's output is parity-bound to gh-create-issue.sh's while/case loop, which
# argparse cannot reproduce (abbreviations, dash-leading values, message wording) — LLD §1.1.
def _parse_create(rest: list[str]) -> argparse.Namespace:
    args = argparse.Namespace(**{dest: None for dest in _CREATE_VALUE_FLAGS.values()},
                              **{dest: False for dest in _CREATE_BOOL_FLAGS.values()})
    tokens = iter(rest)
    for arg in tokens:
        if arg in _CREATE_BOOL_FLAGS:
            setattr(args, _CREATE_BOOL_FLAGS[arg], True)
        elif arg in _CREATE_VALUE_FLAGS:
            value = next(tokens, None)
            if value is None:
                raise TrackerError(f"{arg} needs a value")
            setattr(args, _CREATE_VALUE_FLAGS[arg], value)
        else:
            raise TrackerError(f"unknown option '{arg}'")
    if not args.title:  # empty counts as missing, as bash's [[ -z ]] did
        raise TrackerError("--title is required")
    if not args.body:
        raise TrackerError("--body is required")
    return args


# Justification: status keeps S raw (one argv element, e.g. "in progress"); the backend
# normalises it after its own config checks, for gh-project-status.sh parity — LLD §1.1.
def _parse_status(rest: list[str]) -> argparse.Namespace:
    add_to_board = "--add-to-board" in rest
    positional = [a for a in rest if a != "--add-to-board"]
    if len(positional) != 2:
        raise TrackerError("status needs REF and STATUS")
    return argparse.Namespace(ref=positional[0], status_raw=positional[1], add_to_board=add_to_board)


def _parse(argv: list[str]) -> argparse.Namespace:
    op, rest = (argv[0], argv[1:]) if argv else ("", [])
    if op not in _OPS:
        raise TrackerError(f"unknown operation '{op}'. Use: {' | '.join(_OPS)}")
    if op == "tracker":
        if rest:
            raise TrackerError(f"unexpected argument '{rest[0]}'")
        args = argparse.Namespace()
    elif op == "create":
        args = _parse_create(rest)
    elif op == "status":
        args = _parse_status(rest)
    else:
        args = _argparser(op).parse_args(rest)
        if op == "edit" and not any(getattr(args, f) for f in _EDIT_CHANGE_FLAGS):
            raise TrackerError("edit needs one of --title, --body, --add-label, --remove-label")
    args.op = op
    return args


# ---------------------------------------------------------------- configuration


# Justification: reused by _env_root and _repo_root; both need "stdout or None outside a repo".
def _git(*args: str) -> str | None:
    try:
        result = subprocess.run(["git", "rev-parse", *args], capture_output=True, text=True)
    except OSError as e:  # git missing: fail loudly through the Error contract (I5)
        raise TrackerError("git is not installed or not on PATH") from e
    return result.stdout.strip() if result.returncode == 0 else None


def _env_root() -> pathlib.Path:
    """Main checkout root (parent of the common .git dir), so linked worktrees share its .env."""
    common_dir = _git("--git-common-dir")
    if common_dir is None:
        return pathlib.Path.cwd()
    return (pathlib.Path.cwd() / common_dir).resolve().parent


def _repo_root() -> pathlib.Path | None:
    toplevel = _git("--show-toplevel")
    return pathlib.Path(toplevel) if toplevel else None


def _resolve_context(env_root: pathlib.Path, repo_root: pathlib.Path | None) -> TrackerContext:
    host = _edf_env.resolve("JIRA_HOST", env_root)
    if host is None:
        return TrackerContext(env_root, repo_root, "github", None)
    values = {}
    for var in _JIRA_COMPANIONS:
        values[var] = _edf_env.resolve(var, env_root)
        if values[var] is None:
            raise TrackerError(f"JIRA_HOST is set but {var} is missing")
    if not host.startswith("https://"):
        raise TrackerError("JIRA_HOST must use https://")
    jira = JiraConfig(host, values["JIRA_EMAIL"], values["JIRA_API_TOKEN"], values["JIRA_SPACE"])
    return TrackerContext(env_root, repo_root, "jira", jira)


def _load_backend(name: str) -> ModuleType:
    if name not in _BACKENDS:
        raise TrackerError("Jira backend is not available in this EDF version")
    return importlib.import_module(_BACKENDS[name])


# ---------------------------------------------------------------- entry point


def main(argv: list[str] | None = None) -> int:
    try:
        args = _parse(sys.argv[1:] if argv is None else argv)
        ctx = _resolve_context(_env_root(), _repo_root())
        if args.op == "tracker":
            print(ctx.tracker)
            return 0
        backend = _load_backend(ctx.tracker)  # only after validation (I4)
        return getattr(backend, _OP_FUNCS[args.op])(args, ctx)
    except TrackerError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
