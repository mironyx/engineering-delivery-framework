"""Move Blocked issues to Todo once every issue they depend on is closed.

Usage:
  py bin/unblock-dependants.py <closed-ref>       # 12, #12 or SCRUM-12

Runs `tracker.py list --status blocked`, and for each listed issue whose `## Depends on`
section names <closed-ref>: `tracker.py view` every other ref there; when all are `done`
(the closed ref itself counts as done without a lookup), `tracker.py status <ref> todo`.

Output: one `unblocked: <ref>` line per moved item, or `unblock: none` when nothing moved.
Best-effort: a tracker failure prints one `unblock: skipped — <reason>` line. Always exit 0
(argument errors exit 2) — feature-end chains it with `|| true` after `close`.
"""

from __future__ import annotations

import json
import pathlib
import re
import subprocess
import sys

TRACKER = pathlib.Path(__file__).resolve().parent / "tracker.py"

_REF = re.compile(r"(?<![\w#])(#\d+|[A-Z][A-Z0-9]*-\d+)\b")
_ARG_REF = re.compile(r"^(#?\d+|[A-Za-z][A-Za-z0-9]*-\d+)$")
_HEADING = re.compile(r"^##\s+Depends on\s*$", re.IGNORECASE)


# Justification: CLI arg and parsed refs must compare equal (12 vs #12).
def normalise_ref(raw: str) -> str:
    """'12' / '#12' -> '#12'; a Jira key ('SCRUM-12') is returned unchanged."""
    raw = raw.strip()
    bare = raw.lstrip("#")
    return f"#{bare}" if bare.isdigit() else raw


# Justification: tested contract surface — section parsing independent of the tracker.
def depends_on_refs(body: str) -> list[str]:
    """Refs (normalised, de-duplicated, in order) under the body's `## Depends on` heading,
    up to the next `## ` heading. [] when the section is absent or names none."""
    refs: list[str] = []
    in_section = False
    for line in body.splitlines():
        if _HEADING.match(line.strip()):
            in_section = True
            continue
        if not in_section:
            continue
        if line.startswith("## "):
            break
        if not refs and line.strip().lower().startswith("none"):
            return []  # "None — parallel-safe with #9" names context, not dependencies
        for ref in _REF.findall(line):
            if ref not in refs:
                refs.append(ref)
    return refs


# Justification: the single seam to tracker.py (list, view, status) — tests replace it.
def _tracker(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run([sys.executable, str(TRACKER), *args], capture_output=True, text=True, check=False)


# Justification: one failure rule for every tracker call — stderr's first line or the exit code.
def _reason(result: subprocess.CompletedProcess[str]) -> str:
    lines = (result.stderr or "").strip().splitlines()
    return lines[0] if lines else f"exit {result.returncode}"


# Justification: one view-and-parse per dependency, so a failed lookup is told apart from "not done".
def _is_done(ref: str) -> bool | None:
    """True/False from `view`'s status; None when the lookup fails."""
    result = _tracker("view", ref)
    if result.returncode != 0:
        return None
    try:
        return json.loads(result.stdout).get("status") == "done"
    except (json.JSONDecodeError, AttributeError):
        return None


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    if len(args) != 1 or not _ARG_REF.match(args[0].strip()):
        print("Usage: unblock-dependants.py <closed-ref>   (12, #12 or SCRUM-12)", file=sys.stderr)
        return 2
    closed = normalise_ref(args[0])

    listed = _tracker("list", "--status", "blocked")
    if listed.returncode != 0:
        print(f"unblock: skipped — tracker list failed: {_reason(listed)}")
        return 0
    try:
        blocked = json.loads(listed.stdout)
    except json.JSONDecodeError:
        print("unblock: skipped — tracker list returned invalid JSON")
        return 0

    printed = False
    for issue in blocked:
        # Keep refs of the closed ref's kind only: a key-shaped token such as "UTF-8" in a
        # GitHub body would otherwise fail its lookup and keep the dependant blocked forever.
        deps = [d for d in depends_on_refs(issue.get("body") or "")
                if d.startswith("#") == closed.startswith("#")]
        if closed not in deps:
            continue
        states = {dep: _is_done(dep) for dep in deps if dep != closed}
        unknown = [dep for dep, done in states.items() if done is None]
        if unknown:
            print(f"unblock: skipped {issue['ref']} — could not view {','.join(unknown)}")
            printed = True
            continue
        if not all(states.values()):
            continue
        result = _tracker("status", issue["ref"], "todo")
        if result.returncode != 0:
            print(f"unblock: skipped {issue['ref']} — {_reason(result)}")
        else:
            print(f"unblocked: {issue['ref']}")
        printed = True
    if not printed:
        print("unblock: none")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
