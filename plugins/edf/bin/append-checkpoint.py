"""Append a cost checkpoint row to a session log immediately.

Captures the current UTC timestamp and cumulative cost/tokens from Prometheus
at the moment it is called, then writes a complete table row. No placeholders —
the row is fully materialised before the agent sees it, so backfilling is
impossible without detection.

Usage:
  py bin/append-checkpoint.py --issue 1016 --step 5 --note "green on attempt 2"

--session-log is optional: without it the log is found from the issue, as the
newest docs/sessions/**/*-<FEATURE_ID>.md. The session log must already exist
with a ## Cost checkpoints table header.

--step must be one of STEPS below; a mistyped label would silently break the
cost-by-step analysis. The script appends the model split itself, so a
"[models: ...]" tag in --note is stripped. Blank lines inside the table (which
break Markdown rendering) are removed on every write.
Prometheus cost/token values are best-effort — "unavailable" if unreachable.

If EDF_GRAFANA_URL and EDF_GRAFANA_TOKEN (a service-account token with Editor
role) are set (env or .env), each checkpoint is also posted as a Grafana
annotation — a vertical line labelled with the step — tagged `edf-step` and
the feature ID.
"""

import argparse
import json
import os
import pathlib
import re
import sys
import urllib.parse
import urllib.request
from datetime import datetime, timezone

import _edf_env

_PROM_HOST = os.environ.get("WINDOWS_IP", "localhost")
_PROM_PORT = os.environ.get("PROM_PORT", "9090")
PROM = f"http://{_PROM_HOST}:{_PROM_PORT}/api/v1/query"


STEPS = ("3c", "4bF", "4dF", "5", "6", "6b", "7", "8", "9", "9b", "10")


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


def format_models(cost_by_model: dict[str, float]) -> str:
    if not cost_by_model:
        return ""
    ranked = sorted(cost_by_model.items(), key=lambda kv: -kv[1])
    return "models: " + ", ".join(f"{m} ${c:.2f}" for m, c in ranked)


def query_models(feature_id: str) -> str:
    """Return the feature's cumulative cost split by model, or "" if unavailable."""
    q = (
        f'sum by (model) ('
        f'  claude_code_cost_usage_USD_total'
        f'  * on(session_id) group_left()'
        f'  claude_session_feature{{feature_id="{feature_id}"}}'
        f')'
    )
    try:
        url = PROM + "?" + urllib.parse.urlencode({"query": q})
        rows = (
            json.loads(urllib.request.urlopen(url, timeout=3).read())
            .get("data", {})
            .get("result", [])
        )
    except Exception:
        return ""
    return format_models({r["metric"].get("model", "unknown"): float(r["value"][1]) for r in rows})


def build_annotation(step: str, note: str, feature_id: str | None, time_ms: int) -> dict:
    """Grafana annotation payload: one vertical line per step, filterable by tag."""
    tags = ["edf-step", f"step:{step}"] + ([feature_id] if feature_id else [])
    prefix = f"{feature_id} " if feature_id else ""
    return {"time": time_ms, "tags": tags, "text": f"{prefix}Step {step}: {note}"}


def post_annotation(grafana_url: str, token: str, payload: dict) -> None:
    """Best-effort POST to Grafana — a failure never blocks the checkpoint row."""
    req = urllib.request.Request(
        grafana_url.rstrip("/") + "/api/annotations",
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {token}"},
        method="POST",
    )
    try:
        urllib.request.urlopen(req, timeout=3)
    except Exception as e:
        print(f"Grafana annotation skipped: {e}", file=sys.stderr)


def find_session_log(root: pathlib.Path, feature_id: str) -> pathlib.Path | None:
    logs = list((root / "docs" / "sessions").glob(f"**/*-{feature_id}.md"))
    return max(logs, key=lambda p: p.stat().st_mtime) if logs else None


def clean_note(note: str) -> str:
    return re.sub(r"\s*\[models:[^\]]*\]", "", note).strip()


def insert_row(lines: list[str], row: str) -> list[str]:
    """Insert row at the end of the Cost checkpoints table; drop blank lines inside it."""
    start = next((i for i, ln in enumerate(lines) if ln.strip().startswith("## Cost checkpoints")), None)
    if start is None:
        print("Warning: no '## Cost checkpoints' heading found — appending to end", file=sys.stderr)
        return lines + [row]
    end = next((j for j in range(start + 1, len(lines)) if lines[j].strip().startswith("## ")), len(lines))
    table = [ln for ln in lines[start + 1:end] if ln.strip()]
    trailing = [""] if end < len(lines) else []
    return lines[:start + 1] + table + [row] + trailing + lines[end:]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--session-log", help="Path to the session log .md file (default: found from --issue)")
    parser.add_argument("--step", required=True, choices=STEPS, help="Step label")
    parser.add_argument("--note", required=True, help="Checkpoint note text")
    parser.add_argument("--issue", type=int, help="Issue number for Prometheus cost lookup")
    args = parser.parse_args()

    root = git_root()
    if args.session_log:
        session_log = pathlib.Path(args.session_log)
    elif args.issue is not None:
        # Search the current checkout, not git_root(): in a /feature-team worktree
        # the log lives in the worktree, while git_root() is the main repo.
        import subprocess
        toplevel = subprocess.run(["git", "rev-parse", "--show-toplevel"],
                                  capture_output=True, text=True).stdout.strip()
        session_log = find_session_log(pathlib.Path(toplevel or "."), f"{derive_feature_prefix(root)}-{args.issue}")
    else:
        print("Pass --session-log or --issue", file=sys.stderr)
        sys.exit(1)
    if session_log is None or not session_log.exists():
        print(f"Session log not found: {session_log or 'no docs/sessions/**/*-<FEATURE_ID>.md for this issue'}",
              file=sys.stderr)
        sys.exit(1)

    # Current UTC timestamp — captured NOW, not by the caller
    now = datetime.now(timezone.utc)
    timestamp = now.strftime("%Y-%m-%dT%H:%M:%SZ")
    feature_id = None

    # Query cost if issue provided
    if args.issue is not None:
        prefix = derive_feature_prefix(root)
        feature_id = f"{prefix}-{args.issue}"
        prom_dir = _edf_env.prom_dir(root)
        cost_data = query_cost(feature_id, prom_dir)
        models = query_models(feature_id)
    else:
        cost_data = "unavailable | unavailable"
        models = ""

    # Insert the row into the Cost checkpoints table. The log may have sections
    # after the table (e.g. "## Cost retrospective"), so appending to EOF would
    # land the row under the wrong heading.
    note = clean_note(args.note)
    note = f"{note} [{models}]" if models else note
    row = f"| {args.step} | {timestamp} | {cost_data} | {note} |"
    lines = insert_row(session_log.read_text(encoding="utf-8").splitlines(), row)
    session_log.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(f"Checkpoint appended: step={args.step} timestamp={timestamp}")

    # Opt-in: mark the step boundary as a vertical line on Grafana graphs.
    grafana_url = _edf_env.resolve("EDF_GRAFANA_URL", root)
    grafana_token = _edf_env.resolve("EDF_GRAFANA_TOKEN", root)
    if grafana_url and grafana_token:
        payload = build_annotation(args.step, clean_note(args.note), feature_id, int(now.timestamp() * 1000))
        post_annotation(grafana_url, grafana_token, payload)


if __name__ == "__main__":
    main()
