"""Classify the CI state of a PR head (or a branch's latest run) in one line.

Replaces hand-diagnosis of red CI. Attribution is by head commit SHA — never by
`displayTitle`, which for a post-merge main run carries the PR's title.

Usage:
  py bin/ci-status.py --pr <number> [--wait <minutes>]
  py bin/ci-status.py --branch <name>

--wait polls every 30 s while the verdict is pending, so callers never hand-roll a
sleep loop. Keep it under the caller's command timeout (9 min fits a 10 min cap).

First output line is the verdict; at most a few detail lines follow.

Exit codes:
  0  pass           every workflow on the head completed green
  1  fail(code)     a job ran and failed — a real finding to fix
  2  fail(infra)    account/runner/registry problem — re-run, do not change code
  3  pending        at least one workflow is still running
  4  none           no workflow runs for the head commit (e.g. a paths-ignored,
                    docs-only commit — required checks will be absent)
"""

import argparse
import json
import re
import subprocess
import sys
import time

INFRA_LOG_PATTERNS = [
    (re.compile(r"toomanyrequests|pull rate limit|rate limit exceeded", re.I), "registry rate limit"),
    (re.compile(r"port is already allocated|address already in use", re.I), "runner port collision"),
    (re.compile(r"No space left on device", re.I), "runner out of disk"),
    (re.compile(r"runner has received a shutdown signal|lost communication with the server", re.I), "runner lost"),
    (re.compile(r"account payments have failed|spending limit", re.I), "billing block"),
]

GREEN = {"success", "skipped", "neutral"}
# Scheduled/manual workflows run against whatever main points at; they say nothing
# about a PR head or a merge, so only change-triggered runs count.
CHANGE_EVENTS = {"push", "pull_request", "pull_request_target", "merge_group"}


def gh_json(*args: str):
    out = subprocess.run(["gh", *args], capture_output=True, text=True, check=True).stdout
    return json.loads(out) if out.strip() else None


def gh_text(*args: str) -> str:
    return subprocess.run(["gh", *args], capture_output=True, text=True).stdout


def latest_per_workflow(runs: list[dict]) -> list[dict]:
    """Keep only the newest run of each workflow — re-runs supersede earlier attempts."""
    latest: dict[str, dict] = {}
    for r in runs:
        name = r.get("workflowName") or r.get("name") or str(r["databaseId"])
        if name not in latest or r["databaseId"] > latest[name]["databaseId"]:
            latest[name] = r
    return list(latest.values())


def executed_steps(job: dict) -> int:
    return sum(1 for s in job.get("steps") or [] if s.get("conclusion") not in (None, "", "skipped"))


def classify(sha: str, runs: list[dict], jobs_by_run: dict, logs_by_run: dict) -> tuple[int, list[str]]:
    """Return (exit code, output lines). Pure — all gh data is passed in."""
    head = sha[:8]
    runs = latest_per_workflow([r for r in runs if r.get("event", "push") in CHANGE_EVENTS])
    if not runs:
        return 4, [f"ci: none — no workflow runs for head {head}. If the head commit only "
                   "touches paths-ignored files (e.g. docs/**), CI will not run and required "
                   "checks will be absent."]

    pending = [r for r in runs if r.get("status") != "completed"]
    if pending:
        done = len(runs) - len(pending)
        return 3, [f"ci: pending — head {head}, {done}/{len(runs)} workflows complete"]

    failed = [r for r in runs if r.get("conclusion") not in GREEN]
    if not failed:
        return 0, [f"ci: pass — head {head}, {len(runs)} workflows green"]

    failed_jobs = [(r, j) for r in failed for j in jobs_by_run.get(r["databaseId"], [])
                   if j.get("conclusion") not in GREEN]

    if failed_jobs and all(executed_steps(j) == 0 for _, j in failed_jobs):
        rid = failed[0]["databaseId"]
        return 2, [f"ci: fail(infra) — head {head}: 0 steps executed in {len(failed_jobs)} failed "
                   "job(s) — account/billing block or no runner, not a code failure",
                   f"  fix the account/runner, then: gh run rerun {rid}"]

    for r in failed:
        log = logs_by_run.get(r["databaseId"], "")
        for pattern, label in INFRA_LOG_PATTERNS:
            m = pattern.search(log)
            if m:
                line = next((ln.strip() for ln in log.splitlines() if pattern.search(ln)), m.group(0))
                return 2, [f"ci: fail(infra) — head {head}: {label} in {r.get('workflowName', '')}",
                           f"  {line[:160]}",
                           f"  re-run, do not change code: gh run rerun {r['databaseId']} --failed"]

    if all(r.get("conclusion") == "cancelled" for r in failed):
        return 2, [f"ci: fail(infra) — head {head}: run cancelled "
                   "(concurrency or manual) — re-run: gh run rerun " + str(failed[0]["databaseId"])]

    lines = [f"ci: fail(code) — head {head}"]
    for r, j in failed_jobs[:3]:
        step = next((s.get("name") for s in j.get("steps") or [] if s.get("conclusion") == "failure"), "?")
        lines.append(f"  {r.get('workflowName', '')} / {j.get('name')} — step: {step} "
                     f"(gh run view {r['databaseId']} --log-failed)")
    if not failed_jobs:
        lines.append("  " + ", ".join(f"{r.get('workflowName', '')}: {r.get('conclusion')}" for r in failed))
    return 1, lines


def resolve_sha(pr: str | None, branch: str | None) -> str | None:
    if pr:
        return gh_json("pr", "view", pr, "--json", "headRefOid")["headRefOid"]
    rows = gh_json("run", "list", "--branch", branch, "--event", "push", "--limit", "1", "--json", "headSha") or []
    return rows[0]["headSha"] if rows else None


def check_once(pr: str | None, branch: str | None) -> tuple[int, list[str]]:
    try:
        sha = resolve_sha(pr, branch)
        if not sha:
            return 4, [f"ci: none — no workflow runs on branch {branch}"]
        runs = gh_json("run", "list", "--commit", sha, "--limit", "50", "--json",
                       "databaseId,workflowName,status,conclusion,event") or []
        runs = latest_per_workflow([r for r in runs if r.get("event") in CHANGE_EVENTS])
        failed = [r for r in runs if r.get("status") == "completed" and r.get("conclusion") not in GREEN]
        jobs_by_run = {r["databaseId"]: (gh_json("run", "view", str(r["databaseId"]), "--json", "jobs") or {}).get("jobs", [])
                       for r in failed}
        logs_by_run = {r["databaseId"]: gh_text("run", "view", str(r["databaseId"]), "--log-failed")
                       for r in failed}
    except (subprocess.CalledProcessError, FileNotFoundError, json.JSONDecodeError, KeyError) as e:
        return 3, [f"ci: unknown — gh query failed ({type(e).__name__})"]
    return classify(sha, runs, jobs_by_run, logs_by_run)


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--pr")
    group.add_argument("--branch")
    parser.add_argument("--wait", type=int, metavar="MINUTES", default=0,
                        help="poll every 30 s while pending, for up to MINUTES (keep under the caller's command timeout)")
    args = parser.parse_args()

    deadline = time.monotonic() + args.wait * 60
    code, lines = check_once(args.pr, args.branch)
    while code == 3 and time.monotonic() + 30 < deadline:
        time.sleep(30)
        code, lines = check_once(args.pr, args.branch)
    print("\n".join(lines))
    return code


if __name__ == "__main__":
    sys.exit(main())
