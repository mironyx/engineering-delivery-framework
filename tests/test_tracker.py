"""Tests for bin/tracker.py and bin/_tracker_contract.py — issue #118.

Covers LLD v3 E3.1 §1.1: tracker selection from the environment (worktree-safe
.env root), Jira config validation, the error contract (I1, I2, I4, I5), the
pinned grammar, and the shared contract helpers (status vocabulary, Issue JSON).

The GitHub backend's close is a stub (TrackerError("not implemented")), so a close request
that passes parsing and config validation is observed as "Error: not implemented". create and
status are real since #119, view/list/edit/comment since #120; their grammar tests observe the
gh calls they make instead (behaviour: test_tracker_github.py).
"""

from __future__ import annotations

import json
import pathlib
import subprocess
import sys
from dataclasses import asdict

import pytest

BIN_DIR = pathlib.Path(__file__).resolve().parent.parent / "plugins" / "edf" / "bin"
TRACKER = BIN_DIR / "tracker.py"

pytestmark = pytest.mark.skipif(sys.platform == "win32", reason="fake_gh needs a POSIX shell")

HOST = "https://example.atlassian.net"
EMAIL = "dev@example.com"
TOKEN = "SENTINEL-TOKEN-7f3a9c"  # noqa: S105 — test sentinel, never a real secret
SPACE = "EDF"

FULL_JIRA = {"JIRA_HOST": HOST, "JIRA_EMAIL": EMAIL, "JIRA_API_TOKEN": TOKEN, "JIRA_SPACE": SPACE}

UNKNOWN_OP_MSG = (
    "Error: unknown operation 'frobnicate'. "
    "Use: tracker | create | view | list | edit | comment | status | close"
)
EDIT_NEEDS_MSG = "Error: edit needs one of --title, --body, --add-label, --remove-label"
NOT_IMPLEMENTED = "Error: not implemented"
NO_DUP_RULE = {"argv_prefix": ["issue", "list"], "stdout": ""}
CREATED_RULE = {"argv_prefix": ["issue", "create"], "stdout": "https://github.com/owner/repo/issues/42\n"}
ISSUE_1 = {"number": 1, "title": "T", "body": "", "state": "OPEN",
           "labels": {"nodes": [{"name": "a"}, {"name": "c"}]}, "projectItems": {"nodes": []}}
ISSUE_RULE = {"argv_prefix": ["api", "graphql"], "argv_contains": ["number=1"],
              "stdout": json.dumps({"data": {"repository": {"issue": ISSUE_1}}})}
LIST_RULE = {"argv_prefix": ["api", "graphql"], "stdout": json.dumps({"data": {"repository": {"issues": {"nodes": []}}}})}


# ---------------------------------------------------------------- helpers


def _run(cwd: pathlib.Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(TRACKER), *args],
        cwd=cwd,
        capture_output=True,
        text=True,
        timeout=30,
    )


def _assert_error(result: subprocess.CompletedProcess, expected: str | None = None) -> None:
    """I5: exit 1, exactly one `Error: …` line on stderr, no traceback."""
    assert result.returncode == 1, (result.returncode, result.stdout, result.stderr)
    assert result.stderr.startswith("Error: "), result.stderr
    assert "Traceback" not in result.stderr
    assert len(result.stderr.strip().splitlines()) == 1, result.stderr
    if expected is not None:
        assert result.stderr.strip() == expected


def _set_env(monkeypatch, values: dict[str, str]) -> None:
    for key, value in values.items():
        monkeypatch.setenv(key, value)


def _write_dotenv(root: pathlib.Path, values: dict[str, str]) -> None:
    (root / ".env").write_text("".join(f"{k}={v}\n" for k, v in values.items()), encoding="utf-8")


def _without(var: str) -> dict[str, str]:
    return {k: v for k, v in FULL_JIRA.items() if k != var}


# ---------------------------------------------------------------- tracker selection


class TestTrackerSelection:
    """#118 — Story 1.1 AC1–AC3: backend chosen from OS env, then .env."""

    def test_uses_github_when_jira_host_unset(self, fake_gh):
        result = _run(fake_gh.repo, "tracker")
        assert result.returncode == 0, result.stderr
        assert result.stdout == "github\n"
        assert result.stderr == ""

    def test_uses_github_when_jira_host_empty_in_os_env(self, fake_gh, monkeypatch):
        monkeypatch.setenv("JIRA_HOST", "")
        result = _run(fake_gh.repo, "tracker")
        assert result.returncode == 0, result.stderr
        assert result.stdout == "github\n"

    def test_uses_github_when_jira_host_empty_placeholder_in_dotenv(self, fake_gh):
        _write_dotenv(fake_gh.repo, {"JIRA_HOST": "", "JIRA_EMAIL": "", "JIRA_API_TOKEN": "", "JIRA_SPACE": ""})
        result = _run(fake_gh.repo, "tracker")
        assert result.returncode == 0, result.stderr
        assert result.stdout == "github\n"

    def test_selects_jira_from_os_env(self, fake_gh, monkeypatch):
        _set_env(monkeypatch, FULL_JIRA)
        result = _run(fake_gh.repo, "tracker")
        assert result.returncode == 0, result.stderr
        assert result.stdout == "jira\n"

    def test_selects_jira_from_dotenv_only(self, fake_gh):
        _write_dotenv(fake_gh.repo, FULL_JIRA)
        result = _run(fake_gh.repo, "tracker")
        assert result.returncode == 0, result.stderr
        assert result.stdout == "jira\n"

    def test_os_value_wins_over_dotenv(self, fake_gh, monkeypatch):
        # .env alone would fail the https check; the OS value must override it.
        _write_dotenv(fake_gh.repo, {**FULL_JIRA, "JIRA_HOST": "http://insecure.example"})
        monkeypatch.setenv("JIRA_HOST", HOST)
        result = _run(fake_gh.repo, "tracker")
        assert result.returncode == 0, result.stderr
        assert result.stdout == "jira\n"

    def test_os_value_wins_over_dotenv_reverse(self, fake_gh, monkeypatch):
        _write_dotenv(fake_gh.repo, FULL_JIRA)
        monkeypatch.setenv("JIRA_HOST", "http://insecure.example")
        _assert_error(_run(fake_gh.repo, "tracker"), "Error: JIRA_HOST must use https://")

    def test_companions_mix_os_env_and_dotenv(self, fake_gh, monkeypatch):
        _write_dotenv(fake_gh.repo, {"JIRA_EMAIL": EMAIL, "JIRA_SPACE": SPACE})
        _set_env(monkeypatch, {"JIRA_HOST": HOST, "JIRA_API_TOKEN": TOKEN})
        result = _run(fake_gh.repo, "tracker")
        assert result.returncode == 0, result.stderr
        assert result.stdout == "jira\n"

    def test_reads_dotenv_from_main_repo_root_in_linked_worktree(self, fake_gh, tmp_path):
        repo = fake_gh.repo
        git = ["git", "-c", "user.name=t", "-c", "user.email=t@example.com", "-C", str(repo)]
        subprocess.run([*git, "commit", "-q", "--allow-empty", "-m", "init"], check=True)
        worktree = tmp_path / "wt"
        subprocess.run([*git, "worktree", "add", "-q", "-b", "wt-branch", str(worktree)], check=True)
        _write_dotenv(repo, FULL_JIRA)
        assert not (worktree / ".env").exists()

        result = _run(worktree, "tracker")
        assert result.returncode == 0, result.stderr
        assert result.stdout == "jira\n"

    def test_tracker_op_makes_no_gh_call(self, fake_gh):
        result = _run(fake_gh.repo, "tracker")
        assert result.returncode == 0, result.stderr
        assert fake_gh.calls() == []

    def test_tracker_op_makes_no_gh_call_with_jira(self, fake_gh, monkeypatch):
        _set_env(monkeypatch, FULL_JIRA)
        result = _run(fake_gh.repo, "tracker")
        assert result.returncode == 0, result.stderr
        assert fake_gh.calls() == []


# ---------------------------------------------------------------- Jira config validation


CONFIG_ERROR_CASES = [
    pytest.param({"JIRA_HOST": HOST}, "Error: JIRA_HOST is set but JIRA_EMAIL is missing", id="only-host"),
    pytest.param(_without("JIRA_EMAIL"), "Error: JIRA_HOST is set but JIRA_EMAIL is missing", id="no-email"),
    pytest.param(
        {"JIRA_HOST": HOST, "JIRA_EMAIL": EMAIL},
        "Error: JIRA_HOST is set but JIRA_API_TOKEN is missing",
        id="host-email",
    ),
    pytest.param(
        _without("JIRA_API_TOKEN"), "Error: JIRA_HOST is set but JIRA_API_TOKEN is missing", id="no-token"
    ),
    pytest.param(_without("JIRA_SPACE"), "Error: JIRA_HOST is set but JIRA_SPACE is missing", id="no-space"),
    pytest.param(
        {**FULL_JIRA, "JIRA_HOST": "http://example.atlassian.net"},
        "Error: JIRA_HOST must use https://",
        id="http-host",
    ),
    pytest.param(
        {**FULL_JIRA, "JIRA_HOST": "example.atlassian.net"},
        "Error: JIRA_HOST must use https://",
        id="no-scheme",
    ),
    pytest.param(
        {"JIRA_HOST": "http://example.atlassian.net", "JIRA_API_TOKEN": TOKEN},
        "Error: JIRA_HOST is set but JIRA_EMAIL is missing",
        id="missing-var-reported-before-https",
    ),
]

# Ops that would otherwise be valid; config validation must run for each.
VALID_OPS = [
    pytest.param(["tracker"], id="tracker"),
    pytest.param(["view", "1"], id="view"),
    pytest.param(["list"], id="list"),
    pytest.param(["create", "--title", "T", "--body", "B"], id="create"),
    pytest.param(["edit", "1", "--title", "T"], id="edit"),
    pytest.param(["comment", "1", "--body", "B"], id="comment"),
    pytest.param(["status", "1", "todo"], id="status"),
    pytest.param(["close", "1"], id="close"),
]


class TestJiraConfigValidation:
    """#118 — Story 1.1 AC4–AC5, invariants I1, I2, I5."""

    @pytest.mark.parametrize(("env", "expected"), CONFIG_ERROR_CASES)
    def test_config_error_from_os_env(self, fake_gh, monkeypatch, env, expected):
        _set_env(monkeypatch, env)
        result = _run(fake_gh.repo, "tracker")
        _assert_error(result, expected)
        assert result.stdout == ""

    @pytest.mark.parametrize(("env", "expected"), CONFIG_ERROR_CASES)
    def test_config_error_from_dotenv(self, fake_gh, env, expected):
        _write_dotenv(fake_gh.repo, env)
        _assert_error(_run(fake_gh.repo, "tracker"), expected)

    @pytest.mark.parametrize("argv", VALID_OPS)
    def test_every_op_runs_config_validation(self, fake_gh, monkeypatch, argv):
        monkeypatch.setenv("JIRA_HOST", HOST)
        _assert_error(_run(fake_gh.repo, *argv), "Error: JIRA_HOST is set but JIRA_EMAIL is missing")

    @pytest.mark.parametrize("argv", VALID_OPS)
    @pytest.mark.parametrize(("env", "expected"), CONFIG_ERROR_CASES)
    def test_config_error_makes_no_gh_call(self, fake_gh, monkeypatch, env, expected, argv):
        """I1: a Jira config error makes no gh call."""
        fake_gh.rules([{"argv_prefix": [], "stdout": "", "exit": 0}])
        _set_env(monkeypatch, env)
        result = _run(fake_gh.repo, *argv)
        _assert_error(result, expected)
        assert fake_gh.calls() == []

    @pytest.mark.parametrize("argv", [p for p in VALID_OPS if p.id not in ("tracker", "create", "view", "list")])
    def test_valid_jira_config_dispatches_to_jira_backend(self, fake_gh, fake_jira, argv):
        """#131/#134: a valid config reaches the implemented Jira backend; no gh call, no stub error."""
        result = _run(fake_gh.repo, *argv)
        assert result.returncode == 1
        assert NOT_IMPLEMENTED not in result.stderr
        assert fake_gh.calls() == []

    @pytest.mark.parametrize(
        "env",
        [
            pytest.param(_without("JIRA_EMAIL"), id="no-email"),
            pytest.param(_without("JIRA_SPACE"), id="no-space"),
            pytest.param({**FULL_JIRA, "JIRA_HOST": "http://example.atlassian.net"}, id="http-host"),
            pytest.param(None, id="valid"),  # None: served by the fake_jira fixture
        ],
    )
    @pytest.mark.parametrize("argv", VALID_OPS)
    @pytest.mark.parametrize("source", ["os", "dotenv"])
    def test_token_never_printed(self, fake_gh, monkeypatch, request, env, argv, source):
        """I2: the JIRA_API_TOKEN value appears in neither stream."""
        token = TOKEN
        if env is None:  # valid config: run against the local fake, never example.atlassian.net
            env = request.getfixturevalue("fake_jira").env
            token = env["JIRA_API_TOKEN"]
        if source == "os":
            _set_env(monkeypatch, env)
        else:
            _write_dotenv(fake_gh.repo, env)
        result = _run(fake_gh.repo, *argv)
        # Guard against a vacuous pass: the run must end through the error contract
        # (or succeed), never via a crash whose output happens to omit the token.
        assert "Traceback" not in result.stderr
        assert result.returncode in (0, 1)
        assert token not in result.stdout
        assert token not in result.stderr


class TestNoEarlyBackendImport:
    """#118 — I4: no backend module is imported before config validation succeeds."""

    def test_config_error_does_not_import_github_backend(self, fake_gh, monkeypatch, capsys):
        import tracker

        monkeypatch.delitem(sys.modules, "_tracker_github", raising=False)
        monkeypatch.chdir(fake_gh.repo)
        monkeypatch.setenv("JIRA_HOST", HOST)

        rc = tracker.main(["view", "1"])

        assert rc == 1
        assert "_tracker_github" not in sys.modules
        err = capsys.readouterr().err
        assert err.strip() == "Error: JIRA_HOST is set but JIRA_EMAIL is missing"

    def test_https_error_does_not_import_github_backend(self, fake_gh, monkeypatch, capsys):
        import tracker

        monkeypatch.delitem(sys.modules, "_tracker_github", raising=False)
        monkeypatch.chdir(fake_gh.repo)
        _set_env(monkeypatch, {**FULL_JIRA, "JIRA_HOST": "http://example.atlassian.net"})

        rc = tracker.main(["create", "--title", "T", "--body", "B"])

        assert rc == 1
        assert "_tracker_github" not in sys.modules
        assert capsys.readouterr().err.strip() == "Error: JIRA_HOST must use https://"

    def test_main_returns_int_for_tracker_op(self, fake_gh, monkeypatch, capsys):
        import tracker

        monkeypatch.chdir(fake_gh.repo)
        assert tracker.main(["tracker"]) == 0
        assert capsys.readouterr().out == "github\n"


class TestJiraVarsReadOnlyByTracker:
    """#118 — I3: JIRA_* is referenced in bin/ only by tracker.py (and later _tracker_jira.py)."""

    def test_jira_vars_only_in_tracker_modules(self):
        allowed = {"tracker.py", "_tracker_jira.py"}
        offenders = sorted(
            p.name
            for p in BIN_DIR.rglob("*")
            if p.is_file()
            and "__pycache__" not in p.parts  # bytecode of tracker.py is not a source file
            and p.name not in allowed
            and "JIRA_" in p.read_text(encoding="utf-8", errors="ignore")
        )
        assert offenders == []


# ---------------------------------------------------------------- grammar


class TestGrammar:
    """#118 — pinned grammar and error contract (I5)."""

    def test_unknown_operation(self, fake_gh):
        result = _run(fake_gh.repo, "frobnicate")
        _assert_error(result, UNKNOWN_OP_MSG)
        assert fake_gh.calls() == []

    def test_missing_operation(self, fake_gh):
        result = _run(fake_gh.repo)
        _assert_error(result)
        assert result.stderr.startswith("Error: unknown operation")
        assert "Use: tracker | create | view | list | edit | comment | status | close" in result.stderr

    def test_unknown_operation_reported_before_config_error(self, fake_gh, monkeypatch):
        """Parsing runs before config resolution (main: _parse then _resolve_context)."""
        monkeypatch.setenv("JIRA_HOST", HOST)
        _assert_error(_run(fake_gh.repo, "frobnicate"), UNKNOWN_OP_MSG)

    # -- create (hand-rolled parser, parity-bound messages)

    def test_create_requires_title(self, fake_gh):
        _assert_error(_run(fake_gh.repo, "create", "--body", "B"), "Error: --title is required")

    def test_create_requires_body(self, fake_gh):
        _assert_error(_run(fake_gh.repo, "create", "--title", "T"), "Error: --body is required")

    @pytest.mark.parametrize(
        ("argv", "expected"),
        [
            pytest.param(["--title", "", "--body", "B"], "Error: --title is required", id="empty-title"),
            pytest.param(["--title", "T", "--body", ""], "Error: --body is required", id="empty-body"),
        ],
    )
    def test_create_empty_value_counts_as_missing(self, fake_gh, argv, expected):
        # #119: gh-create-issue.sh used [[ -z ]], so an empty value was "required" too (I6 parity).
        result = _run(fake_gh.repo, "create", *argv)
        _assert_error(result, expected)
        assert fake_gh.calls() == []

    def test_create_reports_title_before_body(self, fake_gh):
        _assert_error(_run(fake_gh.repo, "create"), "Error: --title is required")

    def test_create_unknown_option(self, fake_gh):
        _assert_error(
            _run(fake_gh.repo, "create", "--title", "T", "--body", "B", "--bogus"),
            "Error: unknown option '--bogus'",
        )

    @pytest.mark.parametrize("flag", ["--title", "--body", "--labels", "--type", "--parent", "--board-status"])
    def test_create_flag_without_value(self, fake_gh, flag):
        base = ["create", "--title", "T", "--body", "B"]
        _assert_error(_run(fake_gh.repo, *base, flag), f"Error: {flag} needs a value")

    def test_create_consumes_dash_value_verbatim(self, fake_gh):
        # "-x" is the title and "--y" the body, not options; both reach gh issue create.
        fake_gh.rules([NO_DUP_RULE, CREATED_RULE])
        result = _run(fake_gh.repo, "create", "--title", "-x", "--body", "--y")
        assert (result.returncode, result.stdout) == (0, "created:42\n"), result.stderr
        create = [c for c in fake_gh.calls() if c["argv"][:2] == ["issue", "create"]]
        assert create[0]["argv"][2:4] == ["--title", "-x"]
        assert create[0]["stdin"] == "--y"

    def test_create_board_status_not_validated_at_parse_time(self, fake_gh):
        # An invalid --board-status is a board-step warning after the issue exists, not a parse error.
        fake_gh.rules([NO_DUP_RULE, CREATED_RULE])
        result = _run(
            fake_gh.repo, "create", "--title", "T", "--body", "B", "--add-to-board", "--board-status", "bogus"
        )
        assert result.returncode == 0, result.stderr
        assert result.stdout == "created:42\n"
        assert result.stderr == "Warning: failed to add #42 to board\n"

    def test_create_accepts_full_grammar(self, fake_gh):
        epic = {"number": 12, "title": "E", "body": "", "state": "OPEN", "labels": {"nodes": []},
                "projectItems": {"nodes": []}}
        fake_gh.rules([
            {"argv_prefix": ["api", "graphql"], "stdout": json.dumps({"data": {"repository": {"issue": epic}}})},
            NO_DUP_RULE,
        ])
        result = _run(
            fake_gh.repo,
            "create",
            "--title", "T",
            "--body", "B",
            "--labels", "a,b",
            "--type", "epic",
            "--parent", "12",
            "--add-to-board",
            "--board-status", "todo",
            "--dry-run",
        )  # fmt: skip
        assert result.returncode == 0, result.stderr
        assert result.stdout.startswith("dry-run: would create issue\n")
        assert "  parent: #12\n" in result.stdout
        assert "  labels: a,b,epic\n" in result.stdout

    # -- edit

    def test_edit_requires_a_change_flag(self, fake_gh):
        result = _run(fake_gh.repo, "edit", "1")
        _assert_error(result, EDIT_NEEDS_MSG)
        assert fake_gh.calls() == []

    @pytest.mark.parametrize(
        "flags",
        [
            pytest.param(["--title", "T"], id="title"),
            pytest.param(["--body", "B"], id="body"),
            pytest.param(["--add-label", "a"], id="add-label"),
            pytest.param(["--remove-label", "a"], id="remove-label"),
            pytest.param(["--add-label", "a", "--add-label", "b", "--remove-label", "c"], id="repeated"),
        ],
    )
    def test_edit_with_a_change_flag_reaches_backend(self, fake_gh, flags):
        # #120: edit is real; the request reaches gh issue edit (behaviour: test_tracker_github.py).
        fake_gh.rules([ISSUE_RULE, {"argv_prefix": ["issue", "edit"], "stdout": ""}])
        result = _run(fake_gh.repo, "edit", "1", *flags)
        assert (result.returncode, result.stdout) == (0, "updated:#1\n"), result.stderr
        assert [c["argv"][:3] for c in fake_gh.calls() if c["argv"][0] == "issue"] == [["issue", "edit", "1"]]

    def test_edit_rejects_abbreviated_flag(self, fake_gh):
        result = _run(fake_gh.repo, "edit", "1", "--tit", "T")
        _assert_error(result)
        assert result.stderr.strip() != NOT_IMPLEMENTED

    def test_edit_requires_ref(self, fake_gh):
        result = _run(fake_gh.repo, "edit")
        _assert_error(result)
        assert result.stderr.strip() != NOT_IMPLEMENTED

    # -- argparse-backed ops: errors use the Error contract, not argparse usage/exit 2

    @pytest.mark.parametrize(
        "argv",
        [
            pytest.param(["view"], id="view-no-ref"),
            pytest.param(["view", "1", "extra"], id="view-extra-arg"),
            pytest.param(["list", "--bogus"], id="list-unknown-flag"),
            pytest.param(["comment", "1"], id="comment-no-body"),
            pytest.param(["comment"], id="comment-no-ref"),
            pytest.param(["close"], id="close-no-ref"),
            pytest.param(["status", "1"], id="status-no-status"),
            pytest.param(["status"], id="status-no-ref"),
        ],
    )
    def test_parse_errors_follow_error_contract(self, fake_gh, argv):
        result = _run(fake_gh.repo, *argv)
        _assert_error(result)
        assert "usage:" not in result.stderr
        assert result.stderr.strip() != NOT_IMPLEMENTED
        assert fake_gh.calls() == []

    @pytest.mark.parametrize(
        ("argv", "rules", "expected"),
        [
            # #120: view/list/comment are real; each is observed by the gh call it makes.
            pytest.param(["view", "1"], [ISSUE_RULE], '"ref": "#1"', id="view"),
            pytest.param(["list"], [LIST_RULE], "[]", id="list"),
            pytest.param(["list", "--status", "todo", "--label", "bug"], [LIST_RULE], "[]", id="list-filters"),
            pytest.param(["comment", "1", "--body", "B"],
                         [ISSUE_RULE, {"argv_prefix": ["issue", "comment"], "stdout": ""}], "commented:#1",
                         id="comment"),
        ],
    )
    def test_valid_requests_reach_github_backend(self, fake_gh, argv, rules, expected):
        fake_gh.rules(rules)
        result = _run(fake_gh.repo, *argv)
        assert result.returncode == 0, result.stderr
        assert expected in result.stdout
        assert fake_gh.calls(), "request never reached gh"

    def test_opaque_ref_reaches_github_backend(self, fake_gh):
        # The entry point keeps REF opaque; the GitHub backend rejects a non-numeric one itself.
        _assert_error(_run(fake_gh.repo, "view", "PROJ-12"), "Error: invalid GitHub reference 'PROJ-12'")
        assert fake_gh.calls() == []

    def test_close_reaches_github_backend(self, fake_gh):
        # #121: close is implemented; an unknown ref proves the GitHub backend was reached.
        fake_gh.rules([{"argv_prefix": ["api", "graphql"], "exit": 1,
                        "stderr": "gh: Could not resolve to an Issue with the number of 1.\n"}])
        _assert_error(_run(fake_gh.repo, "close", "1"), "Error: #1 not found")

    @pytest.mark.parametrize(
        "argv",
        [
            pytest.param(["status", "1", "in progress"], id="status-two-words"),
            pytest.param(["status", "1", "todo", "--add-to-board"], id="status-add-to-board"),
            # The backend's status() calls normalise_status itself, after board config.
            pytest.param(["status", "1", "bogus"], id="status-value-not-validated-by-entry-point"),
        ],
    )
    def test_valid_status_requests_reach_github_backend(self, fake_gh, argv):
        # No .github/project.env in the fresh repo: the backend's config check answers.
        result = _run(fake_gh.repo, *argv)
        assert result.returncode == 1
        assert result.stderr.startswith("Error: config file not found: ")
        assert fake_gh.calls() == []


# ---------------------------------------------------------------- _tracker_contract


class TestNormaliseStatus:
    """#118 — Story 1.5 AC6: status vocabulary."""

    def test_vocabulary(self):
        from _tracker_contract import STATUSES

        assert STATUSES == ("todo", "in progress", "blocked", "done")

    @pytest.mark.parametrize("raw", ["todo", "in progress", "blocked", "done"])
    def test_accepts_each_status(self, raw):
        from _tracker_contract import normalise_status

        assert normalise_status(raw) == raw

    @pytest.mark.parametrize(
        ("raw", "expected"),
        [("Todo", "todo"), ("In Progress", "in progress"), ("BLOCKED", "blocked"), ("Done", "done")],
    )
    def test_lower_cases(self, raw, expected):
        from _tracker_contract import normalise_status

        assert normalise_status(raw) == expected

    @pytest.mark.parametrize("raw", ["bogus", "", "in-progress", "inprogress", "closed"])
    def test_rejects_unknown_status(self, raw):
        from _tracker_contract import TrackerError, normalise_status

        with pytest.raises(TrackerError) as exc:
            normalise_status(raw)
        assert str(exc.value) == f"unknown status '{raw}'. Use: todo | blocked | \"in progress\" | done"

    def test_tracker_error_carries_message_without_prefix(self):
        from _tracker_contract import TrackerError, normalise_status

        with pytest.raises(TrackerError) as exc:
            normalise_status("bogus")
        assert not str(exc.value).startswith("Error:")


class TestIssueJson:
    """#118 — Issue JSON shape shared by every backend."""

    def _issue(self, **overrides):
        from _tracker_contract import Issue

        fields = {
            "ref": "42",
            "title": "Fix — naïve parser",
            "body": "Body with ünïcode",
            "labels": ["bug", "v3"],
            "status": "in progress",
            "parent": "7",
            "children": ["43", "44"],
        }
        fields.update(overrides)
        return Issue(**fields)

    def test_single_issue_matches_pinned_format(self):
        from _tracker_contract import issue_json

        issue = self._issue()
        assert issue_json(issue) == json.dumps(asdict(issue), indent=2, ensure_ascii=False)

    def test_key_order_as_declared(self):
        from _tracker_contract import issue_json

        parsed = json.loads(issue_json(self._issue()))
        assert list(parsed) == ["ref", "title", "body", "labels", "status", "parent", "children"]

    def test_non_ascii_not_escaped(self):
        from _tracker_contract import issue_json

        out = issue_json(self._issue())
        assert "naïve" in out
        assert "\\u" not in out

    def test_indent_two(self):
        from _tracker_contract import issue_json

        assert '\n  "ref": "42",' in issue_json(self._issue())

    def test_null_parent_and_empty_lists(self):
        from _tracker_contract import issue_json

        parsed = json.loads(issue_json(self._issue(parent=None, labels=[], children=[])))
        assert parsed["parent"] is None
        assert parsed["labels"] == []
        assert parsed["children"] == []

    def test_list_of_issues(self):
        from _tracker_contract import issue_json

        a, b = self._issue(ref="1"), self._issue(ref="2", parent=None)
        out = issue_json([a, b])
        assert out == json.dumps([asdict(a), asdict(b)], indent=2, ensure_ascii=False)
        assert [i["ref"] for i in json.loads(out)] == ["1", "2"]

    def test_empty_list(self):
        from _tracker_contract import issue_json

        assert json.loads(issue_json([])) == []


# ---------------------------------------------------------------- evaluator additions


class TestEvaluatorGaps:
    """#118 — feature-evaluator gap tests: LLD §1.1 Part B properties not covered above."""

    def test_token_excluded_from_config_and_context_repr(self):
        """I2 defence in depth: JiraConfig declares repr=False on token (LLD §1.1 Part B)."""
        import tracker

        jira = tracker.JiraConfig(HOST, EMAIL, TOKEN, SPACE)
        ctx = tracker.TrackerContext(pathlib.Path("."), None, "jira", jira)
        assert TOKEN not in repr(jira)
        assert TOKEN not in repr(ctx)

    def test_reads_dotenv_from_cwd_outside_a_repo(self, fake_gh, tmp_path, monkeypatch):
        """_env_root: outside a repo the .env is read from the current directory."""
        outside = tmp_path / "not-a-repo"
        outside.mkdir()
        monkeypatch.setenv("GIT_CEILING_DIRECTORIES", str(tmp_path))
        _write_dotenv(outside, FULL_JIRA)
        result = _run(outside, "tracker")
        assert result.returncode == 0, result.stderr
        assert result.stdout == "jira\n"

    def test_reads_dotenv_from_repo_root_when_run_in_a_subdirectory(self, fake_gh):
        """_env_root resolves the checkout root, not the cwd, so a subdirectory sees the root .env."""
        sub = fake_gh.repo / "a" / "b"
        sub.mkdir(parents=True)
        _write_dotenv(fake_gh.repo, FULL_JIRA)
        result = _run(sub, "tracker")
        assert result.returncode == 0, result.stderr
        assert result.stdout == "jira\n"

    def test_git_missing_from_path_is_an_error_without_traceback(self, tmp_path):
        """I5: no git on PATH fails through the Error contract, never a traceback."""
        result = subprocess.run(
            [sys.executable, str(TRACKER), "tracker"],
            cwd=tmp_path, capture_output=True, text=True, timeout=30,
            env={"PATH": str(tmp_path / "no-such-dir")},
        )  # fmt: skip
        _assert_error(result, "Error: git is not installed or not on PATH")
