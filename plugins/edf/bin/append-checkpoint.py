"""Append a cost checkpoint row to a session log immediately.

Captures the current UTC timestamp and cumulative cost/tokens from Prometheus
at the moment it is called, then writes a complete table row. No placeholders —
the row is fully materialised before the agent sees it, so backfilling is
impossible without detection.

Usage:
  py bin/append-checkpoint.py \\
    --session-log docs/sessions/2026-07/2026-07-31-session-1-foo-FCS-1016.md \\
    --step 5 \\
    --note "green on attempt 2" \\
    --issue 1016

The session log must already exist with a ## Cost checkpoints table header.
Prometheus cost/token values are best-effort — "unavailable" if unreachable.
"""

import argparse
import json
import os
import pathlib
import sys
import urllib.parse
import urllib.request
from datetime import datetime, timezone

import _edf_env

_PROM_HOST = os.environ.get("WINDOWS_IP", "localhost")
_PROM_PORT = os.environ.get("PROM_PORT", "9090")
PROM = f"http://{_PROM_HOST}:{_PROM_PORT}/api/v1/query"


def git_root() -> pathlib.Path:
    import subprocess
    common = subprocess.run(
        ["git", "rev-parse", "--git-common-dir"],
        capture_output=True, text=True, check=True,
    ).stdout.strip()
    p = pathlib.Path(common)
    if not p.is_absolute():
        p = pathlib.Path.cwd() / p
    return p.parent


def derive_feature_prefix(root: pathlib.Path) -> str:
    prefix = _edf_env.resolve("EDF_FEATURE_PREFIX", root)
    if prefix:
        return prefix
    name = root.name
    parts = [p for p in name.replace("_", "-").split("-") if p]
    if len(parts) >= 2:
        return "".join(p[0].upper() for p in parts)
    return name.upper() or "FEAT"


def _extract_session_id(line: str, feature_id: str) -> str | None:
    if not (line.startswith("claude_session_feature{") and f'feature_id="{feature_id}"' in line):
        return None
    for part in line.split(","):
        if "session_id=" in part:
            return part.split('"')[1]
    return None


def read_session_ids(feature_id: str, prom_dir: pathlib.Path) -> list[str]:
    """Look up session IDs for a feature, querying Prometheus first, file as fallback."""
    # Try Prometheus first
    try:
        q = f'claude_session_feature{{feature_id="{feature_id}"}}'
        url = PROM + "?" + urllib.parse.urlencode({"query": q})
        rows = (
            json.loads(urllib.request.urlopen(url, timeout=3).read())
            .get("data", {})
            .get("result", [])
        )
        ids = [r["metric"]["session_id"] for r in rows if "session_id" in r.get("metric", {})]
        if ids:
            return ids
    except Exception:
        pass

    # Fallback to local .prom file
    prom_file = prom_dir / "session_feature.prom"
    if not prom_file.exists():
        return []
    lines = prom_file.read_text(encoding="utf-8").splitlines()
    return [sid for line in lines if (sid := _extract_session_id(line, feature_id))]


def query_prom(promql: str) -> float | None:
    try:
        url = PROM + "?" + urllib.parse.urlencode({"query": promql})
        rows = (
            json.loads(urllib.request.urlopen(url, timeout=3).read())
            .get("data", {})
            .get("result", [])
        )
        return sum(float(r["value"][1]) for r in rows) if rows else 0.0
    except Exception:
        return None


def query_cost(feature_id: str, prom_dir: pathlib.Path) -> str:
    """Return 'cost | tokens' string for the checkpoint row, or 'unavailable | unavailable'."""
    session_ids = read_session_ids(feature_id, prom_dir)
    if not session_ids:
        return "unavailable | unavailable"

    f = f'feature_id="{feature_id}"'

    cost_q = (
        f'sum by (feature_id) ('
        f'  claude_session_feature{{{f}}}'
        f'  * on(session_id) group_left()'
        f'  sum by (session_id) (claude_code_cost_usage_USD_total)'
        f')'
    )
    cost = query_prom(cost_q)
    if cost is None:
        return "unavailable | unavailable"

    def tok(typ: str) -> float:
        q = (
            f'sum by (feature_id) ('
            f'  claude_session_feature{{{f}}}'
            f'  * on(session_id) group_left()'
            f'  sum by (session_id) (claude_code_token_usage_tokens_total{{type="{typ}"}})'
            f')'
        )
        return query_prom(q) or 0.0

    inp = tok("input")
    out = tok("output")
    return f"${cost:.2f} | {int(inp):,} in / {int(out):,} out"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--session-log", required=True, help="Path to the session log .md file")
    parser.add_argument("--step", required=True, help="Step label (e.g. '5', '6b', '4bF')")
    parser.add_argument("--note", required=True, help="Checkpoint note text")
    parser.add_argument("--issue", type=int, help="Issue number for Prometheus cost lookup")
    args = parser.parse_args()

    session_log = pathlib.Path(args.session_log)
    if not session_log.exists():
        print(f"Session log not found: {session_log}", file=sys.stderr)
        sys.exit(1)

    # Current UTC timestamp — captured NOW, not by the caller
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    # Query cost if issue provided
    if args.issue is not None:
        root = git_root()
        prefix = derive_feature_prefix(root)
        feature_id = f"{prefix}-{args.issue}"
        prom_dir = _edf_env.prom_dir(root)
        cost_data = query_cost(feature_id, prom_dir)
    else:
        cost_data = "unavailable | unavailable"

    # Insert the row into the Cost checkpoints table. The log may have sections
    # after the table (e.g. "## Cost retrospective"), so appending to EOF would
    # land the row under the wrong heading.
    row = f"| {args.step} | {timestamp} | {cost_data} | {args.note} |"
    lines = session_log.read_text(encoding="utf-8").splitlines()
    insert_at = len(lines)
    found = False
    for i, line in enumerate(lines):
        if line.strip().startswith("## Cost checkpoints"):
            found = True
            insert_at = len(lines)
            for j in range(i + 1, len(lines)):
                if lines[j].strip().startswith("## "):
                    insert_at = j
                    break
                if lines[j].strip():
                    insert_at = j + 1
            break
    if not found:
        print("Warning: no '## Cost checkpoints' heading found — appending to end", file=sys.stderr)
    lines.insert(insert_at, row)
    session_log.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(f"Checkpoint appended: step={args.step} timestamp={timestamp}")


if __name__ == "__main__":
    main()
