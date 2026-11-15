"""Tests for the GitHub backend `view`, `list`, `edit` and `comment` — issue #120.

Covers LLD v3 E3.1 §1.3 (Part A and Part B) and Open question 1 (GitHub status derivation):
the seven-key issue JSON (I10), the single `list` query capped at 100 (I11), absent
remove-labels skipped (I12), and bodies/comments sent on stdin (I13). Every test drives the
public CLI (`tracker.py`) as a subprocess under the fake `gh` (tests/fixtures/fake_gh.py) with
`cwd=fake_gh.repo`, and asserts on stdout, stderr, exit code and the fake `gh` call log.

Fake gh conventions the rules rely on (LLD §1.2/§1.3 Part B):
- Issue lookups are `gh api graphql ... -F number=N ...`; rules tell them apart with
  `argv_contains: ["number=N"]`.
- `list` is one `gh api graphql` call over `repository.issues`; its reply is
  `{"data": {"repository": {"issues": {"nodes": [...]}}}}`.
- Unknown issue: exit 1, stderr `gh: Could not resolve to an Issue with the number of N.`
"""

from __future__ import annotations

import importlib.util
import json
import pathlib
import subprocess
import sys

import pytest

TESTS_DIR = pathlib.Path(__file__).resolve().parent
BIN_DIR = TESTS_DIR.parent / "plugins" / "edf" / "bin"
TRACKER = BIN_DIR / "tracker.py"

pytestmark = pytest.mark.skipif(sys.platform == "win32", reason="fake_gh needs a POSIX shell")


def _load_recorder():
    """tests/fixtures is not a package — load the golden recorder by path."""
    path = TESTS_DIR / "fixtures" / "record_tracker_golden.py"
    spec = importlib.util.spec_from_file_location("record_tracker_golden", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


recorder = _load_recorder()
PROJECT_ENV: dict[str, str] = recorder.PROJECT_ENV

KEYS = ["ref", "title", "body", "labels", "status", "parent", "children"]
UNKNOWN_STATUS_MSG = "Error: unknown status 'bogus'. Use: todo | blocked | \"in progress\" | done\n"
OPTION_IDS = {
    "todo": PROJECT_ENV["STATUS_TODO"],
    "blocked": PROJECT_ENV["STATUS_BLOCKED"],
    "in progress": PROJECT_ENV["STATUS_IN_PROGRESS"],
    "done": PROJECT_ENV["STATUS_DONE"],
}


# ---------------------------------------------------------------- fake gh rules


def _node(number: int, *, title: str = "Some issue", body: str = "Body", state: str = "OPEN",
          labels: tuple[str, ...] = (), option: str | None = None, project_id: str = PROJECT_ENV["PROJECT_ID"],
          field_id: str = PROJECT_ENV["FIELD_ID"], on_board: bool = True) -> dict:
    """Full ISSUE_FIELDS node (LLD §1.2). `option` is the board column's option id, if any.

    fieldValues mirrors real GraphQL: values that are not single-select come back as `{}`."""
    field_values: list[dict] = [{}]
    if option is not None:
        field_values.append({"optionId": option, "field": {"id": field_id}})
    items = [{"id": f"PVTI_{number}", "project": {"id": project_id}, "fieldValues": {"nodes": field_values}}]
    return {
        "number": number,
        "title": title,
        "body": body,
        "state": state,
        "labels": {"nodes": [{"name": name} for name in labels]},
        "projectItems": {"nodes": items if on_board else []},
    }


def _issue_rule(number: int, **node_kwargs) -> dict:
    """A graphql issue lookup for one specific number."""
    response = json.dumps({"data": {"repository": {"issue": _node(number, **node_kwargs)}}}) + "\n"
    return {"argv_prefix": ["api", "graphql"], "argv_contains": [f"number={number}"], "stdout": response}


def _missing_rule(number: int) -> dict:
    return {
        "argv_prefix": ["api", "graphql"],
        "argv_contains": [f"number={number}"],
        "stderr": f"gh: Could not resolve to an Issue with the number of {number}.\n",
        "exit": 1,
    }


def _list_rule(nodes: list[dict]) -> dict:
    """The single repository.issues query `list` makes."""
    response = json.dumps({"data": {"repository": {"issues": {"nodes": nodes}}}}) + "\n"
    return {"argv_prefix": ["api", "graphql"], "stdout": response}


EDIT_OK = {"argv_prefix": ["issue", "edit"], "stdout": ""}
COMMENT_OK = {"argv_prefix": ["issue", "comment"], "stdout": "https://github.com/owner/repo/issues/5#issuecomment-1\n"}


# ---------------------------------------------------------------- helpers


def _run(cwd: pathlib.Path, *args: str, timeout: float = 30) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, str(TRACKER), *args], cwd=cwd, capture_output=True, text=True,
                          timeout=timeout, stdin=subprocess.DEVNULL)


def _write_project_env(root: pathlib.Path) -> None:
    (root / ".github").mkdir(exist_ok=True)
    (root / ".github" / "project.env").write_text("".join(f"{k}={v}\n" for k, v in PROJECT_ENV.items()),
                                                  encoding="utf-8")


def _calls(fake_gh, *prefix: str) -> list[dict]:
    return [c for c in fake_gh.calls() if c["argv"][: len(prefix)] == list(prefix)]


def _writes(fake_gh) -> list[dict]:
    """Every call that mutates GitHub state."""
    write_prefixes = (["issue", "create"], ["issue", "edit"], ["issue", "comment"], ["issue", "close"],
                      ["project", "item-add"], ["project", "item-edit"], ["project", "item-delete"])
    return [c for c in fake_gh.calls() if any(c["argv"][: len(p)] == p for p in write_prefixes)]


def _flag(argv: list[str], flag: str) -> str:
    assert flag in argv, (flag, argv)
    return argv[argv.index(flag) + 1]


def _flag_values(argv: list[str], flag: str) -> list[str]:
    """Every name passed with `flag`, whether as one comma-separated value or repeated flags."""
    names: list[str] = []
    for i, arg in enumerate(argv):
        if arg == flag:
            names += [n for n in argv[i + 1].split(",") if n]
    return names


def _only(calls: list[dict]) -> dict:
    assert len(calls) == 1, calls
    return calls[0]


def _ok_json(result: subprocess.CompletedProcess):
    assert result.returncode == 0, (result.stdout, result.stderr)
    assert result.stderr == ""
    return json.loads(result.stdout)


def _not_found(result: subprocess.CompletedProcess, number: int) -> None:
    assert (result.returncode, result.stdout, result.stderr) == (1, "", f"Error: #{number} not found\n")


# ---------------------------------------------------------------- view


class TestView:
    """#120 — describe("github view")."""

    def test_returns_seven_key_json_for_a_task_with_a_parent_epic(self, fake_gh):
        """#120 AC1 / I10 — exact keys in order; parent "#E"; children [] for a non-epic."""
        body = "## Parent epic\n#7\n\n## What\nDo the thing\n- [ ] #99 — not a child: not an epic\n"
        fake_gh.rules([_issue_rule(12, title="Add widget", body=body, labels=("kind:task", "backend"))])
        issue = _ok_json(_run(fake_gh.repo, "view", "#12"))
        assert list(issue.keys()) == KEYS
        assert issue == {
            "ref": "#12",
            "title": "Add widget",
            "body": body,
            "labels": ["kind:task", "backend"],
            "status": "todo",
            "parent": "#7",
            "children": [],
        }

    def test_parent_is_null_without_a_parent_epic_section(self, fake_gh):
        """#120 AC1 — parent is null when the body has no '## Parent epic'."""
        fake_gh.rules([_issue_rule(12, body="Just a body mentioning #7")])
        issue = _ok_json(_run(fake_gh.repo, "view", "12"))
        assert issue["parent"] is None
        assert issue["children"] == []

    def test_returns_children_for_an_epic_checklist_with_ticked_and_unticked_lines(self, fake_gh):
        """#120 AC1 — `- [ ]`, `- [x]`, `- [X]` lines, order kept, de-duplicated."""
        body = ("## What\nEpic\n\n### Tasks\n"
                "- [ ] #21 — first\n"
                "- [x] #22 — second\n"
                "- [X] #23 — third\n"
                "  - [ ] #24 — indented\n"
                "- [ ] #21 — duplicate line\n"
                "- [ ] T5 — not yet numbered\n"
                "See #30 in prose\n")
        fake_gh.rules([_issue_rule(7, body=body, labels=("epic",))])
        issue = _ok_json(_run(fake_gh.repo, "view", "#7"))
        assert list(issue.keys()) == KEYS
        assert issue["children"] == ["#21", "#22", "#23", "#24"]
        assert issue["parent"] is None

    def test_epic_without_checklist_has_empty_children(self, fake_gh):
        fake_gh.rules([_issue_rule(7, body="No tasks yet", labels=("epic",))])
        assert _ok_json(_run(fake_gh.repo, "view", "#7"))["children"] == []

    @pytest.mark.parametrize("status", ["todo", "blocked", "in progress", "done"])
    def test_maps_the_board_option_id_to_the_edf_status(self, fake_gh, status):
        """#120 Open question 1 — an open issue on the board takes its column."""
        _write_project_env(fake_gh.repo)
        fake_gh.rules([_issue_rule(12, option=OPTION_IDS[status])])
        assert _ok_json(_run(fake_gh.repo, "view", "#12"))["status"] == status

    @pytest.mark.parametrize("node_kwargs", [
        {"on_board": False},
        {"project_id": "PVT_other", "option": PROJECT_ENV["STATUS_IN_PROGRESS"]},
        {"option": None},
        {"option": "custom-column-id"},
        {"field_id": "PVTSSF_other", "option": PROJECT_ENV["STATUS_BLOCKED"]},
    ], ids=["not-on-board", "other-project", "no-column", "custom-column", "other-field"])
    def test_falls_back_to_todo_for_an_open_issue_not_on_the_board(self, fake_gh, node_kwargs):
        """#120 Open question 1 — anything but a matching board column is todo."""
        _write_project_env(fake_gh.repo)
        fake_gh.rules([_issue_rule(12, **node_kwargs)])
        assert _ok_json(_run(fake_gh.repo, "view", "#12"))["status"] == "todo"

    def test_falls_back_to_todo_without_project_env(self, fake_gh):
        """#120 Open question 1 — no .github/project.env: open is todo, and view still succeeds."""
        fake_gh.rules([_issue_rule(12, option=PROJECT_ENV["STATUS_IN_PROGRESS"])])
        assert _ok_json(_run(fake_gh.repo, "view", "#12"))["status"] == "todo"

    @pytest.mark.parametrize("option", [PROJECT_ENV["STATUS_IN_PROGRESS"], PROJECT_ENV["STATUS_TODO"], None],
                             ids=["in-progress-column", "todo-column", "not-on-board"])
    def test_reports_done_for_a_closed_issue_whatever_its_board_column(self, fake_gh, option):
        """#120 Open question 1 — CLOSED is always done."""
        _write_project_env(fake_gh.repo)
        fake_gh.rules([_issue_rule(12, state="CLOSED", option=option, on_board=option is not None)])
        assert _ok_json(_run(fake_gh.repo, "view", "#12"))["status"] == "done"

    def test_closed_issue_is_done_without_project_env(self, fake_gh):
        fake_gh.rules([_issue_rule(12, state="CLOSED", on_board=False)])
        assert _ok_json(_run(fake_gh.repo, "view", "#12"))["status"] == "done"

    def test_errors_not_found_for_an_unknown_number(self, fake_gh):
        """#120 AC5 — gh's 'Could not resolve' becomes 'Error: #N not found', exit 1."""
        fake_gh.rules([_missing_rule(404)])
        _not_found(_run(fake_gh.repo, "view", "#404"), 404)

    def test_errors_not_found_when_graphql_returns_a_null_issue(self, fake_gh):
        fake_gh.rules([{"argv_prefix": ["api", "graphql"], "argv_contains": ["number=404"],
                        "stdout": json.dumps({"data": {"repository": {"issue": None}}}) + "\n"}])
        _not_found(_run(fake_gh.repo, "view", "404"), 404)

    def test_accepts_123_and_hash_123_as_the_same_ref(self, fake_gh):
        """#120 — both ref forms query number=123 and print identical JSON with ref '#123'."""
        fake_gh.rules([_issue_rule(123, title="Same")])
        plain = _run(fake_gh.repo, "view", "123")
        hashed = _run(fake_gh.repo, "view", "#123")
        assert plain.returncode == hashed.returncode == 0, (plain.stderr, hashed.stderr)
        assert plain.stdout == hashed.stdout
        assert json.loads(plain.stdout)["ref"] == "#123"
        assert all("number=123" in c["argv"] for c in fake_gh.calls())

    def test_other_graphql_failure_is_an_error_line(self, fake_gh):
        fake_gh.rules([{"argv_prefix": ["api", "graphql"], "stderr": "HTTP 502: Bad Gateway\n", "exit": 1}])
        result = _run(fake_gh.repo, "view", "#12")
        assert result.returncode == 1
        assert result.stdout == ""
        assert result.stderr.startswith("Error: ")
        assert "HTTP 502" in result.stderr

    def test_view_makes_no_writes(self, fake_gh):
        fake_gh.rules([_issue_rule(12)])
        _ok_json(_run(fake_gh.repo, "view", "#12"))
        assert _writes(fake_gh) == []


# ---------------------------------------------------------------- list


class TestList:
    """#120 — describe("github list")."""

    def test_returns_an_array_of_seven_key_objects_in_server_order(self, fake_gh):
        """#120 AC2 / I10 — same shape as view; newest first as returned by the query."""
        nodes = [
            _node(30, title="Newest", body="## Parent epic\n#7\n", labels=("kind:task",)),
            _node(29, title="Epic", body="- [ ] #30 — Newest\n- [x] #28 — Old\n", labels=("epic",)),
            _node(28, title="Oldest"),
        ]
        fake_gh.rules([_list_rule(nodes)])
        issues = _ok_json(_run(fake_gh.repo, "list"))
        assert isinstance(issues, list)
        assert [list(i.keys()) for i in issues] == [KEYS] * 3
        assert [i["ref"] for i in issues] == ["#30", "#29", "#28"]
        assert issues[0]["parent"] == "#7"
        assert issues[0]["labels"] == ["kind:task"]
        assert issues[1]["children"] == ["#30", "#28"]
        assert issues[2]["children"] == []

    def test_makes_exactly_one_gh_call(self, fake_gh):
        """#120 I11 — one gh api graphql call, first 100, newest first."""
        fake_gh.rules([_list_rule([_node(1)])])
        _ok_json(_run(fake_gh.repo, "list", "--label", "kind:task"))
        call = _only(fake_gh.calls())
        assert call["argv"][:2] == ["api", "graphql"]
        joined = " ".join(call["argv"])
        assert "first" in joined and "100" in joined, call["argv"]
        assert "CREATED_AT" in joined and "DESC" in joined, call["argv"]

    def test_returns_up_to_100_items(self, fake_gh):
        """#120 AC2 / I11 — a full page of 100 comes back whole, from one call."""
        fake_gh.rules([_list_rule([_node(n) for n in range(200, 100, -1)])])
        issues = _ok_json(_run(fake_gh.repo, "list"))
        assert len(issues) == 100
        assert len(fake_gh.calls()) == 1

    def test_empty_result_is_an_empty_array(self, fake_gh):
        fake_gh.rules([_list_rule([])])
        assert _ok_json(_run(fake_gh.repo, "list")) == []

    def test_filters_by_label_server_side(self, fake_gh):
        """#120 AC2 — --label goes into the query; nodes are not re-filtered on label."""
        fake_gh.rules([_list_rule([_node(5, labels=("kind:task",)), _node(4, labels=("kind:task", "bug"))])])
        issues = _ok_json(_run(fake_gh.repo, "list", "--label", "kind:task"))
        assert "kind:task" in " ".join(_only(fake_gh.calls())["argv"])
        assert [i["ref"] for i in issues] == ["#5", "#4"]

    def test_filters_by_status_client_side(self, fake_gh):
        """#120 AC2 / Open question 1 — derived status filters the fetched nodes."""
        _write_project_env(fake_gh.repo)
        nodes = [
            _node(6, option=PROJECT_ENV["STATUS_IN_PROGRESS"], labels=("kind:task",)),
            _node(5, option=PROJECT_ENV["STATUS_TODO"], labels=("kind:task",)),
            _node(4, on_board=False, labels=("kind:task",)),
            _node(3, option="custom-column-id", labels=("kind:task",)),
            _node(2, option=PROJECT_ENV["STATUS_BLOCKED"], labels=("kind:task",)),
        ]
        fake_gh.rules([_list_rule(nodes)])
        todo = _ok_json(_run(fake_gh.repo, "list", "--status", "todo", "--label", "kind:task"))
        assert [i["ref"] for i in todo] == ["#5", "#4", "#3"]
        assert all(i["status"] == "todo" for i in todo)
        in_progress = _ok_json(_run(fake_gh.repo, "list", "--status", "in progress"))
        assert [i["ref"] for i in in_progress] == ["#6"]
        blocked = _ok_json(_run(fake_gh.repo, "list", "--status", "Blocked"))
        assert [i["ref"] for i in blocked] == ["#2"]

    def test_without_status_returns_every_open_issue_unfiltered(self, fake_gh):
        _write_project_env(fake_gh.repo)
        fake_gh.rules([_list_rule([_node(6, option=PROJECT_ENV["STATUS_IN_PROGRESS"]), _node(5)])])
        issues = _ok_json(_run(fake_gh.repo, "list"))
        assert [(i["ref"], i["status"]) for i in issues] == [("#6", "in progress"), ("#5", "todo")]

    @pytest.mark.parametrize("status", ["done", "Done"])
    def test_queries_closed_issues_for_status_done(self, fake_gh, status):
        """#120 — --status done asks GraphQL for CLOSED issues only."""
        fake_gh.rules([_list_rule([_node(9, state="CLOSED")])])
        issues = _ok_json(_run(fake_gh.repo, "list", "--status", status))
        joined = " ".join(_only(fake_gh.calls())["argv"])
        assert "CLOSED" in joined and "OPEN" not in joined, joined
        assert [(i["ref"], i["status"]) for i in issues] == [("#9", "done")]

    @pytest.mark.parametrize("extra", [[], ["--status", "todo"], ["--status", "in progress"], ["--status", "blocked"]],
                             ids=["no-status", "todo", "in-progress", "blocked"])
    def test_queries_open_issues_otherwise(self, fake_gh, extra):
        """#120 — every other status (and no status) asks for OPEN issues only."""
        fake_gh.rules([_list_rule([])])
        _ok_json(_run(fake_gh.repo, "list", *extra))
        joined = " ".join(_only(fake_gh.calls())["argv"])
        assert "OPEN" in joined and "CLOSED" not in joined, joined

    def test_surfaces_a_gh_api_graphql_failure_as_an_error_line_with_exit_1(self, fake_gh):
        fake_gh.rules([{"argv_prefix": ["api", "graphql"], "stderr": "HTTP 502: Bad Gateway\n", "exit": 1}])
        result = _run(fake_gh.repo, "list")
        assert (result.returncode, result.stdout, result.stderr) == (
            1, "", "Error: gh api graphql failed: HTTP 502: Bad Gateway\n")

    def test_unknown_status_is_rejected_before_any_gh_call(self, fake_gh):
        fake_gh.rules([_list_rule([])])
        result = _run(fake_gh.repo, "list", "--status", "bogus")
        assert (result.returncode, result.stdout, result.stderr) == (1, "", UNKNOWN_STATUS_MSG)
        assert fake_gh.calls() == []


# ---------------------------------------------------------------- edit


class TestEdit:
    """#120 — describe("github edit and comment"), edit half."""

    def test_adds_and_removes_labels_in_one_gh_issue_edit(self, fake_gh):
        """#120 AC3 — one edit call; untouched labels are neither removed nor re-set."""
        fake_gh.rules([_issue_rule(5, labels=("kind:task", "bug", "keep-me")), EDIT_OK])
        result = _run(fake_gh.repo, "edit", "#5", "--add-label", "high", "--add-label", "ui",
                      "--remove-label", "bug")
        assert (result.returncode, result.stdout, result.stderr) == (0, "updated:#5\n", "")
        call = _only(_writes(fake_gh))
        assert call["argv"][:3] == ["issue", "edit", "5"]
        assert sorted(_flag_values(call["argv"], "--add-label")) == ["high", "ui"]
        assert _flag_values(call["argv"], "--remove-label") == ["bug"]
        assert "--label" not in call["argv"]
        assert "--title" not in call["argv"] and "--body-file" not in call["argv"]

    def test_renames_the_issue_with_title(self, fake_gh):
        """#120 AC3 / Open question 2 — --title passes through to gh issue edit."""
        fake_gh.rules([_issue_rule(5), EDIT_OK])
        result = _run(fake_gh.repo, "edit", "5", "--title", "New name: with colon")
        assert (result.returncode, result.stdout, result.stderr) == (0, "updated:#5\n", "")
        call = _only(_writes(fake_gh))
        assert call["argv"][:3] == ["issue", "edit", "5"]
        assert _flag(call["argv"], "--title") == "New name: with colon"
        assert "--body-file" not in call["argv"]

    def test_sends_the_body_on_stdin(self, fake_gh):
        """#120 AC3 / I13 — --body-file - and the body in recorded stdin, never in argv."""
        body = "## What\nReplace the body\n\n- [ ] item with `code` and $VAR\n"
        fake_gh.rules([_issue_rule(5), EDIT_OK])
        result = _run(fake_gh.repo, "edit", "#5", "--body", body)
        assert (result.returncode, result.stdout, result.stderr) == (0, "updated:#5\n", "")
        call = _only(_writes(fake_gh))
        assert _flag(call["argv"], "--body-file") == "-"
        assert call["stdin"] == body
        assert "--body" not in call["argv"]
        assert not any("Replace the body" in arg for arg in call["argv"])

    def test_title_body_and_labels_together_in_one_call(self, fake_gh):
        fake_gh.rules([_issue_rule(5, labels=("old",)), EDIT_OK])
        result = _run(fake_gh.repo, "edit", "#5", "--title", "T2", "--body", "B2",
                      "--add-label", "new", "--remove-label", "old")
        assert (result.returncode, result.stdout) == (0, "updated:#5\n")
        call = _only(_writes(fake_gh))
        assert _flag(call["argv"], "--title") == "T2"
        assert _flag(call["argv"], "--body-file") == "-"
        assert call["stdin"] == "B2"
        assert _flag_values(call["argv"], "--add-label") == ["new"]
        assert _flag_values(call["argv"], "--remove-label") == ["old"]

    def test_skips_remove_for_a_label_the_issue_does_not_carry(self, fake_gh):
        """#120 I12 — only present labels are removed."""
        fake_gh.rules([_issue_rule(5, labels=("bug",)), EDIT_OK])
        result = _run(fake_gh.repo, "edit", "#5", "--remove-label", "absent", "--remove-label", "bug",
                      "--add-label", "x")
        assert (result.returncode, result.stdout) == (0, "updated:#5\n")
        call = _only(_writes(fake_gh))
        assert _flag_values(call["argv"], "--remove-label") == ["bug"]
        assert "absent" not in " ".join(call["argv"])

    def test_omits_remove_label_flag_when_every_remove_is_absent(self, fake_gh):
        """#120 I12 — no --remove-label at all when none of the names are present."""
        fake_gh.rules([_issue_rule(5, labels=("bug",)), EDIT_OK])
        result = _run(fake_gh.repo, "edit", "#5", "--remove-label", "absent", "--add-label", "x")
        assert (result.returncode, result.stdout) == (0, "updated:#5\n")
        call = _only(_writes(fake_gh))
        assert "--remove-label" not in call["argv"]
        assert _flag_values(call["argv"], "--add-label") == ["x"]

    def test_only_absent_removes_is_a_no_op_that_still_prints_updated(self, fake_gh):
        """#120 AC3 — an absent remove-label is a no-op: no gh issue edit, exit 0."""
        fake_gh.rules([_issue_rule(5, labels=("bug",))])
        result = _run(fake_gh.repo, "edit", "#5", "--remove-label", "absent")
        assert (result.returncode, result.stdout, result.stderr) == (0, "updated:#5\n", "")
        assert _writes(fake_gh) == []

    def test_errors_not_found_before_any_write(self, fake_gh):
        """#120 AC5 — unknown ref: 'Error: #N not found', exit 1, nothing written."""
        fake_gh.rules([_missing_rule(404), EDIT_OK])
        _not_found(_run(fake_gh.repo, "edit", "#404", "--title", "x", "--body", "y"), 404)
        assert _writes(fake_gh) == []

    def test_gh_issue_edit_failure_is_an_error_line(self, fake_gh):
        fake_gh.rules([_issue_rule(5), {"argv_prefix": ["issue", "edit"], "stderr": "HTTP 422\n", "exit": 1}])
        result = _run(fake_gh.repo, "edit", "#5", "--title", "x")
        assert result.returncode == 1
        assert result.stdout == ""
        assert result.stderr.startswith("Error: gh issue edit failed")
        assert "HTTP 422" in result.stderr


# ---------------------------------------------------------------- comment


class TestComment:
    """#120 — describe("github edit and comment"), comment half."""

    @pytest.mark.parametrize("ref", ["5", "#5"])
    def test_prints_commented(self, fake_gh, ref):
        """#120 AC4 — `comment #N --body MD` prints commented:#N."""
        fake_gh.rules([_issue_rule(5), COMMENT_OK])
        result = _run(fake_gh.repo, "comment", ref, "--body", "Looks good")
        assert (result.returncode, result.stdout, result.stderr) == (0, "commented:#5\n", "")
        call = _only(_writes(fake_gh))
        assert call["argv"][:3] == ["issue", "comment", "5"]

    def test_sends_the_comment_on_stdin(self, fake_gh):
        """#120 I13 — --body-file - and the text in recorded stdin, never in argv."""
        text = "## Review\n- point one\n```py\nprint('x')\n```\n"
        fake_gh.rules([_issue_rule(5), COMMENT_OK])
        result = _run(fake_gh.repo, "comment", "#5", "--body", text)
        assert result.returncode == 0, result.stderr
        call = _only(_writes(fake_gh))
        assert _flag(call["argv"], "--body-file") == "-"
        assert call["stdin"] == text
        assert "--body" not in call["argv"]
        assert not any("point one" in arg for arg in call["argv"])

    def test_errors_not_found_before_any_write(self, fake_gh):
        """#120 AC5 — unknown ref: 'Error: #N not found', exit 1, no comment posted."""
        fake_gh.rules([_missing_rule(404), COMMENT_OK])
        _not_found(_run(fake_gh.repo, "comment", "#404", "--body", "hi"), 404)
        assert _writes(fake_gh) == []

    def test_gh_issue_comment_failure_is_an_error_line(self, fake_gh):
        fake_gh.rules([_issue_rule(5), {"argv_prefix": ["issue", "comment"], "stderr": "HTTP 500\n", "exit": 1}])
        result = _run(fake_gh.repo, "comment", "#5", "--body", "hi")
        assert result.returncode == 1
        assert result.stdout == ""
        assert result.stderr.startswith("Error: ")
        assert "HTTP 500" in result.stderr
        assert _only(_writes(fake_gh))["argv"][:3] == ["issue", "comment", "5"]
