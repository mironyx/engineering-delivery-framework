"""Print the session's feature title from the Claude Code session JSONL.

When CLAUDE_CODE_SESSION_ID is set, the JSONL path is constructed directly
from the session UUID, skipping the old /proc and mtime-based search.
Falls back to the old search methods when the env var is absent.

Usage:
    python get-session-id.py
    .claude/hooks/run-python.sh bin/get-session-id.py
"""

import json
import os
import pathlib
import sys


def derive_project_key() -> str:
    """Convert git root path to a Claude project key (same derivation as tag-session.py)."""
    import subprocess
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--git-common-dir"],
            capture_output=True, text=True, check=True,
        )
        root = pathlib.Path(result.stdout.strip()).parent.resolve()
    except (subprocess.CalledProcessError, FileNotFoundError):
        root = pathlib.Path.cwd()
    path_str = str(root).lower()
    path_str = path_str.replace(":\\", "--")
    return path_str.replace("\\", "-").replace("/", "-").replace(":", "")


def find_jsonl_via_proc(claude_dir: pathlib.Path) -> pathlib.Path | None:
    try:
        ppid = next(
            line.split()[1]
            for line in pathlib.Path("/proc/self/status").read_text().splitlines()
            if line.startswith("PPid:")
        )
        for fd in pathlib.Path(f"/proc/{ppid}/fd").iterdir():
            try:
                target = fd.resolve()
                if target.parent == claude_dir and target.suffix == ".jsonl":
                    return target
            except OSError:
                continue
    except Exception:
        pass
    return None


def read_title(jsonl: pathlib.Path) -> str | None:
    for line in reversed(jsonl.read_text(encoding="utf-8").splitlines()):
        try:
            obj = json.loads(line)
            if obj.get("type") == "custom-title":
                return obj["customTitle"]
        except (json.JSONDecodeError, KeyError):
            continue
    return None


def _compare(old_uuid: str, new_uuid: str) -> None:
    if old_uuid and new_uuid and old_uuid != new_uuid:
        print(
            f"[get-session-id] CLAUDE_CODE_SESSION_ID={new_uuid} but old method found {old_uuid}",
            file=sys.stderr,
        )


claude_dir = pathlib.Path.home() / ".claude" / "projects" / derive_project_key()
env_session_id = os.environ.get("CLAUDE_CODE_SESSION_ID")

# New path: construct JSONL path from CLAUDE_CODE_SESSION_ID
if env_session_id:
    jsonl = claude_dir / f"{env_session_id}.jsonl"
    if jsonl.exists():
        title = read_title(jsonl)
        if title:
            # Compare old method (best-effort, for validation)
            old = find_jsonl_via_proc(claude_dir)
            if old:
                _compare(old.stem, env_session_id)
            else:
                newest = max(claude_dir.glob("*.jsonl"), key=os.path.getmtime, default=None)
                if newest:
                    _compare(newest.stem, env_session_id)
            print(title)
            sys.exit(0)

# Fallback: old method
proc_jsonl = find_jsonl_via_proc(claude_dir)
if proc_jsonl:
    title = read_title(proc_jsonl)
    if title:
        print(title)
        sys.exit(0)

for jsonl in sorted(claude_dir.glob("*.jsonl"), key=os.path.getmtime, reverse=True):
    title = read_title(jsonl)
    if title:
        print(title)
        sys.exit(0)

print("pr-review")
