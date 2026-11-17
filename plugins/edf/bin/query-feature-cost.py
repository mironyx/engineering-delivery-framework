"""Query Prometheus for feature cost/tokens and optionally label the issue and PR.

Usage:
  py bin/query-feature-cost.py <feature_id> [--issue N] [--pr N] [--stage pr|final]
  py bin/query-feature-cost.py --issue N [--pr N] [--stage pr|final]

Arguments:
  feature_id     Optional. Feature ID to look up, e.g. EDF-55. When omitted, derived from
                 --issue plus a prefix from the feature-identity resolver
                 (e.g. "engineering-delivery-framework" -> "EDF").
  --issue N      Issue reference (#N, N or Jira key); if given, applies stage-namespaced cost labels.
                 Required when feature_id is omitted.
  --pr N         GitHub PR number; if given, also applies labels to PR and outputs time-to-PR.
  --stage        Label stage: 'pr' (at PR creation) or 'final' (post-merge). Default: pr.
                 Labels are named ai-cost-<stage>:X, input-tokens-<stage>:X, etc.
                 Two stages per PR let external tools (e.g. Monocle) measure rework overhead.
"""

import argparse
import json
import pathlib
import subprocess
import sys
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timezone

import os

import _edf_env
import _feature_id
import _tracker_github
import tracker
from _tracker_contract import TrackerError

_PROM_HOST = os.environ.get("WINDOWS_IP", "localhost")
_PROM_PORT = os.environ.get("PROM_PORT", "9090")
PROM = f"http://{_PROM_HOST}:{_PROM_PORT}/api/v1/query"
TRACKER = pathlib.Path(__file__).resolve().parent / "tracker.py"


def git_root() -> pathlib.Path:
    # --git-common-dir always points to the main worktree's .git, even from a linked worktree
    common = subprocess.run(
        ["git", "rev-parse", "--git-common-dir"],
        capture_output=True, text=True, check=True,
    ).stdout.strip()
    p = pathlib.Path(common)
    if not p.is_absolute():
        p = pathlib.Path.cwd() / p
    return p.parent


def _prom_dir() -> pathlib.Path:
    """Resolve the Prometheus textfile directory.

    Honors $EDF_FEATURE_PROM_DIR, then .env in the repo root.
    """
    return _edf_env.prom_dir(git_root())


def read_feature_start(feature_id: str) -> datetime | None:
    """Return the recorded start timestamp for feature_id, or None if not available."""
    timing_file = _prom_dir() / "feature_timing.json"
    if not timing_file.exists():
        return None
    try:
        data = json.loads(timing_file.read_text(encoding="utf-8"))
        iso = data.get(feature_id, {}).get("start_iso")
        if iso:
            return datetime.fromisoformat(iso.replace("Z", "+00:00"))
    except Exception:
        pass
    return None


def fetch_pr_created_at(pr: int) -> datetime | None:
    """Return the PR creation timestamp from GitHub, or None on error."""
    result = subprocess.run(
        ["gh", "pr", "view", str(pr), "--json", "createdAt", "-q", ".createdAt"],
        capture_output=True, text=True,
    )
    if result.returncode != 0 or not result.stdout.strip():
        return None
    try:
        return datetime.fromisoformat(result.stdout.strip().replace("Z", "+00:00"))
    except ValueError:
        return None


def format_duration(seconds: float) -> str:
    """Format a duration in seconds as a human-readable string."""
    minutes = int(seconds // 60)
    if minutes < 60:
        return f"{minutes} min"
    hours, mins = divmod(minutes, 60)
    return f"{hours}h {mins}min"


def _extract_session_id(line: str, feature_id: str) -> str | None:
    if not (line.startswith("claude_session_feature{") and f'feature_id="{feature_id}"' in line):
        return None
    for part in line.split(","):
        if "session_id=" in part:
            return part.split('"')[1]
    return None


def read_session_ids(feature_id: str) -> list[str]:
    """Look up session IDs for a feature, querying Prometheus first, file as fallback."""
    ids = _read_session_ids_from_prom(feature_id)
    if ids:
        return ids
    return _read_session_ids_from_file(feature_id)


def _read_session_ids_from_prom(feature_id: str) -> list[str]:
    """Query Prometheus for session IDs mapped to this feature."""
    try:
        q = f'claude_session_feature{{feature_id="{feature_id}"}}'
        url = PROM + "?" + urllib.parse.urlencode({"query": q})
        rows = (
            json.loads(urllib.request.urlopen(url, timeout=3).read())
            .get("data", {})
            .get("result", [])
        )
        return [r["metric"]["session_id"] for r in rows if "session_id" in r.get("metric", {})]
    except Exception:
        return []


def _read_session_ids_from_file(feature_id: str) -> list[str]:
    """Fallback: read session IDs from the local .prom textfile."""
    prom_file = _prom_dir() / "session_feature.prom"
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


@dataclass
class UsageMetrics:
    cost: float
    inp: float
    out: float
    cr: float
    cc: float


def query_metrics(feature_id: str) -> UsageMetrics | None:
    """Query Prometheus for per-feature usage via the session->feature mapping gauge.

    Mirrors the Grafana dashboard's PromQL: join claude_code_* metrics with
    claude_session_feature on session_id, then sum by feature_id. This correctly
    splits cost when one session touches multiple features (agent-team runs).
    """
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
        return None

    def tok(typ: str) -> float:
        q = (
            f'sum by (feature_id) ('
            f'  claude_session_feature{{{f}}}'
            f'  * on(session_id) group_left()'
            f'  sum by (session_id) (claude_code_token_usage_tokens_total{{type="{typ}"}})'
            f')'
        )
        return query_prom(q) or 0.0

    return UsageMetrics(cost=cost, inp=tok("input"), out=tok("output"),
                        cr=tok("cacheRead"), cc=tok("cacheCreation"))


def build_time_line(feature_id: str, pr: int) -> str:
    """Return a time-to-PR markdown line, or empty string if data unavailable."""
    start = read_feature_start(feature_id)
    pr_created = fetch_pr_created_at(pr)
    if start is None or pr_created is None:
        return ""
    elapsed = (pr_created - start).total_seconds()
    return f"\n- **Time to PR:** {format_duration(elapsed)}"


# Justification: view and edit share one tracker.py subprocess runner (credentials live only there).
def _tracker(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run([sys.executable, str(TRACKER), *args], capture_output=True, text=True)


def _fetch_existing_labels(ref: str) -> list[str]:
    result = _tracker("view", ref)
    if result.returncode != 0:
        return []
    try:
        return list(json.loads(result.stdout).get("labels", []))
    except (json.JSONDecodeError, AttributeError):
        return []


def _fetch_pr_labels(pr: int) -> list[str]:
    result = subprocess.run(
        ["gh", "pr", "view", str(pr), "--json", "labels"],
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        return []
    return [lbl["name"] for lbl in json.loads(result.stdout).get("labels", [])]


# Justification: issue and PR label cleanup share the same stale-prefix rule.
def _stale(existing: list[str], new_labels: list[tuple[str, str]]) -> list[str]:
    """Existing labels that share a prefix with a new label but differ from it."""
    return [name for name in existing
            if any(name.startswith(f"{prefix}:") and name != label for prefix, label in new_labels)]


def apply_labels(ref: str, metrics: UsageMetrics, stage: str, pr: int | None = None) -> None:
    """Best-effort: one tracker `edit` for the issue, set_pr_labels for the PR; never raises."""
    labels = [
        (f"ai-cost-{stage}",       f"ai-cost-{stage}:{metrics.cost:.4f}"),
        (f"input-tokens-{stage}",  f"input-tokens-{stage}:{int(metrics.inp)}"),
        (f"output-tokens-{stage}", f"output-tokens-{stage}:{int(metrics.out)}"),
    ]
    add = [label for _, label in labels]
    if tracker.active_backend(_feature_id.main_checkout_root()) == "github":
        for label in add:
            subprocess.run(["gh", "label", "create", label, "--color", "0075ca", "--force"], capture_output=True)
    remove = _stale(_fetch_existing_labels(ref), labels)
    edit = ["edit", ref]
    for label in add:
        edit += ["--add-label", label]
    for label in remove:
        edit += ["--remove-label", label]
    _tracker(*edit)
    if pr is not None:
        _tracker_github.set_pr_labels(pr, add, _stale(_fetch_pr_labels(pr), labels))
    targets = f"issue {ref}" + (f", PR #{pr}" if pr is not None else "")
    for label in add:
        print(f"Label applied: {label} -> {targets}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("feature_id", nargs="?", help="e.g. EDF-55. Derived from --issue if omitted.")
    parser.add_argument("--issue", help="Issue reference (#N, N or a Jira key) for cost labels")
    parser.add_argument("--pr", type=int, help="GitHub PR number to also apply cost labels to")
    parser.add_argument("--stage", choices=["pr", "final"], default="pr",
                        help="Label stage suffix: 'pr' at PR creation, 'final' post-merge")
    args = parser.parse_args()

    if not args.feature_id:
        if args.issue is None:
            parser.error("either feature_id or --issue must be provided")
        try:
            args.feature_id = _feature_id.resolve_feature_id(args.issue, _feature_id.main_checkout_root())
        except TrackerError as e:
            print(f"Error: {e}", file=sys.stderr)
            sys.exit(1)

    session_ids = read_session_ids(args.feature_id)
    sessions_note = f" ({len(session_ids)} sessions)" if len(session_ids) > 1 else ""
    heading = "Final " if args.stage == "final" else ""

    if not session_ids:
        print(f"## {heading}Usage\n- No session data found for {args.feature_id} — session tagging may not have run")
        sys.exit(0)

    metrics = query_metrics(args.feature_id)
    if metrics is None:
        print(f"## {heading}Usage\n- Prometheus unreachable at {PROM} — is the monitoring stack running?")
        sys.exit(0)

    time_line = build_time_line(args.feature_id, args.pr) if args.pr is not None else ""

    print(
        f"## {heading}Usage ({args.feature_id}{sessions_note})\n"
        f"- **Cost:** ${metrics.cost:.4f}\n"
        f"- **Tokens:** {int(metrics.inp):,} input / {int(metrics.out):,} output"
        f" / {int(metrics.cr):,} cache-read / {int(metrics.cc):,} cache-write"
        f"{time_line}"
    )
    if args.stage == "final":
        print("_Compare to PR-creation cost in the PR body to see post-PR rework overhead._")

    if args.issue is not None:
        apply_labels(args.issue, metrics, args.stage, pr=args.pr)


if __name__ == "__main__":
    main()
