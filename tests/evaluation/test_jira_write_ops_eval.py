"""#134 evaluation — security boundaries for Jira write operations (hostile refs, server errors)."""

from __future__ import annotations

import sys

import pytest

from tests.test_tracker_jira import _close, _comment, _edit, _status

pytestmark = pytest.mark.skipif(sys.platform == "win32", reason="fake_jira is POSIX only")

HOSTILE_REFS = ["SCRUM-1/../../../myself", "SCRUM-1?expand=x", "SCRUM-1\n", "../SCRUM-1", "SCRUM-1/transitions"]


@pytest.mark.parametrize("ref", HOSTILE_REFS)
@pytest.mark.parametrize("op", ["edit", "comment", "status", "close"])
def test_hostile_ref_is_rejected_before_any_request(fake_jira, tmp_path, op, ref):
    calls = {"edit": lambda: _edit(tmp_path, ref, "--body", "x"), "comment": lambda: _comment(tmp_path, ref),
             "status": lambda: _status(tmp_path, ref, "done"), "close": lambda: _close(tmp_path, ref)}
    r = calls[op]()
    assert r.returncode == 1
    assert r.stderr.startswith("Error: invalid issue reference")
    assert fake_jira.calls() == []


@pytest.mark.parametrize("op", ["edit", "comment", "status", "close"])
def test_server_error_on_write_is_error_line_without_token(fake_jira, tmp_path, op):
    key = fake_jira.add_issue("T")
    fake_jira.fail_next(500, "boom")
    runs = {"edit": lambda: _edit(tmp_path, key, "--body", "x"), "comment": lambda: _comment(tmp_path, key),
            "status": lambda: _status(tmp_path, key, "done"), "close": lambda: _close(tmp_path, key)}
    r = runs[op]()
    assert r.returncode == 1
    assert r.stderr.startswith("Error:")
    assert "Traceback" not in r.stderr
    assert "tok-SECRET" not in r.stdout + r.stderr
    assert not r.stdout.startswith(("updated", "commented", "closed"))
