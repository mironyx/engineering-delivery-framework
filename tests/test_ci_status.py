"""Tests for bin/ci-status.py — CI verdicts classified by script, not by the model.

The FCS session logs show each infra failure mode being diagnosed by hand, once
per occurrence: a GitHub billing block (every failing job executed zero steps),
Docker Hub rate limiting, a runner port collision, and a post-merge main run
misattributed to a PR through `displayTitle`.
"""

import importlib.util
import pathlib

BIN_DIR = pathlib.Path(__file__).resolve().parent.parent / "plugins" / "edf" / "bin"


def _mod():
    spec = importlib.util.spec_from_file_location("ci_status", BIN_DIR / "ci-status.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


SHA = "abcdef1234567890"


def _run(rid, conclusion="success", status="completed", name="CI", event="pull_request"):
    return {"databaseId": rid, "workflowName": name, "status": status, "conclusion": conclusion, "event": event}


def _job(name, conclusion, steps):
    return {"name": name, "conclusion": conclusion,
            "steps": [{"name": n, "conclusion": c} for n, c in steps]}


def test_all_green_is_pass():
    code, lines = _mod().classify(SHA, [_run(1), _run(2, name="Lint")], {}, {})
    assert code == 0
    assert lines[0].startswith("ci: pass")
    assert "abcdef12" in lines[0]


def test_no_runs_for_head_is_none_and_names_paths_ignore():
    # A docs-only head commit in a repo that paths-ignores docs/** gets no run at all.
    code, lines = _mod().classify(SHA, [], {}, {})
    assert code == 4
    assert "paths-ignored" in lines[0]


def test_running_workflow_is_pending():
    code, lines = _mod().classify(SHA, [_run(1), _run(2, name="Lint", status="in_progress", conclusion=None)], {}, {})
    assert code == 3
    assert "1/2" in lines[0]


def test_rerun_supersedes_failed_attempt():
    runs = [_run(1, conclusion="failure"), _run(5, conclusion="success")]
    code, _ = _mod().classify(SHA, runs, {}, {})
    assert code == 0


def test_zero_executed_steps_is_infra_not_code():
    # FCS #1384: billing block — failing jobs executed no steps.
    runs = [_run(9, conclusion="failure")]
    jobs = {9: [_job("Lint, Types & Unit tests", "failure", []), _job("validate", "failure", [])]}
    code, lines = _mod().classify(SHA, runs, jobs, {})
    assert code == 2
    assert "fail(infra)" in lines[0]
    assert "0 steps executed" in lines[0]
    assert "gh run rerun 9" in lines[1]


def test_rate_limit_in_log_is_infra():
    runs = [_run(9, conclusion="failure")]
    jobs = {9: [_job("Test & Push", "failure", [("Set up job", "success"), ("Start Supabase", "failure")])]}
    logs = {9: "Start Supabase\nError response from daemon: toomanyrequests: You have reached your pull rate limit\n"}
    code, lines = _mod().classify(SHA, runs, jobs, logs)
    assert code == 2
    assert "registry rate limit" in lines[0]
    assert "toomanyrequests" in lines[1]


def test_port_collision_in_log_is_infra():
    runs = [_run(9, conclusion="failure")]
    jobs = {9: [_job("Test & Push", "failure", [("Start Supabase", "failure")])]}
    logs = {9: "Bind for 0.0.0.0:54324 failed: port is already allocated"}
    code, lines = _mod().classify(SHA, runs, jobs, logs)
    assert code == 2
    assert "port collision" in lines[0]


def test_failing_test_step_is_code_failure_naming_job_and_step():
    runs = [_run(9, conclusion="failure")]
    jobs = {9: [_job("Lint, Types & Unit tests", "failure",
                     [("Checkout", "success"), ("Unit tests", "failure"), ("Upload", "skipped")])]}
    logs = {9: "FAIL tests/lib/foo.test.ts > returns 5xx\nAssertionError: expected 200 to be 500"}
    code, lines = _mod().classify(SHA, runs, jobs, logs)
    assert code == 1
    assert lines[0].startswith("ci: fail(code)")
    assert "Lint, Types & Unit tests" in lines[1]
    assert "step: Unit tests" in lines[1]


def test_scheduled_runs_do_not_count():
    # A scheduled workflow failing on main says nothing about a merge or a PR head.
    runs = [_run(1), _run(2, name="Observer", conclusion="failure", event="schedule")]
    code, _ = _mod().classify(SHA, runs, {}, {})
    assert code == 0
