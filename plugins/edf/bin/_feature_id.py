"""Feature identity resolver (ADR-0041, LLD v3-e3-3 §1.1).

The only place `FEATURE_ID` and the PR-body issue-reference lines are derived.
Asks `tracker.active_backend` which tracker is active; never reads Jira settings.
"""

from __future__ import annotations

import pathlib
import re
import subprocess
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

import _edf_env  # noqa: E402
import tracker  # noqa: E402
from _tracker_contract import TrackerError  # noqa: E402

_ISSUE_KEY = re.compile(r"([A-Za-z][A-Za-z0-9_]*)-([0-9]+)")
_GITHUB_NUMBER = re.compile(r"#?([0-9]+)")


def main_checkout_root() -> pathlib.Path:
    """Main checkout root (parent of the common .git dir) — shared by linked worktrees."""
    common = subprocess.run(["git", "rev-parse", "--git-common-dir"],
                            capture_output=True, text=True, check=True).stdout.strip()
    path = pathlib.Path(common)
    if not path.is_absolute():
        path = pathlib.Path.cwd() / path
    return path.resolve().parent


def derive_feature_prefix(root: pathlib.Path) -> str:
    """Derive a feature-id prefix.

    Precedence: $EDF_FEATURE_PREFIX env var → .env in repo root → derivation.
    Derivation: "engineering-delivery-framework" -> "EDF", "myproject" -> "MYPROJECT".
    """
    prefix = _edf_env.resolve("EDF_FEATURE_PREFIX", root)
    if prefix:
        return prefix
    name = root.name
    parts = [p for p in name.replace("_", "-").split("-") if p]
    if len(parts) >= 2:
        return "".join(p[0].upper() for p in parts)
    return name.upper() or "FEAT"


def _jira_key(ref: str) -> str:
    match = _ISSUE_KEY.fullmatch(ref)
    if not match:
        raise TrackerError(f"invalid issue reference '{ref}'")
    return f"{match.group(1).upper()}-{match.group(2)}"


def _github_number(ref: str) -> str:
    match = _GITHUB_NUMBER.fullmatch(ref)
    if not match:
        raise TrackerError(f"invalid issue reference '{ref}'")
    return match.group(1)


def resolve_feature_id(ref: str, root: pathlib.Path) -> str:
    """Jira: the upper-cased key. GitHub: `<prefix>-<n>` from '#87' or '87'.

    Raises TrackerError on a ref of the wrong shape for the active backend.
    """
    if tracker.active_backend(root) == "jira":
        return _jira_key(ref)
    return f"{derive_feature_prefix(root)}-{_github_number(ref)}"


def issue_reference_lines(refs: list[str], root: pathlib.Path) -> str:
    """Jira: 'Jira: KEY' per ref. GitHub: 'Closes #N' per ref."""
    if tracker.active_backend(root) == "jira":
        return "\n".join(f"Jira: {_jira_key(r)}" for r in refs)
    return "\n".join(f"Closes #{_github_number(r)}" for r in refs)
