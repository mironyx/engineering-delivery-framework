"""Tests for the GitHub backend — `create`/`status` (issue #119) and `view`/`list`/`edit`/`comment` (#120).

Covers LLD v3 E3.1 §1.2: byte-identical parity with the pre-port gh-create-issue.sh and
gh-project-status.sh (I6, golden matrix in tests/fixtures/tracker_golden/), the new
`--type epic` and `--parent` flags, `--dry-run`, title quoting, the status port, the shims,
and the no-shell rule (I8). Every test drives the public CLI (`tracker.py` or a shim) under
the fake `gh` (tests/fixtures/fake_gh.py) and asserts on stdout, stderr, exit code and the
fake `gh` call log.

#120 (LLD §1.3, Open question 1): the seven-key issue JSON (I10), the single `list` query
capped at 100 (I11), absent remove-labels skipped (I12), bodies/comments on stdin (I13);
`list` is one `gh api graphql` call over `repository.issues`.

Port notes the assertions rely on (LLD §1.2 Part B):
- `gh issue create` / `gh issue edit` receive bodies via `--body-file -`, so body content is
  asserted from the call log's "stdin" field, never argv.
- Issue lookups use `gh api graphql -F owner=… -F name=… -F number=N -f query=…`; rules tell
  lookups apart with `argv_contains: ["number=N"]`.
"""

from __future__ import annotations

import ast
import importlib.util
import json
import pathlib
import subprocess
import sys
import time

import pytest

TESTS_DIR = pathlib.Path(__file__).resolve().parent
BIN_DIR = TESTS_DIR.parent / "plugins" / "edf" / "bin"
TRACKER = BIN_DIR / "tracker.py"
GITHUB_BACKEND = BIN_DIR / "_tracker_github.py"
CREATE_SHIM = BIN_DIR / "gh-create-issue.sh"
STATUS_SHIM = BIN_DIR / "gh-project-status.sh"
GOLDEN_DIR = TESTS_DIR / "fixtures" / "tracker_golden"

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

TITLE = "Add widget"
BODY = "Line one\nLine two"
BASE = ["--title", TITLE, "--body", BODY]
UNKNOWN_STATUS_MSG = "Error: unknown status 'bogus'. Use: todo | blocked | \"in progress\" | done"
PLACEHOLDER = "- [ ] (to be filled by edf:architect)"
KEYS = ["ref", "title", "body", "labels", "status", "parent", "children"]
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
    items = [{"id": "PVTI_item", "project": {"id": project_id}, "fieldValues": {"nodes": field_values}}]
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


NO_DUP = {"argv_prefix": ["issue", "list"], "stdout": ""}
CREATED = {"argv_prefix": ["issue", "create"], "stdout": "https://github.com/owner/repo/issues/42\n"}
EDIT_OK = {"argv_prefix": ["issue", "edit"], "stdout": ""}
COMMENT_OK = {"argv_prefix": ["issue", "comment"], "stdout": "https://github.com/owner/repo/issues/5#issuecomment-1\n"}
ITEM_ADD_OK = {"argv_prefix": ["project", "item-add"], "stdout": '{"id":"PVTI_new"}\n'}
ITEM_EDIT_OK = {"argv_prefix": ["project", "item-edit"], "stdout": ""}
ON_BOARD = {"argv_prefix": ["api", "graphql"],
            "stdout": json.dumps({"data": {"repository": {"issue": _node(42)}}}) + "\n"}


def _list_rule(nodes: list[dict]) -> dict:
    """The single repository.issues query `list` makes (#120)."""
    response = json.dumps({"data": {"repository": {"issues": {"nodes": nodes}}}}) + "\n"
    return {"argv_prefix": ["api", "graphql"], "stdout": response}


def _dup(number: int) -> dict:
    return {"argv_prefix": ["issue", "list"], "stdout": f"{number}\n"}


# ---------------------------------------------------------------- helpers


def _run(cwd: pathlib.Path, *args: str, timeout: float = 30) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, str(TRACKER), *args], cwd=cwd, capture_output=True, text=True,
                          timeout=timeout, stdin=subprocess.DEVNULL)


def _shim(cwd: pathlib.Path, script: pathlib.Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["bash", str(script), *args], cwd=cwd, capture_output=True, text=True, timeout=30,
                          stdin=subprocess.DEVNULL)


def _write_project_env(root: pathlib.Path, text: str | None = None) -> pathlib.Path:
    (root / ".github").mkdir(exist_ok=True)
    path = root / ".github" / "project.env"
    path.write_text(text if text is not None else "".join(f"{k}={v}\n" for k, v in PROJECT_ENV.items()),
                    encoding="utf-8")
    return path


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


def _ok_json(result: subprocess.CompletedProcess):
    assert result.returncode == 0, (result.stdout, result.stderr)
    assert result.stderr == ""
    return json.loads(result.stdout)


def _not_found(result: subprocess.CompletedProcess, number: int) -> None:
    assert (result.returncode, result.stdout, result.stderr) == (1, "", f"Error: #{number} not found\n")


def _only(calls: list[dict]) -> dict:
    assert len(calls) == 1, calls
    return calls[0]


def _ok(result: subprocess.CompletedProcess, stdout: str, stderr: str = "") -> None:
    assert (result.returncode, result.stdout, result.stderr) == (0, stdout, stderr)


def _epic_body_written(fake_gh, epic: int = 7) -> str:
    call = _only(_calls(fake_gh, "issue", "edit", str(epic)))
    assert "--body-file" in call["argv"] and _flag(call["argv"], "--body-file") == "-", call["argv"]
    return call["stdin"]


# ---------------------------------------------------------------- golden parity (I6)


def _golden_params() -> list:
    params = []
    for path in sorted(GOLDEN_DIR.glob("*.json")):
        golden = json.loads(path.read_text(encoding="utf-8"))
        params.append(pytest.param(golden, "shim", id=f"{path.stem}-shim"))
        if golden["tracker_argv"] is not None:
            params.append(pytest.param(golden, "port", id=f"{path.stem}-tracker"))
    return params


GOLDEN_PARAMS = _golden_params()


def test_golden_matrix_is_recorded():
    """#119 — the LLD's scenario matrix (12 create + 15 status) is on disk."""
    names = {p.stem for p in GOLDEN_DIR.glob("*.json")}
    assert len([n for n in names if n.startswith("create-")]) == 12, names
    assert len([n for n in names if n.startswith("status-")]) == 15, names


@pytest.mark.parametrize(("golden", "mode"), GOLDEN_PARAMS)
def test_golden_parity(golden, mode, fake_gh, tmp_path):
    """#119 I6 / AC1 — shim and `tracker.py` reproduce the pre-port bash bytes."""
    fake_gh.rules(golden["rules"])
    base = tmp_path / f"golden-{mode}"
    base.mkdir()
    cwd = recorder.prepare_cwd(base, golden["setup"])
    script = BIN_DIR / golden["script"]
    if mode == "shim":
        cmd = ["bash", str(script), *golden["argv"]]
    else:
        cmd = [sys.executable, str(TRACKER), *golden["tracker_argv"]]
    result = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, timeout=60, stdin=subprocess.DEVNULL)

    def expand(text: str) -> str:
        return text.replace("{script}", str(script)).replace("{cwd}", str(cwd))

    expected_stdout = expand(golden.get("port_stdout", golden["stdout"]))
    expected_stderr = expand(golden.get("port_stderr", golden["stderr"]))
    assert result.returncode == golden["exit"], (result.stdout, result.stderr)
    if golden["compare"] == "first_stderr_line":
        first = (result.stderr.splitlines() or [""])[0]
        assert first == expected_stderr.splitlines()[0], result.stderr
    else:
        assert result.stdout == expected_stdout
        assert result.stderr == expected_stderr


# ---------------------------------------------------------------- create — parity behaviour


class TestCreateParity:
    """#119 — describe("github create — parity")."""

    def test_prints_created_after_issue_create_returns_url(self, fake_gh):
        fake_gh.rules([NO_DUP, CREATED])
        _ok(_run(fake_gh.repo, "create", *BASE), "created:42\n")
        call = _only(_calls(fake_gh, "issue", "create"))
        assert _flag(call["argv"], "--title") == TITLE
        assert _flag(call["argv"], "--body-file") == "-"
        assert call["stdin"] == BODY
        assert "--label" not in call["argv"]

    def test_passes_labels_as_one_comma_separated_label_flag(self, fake_gh):
        fake_gh.rules([NO_DUP, CREATED])
        _ok(_run(fake_gh.repo, "create", *BASE, "--labels", "bug,high-priority"), "created:42\n")
        assert _flag(_only(_calls(fake_gh, "issue", "create"))["argv"], "--label") == "bug,high-priority"

    def test_dedup_search_is_open_in_title_query(self, fake_gh):
        fake_gh.rules([NO_DUP, CREATED])
        _run(fake_gh.repo, "create", *BASE)
        call = _only(_calls(fake_gh, "issue", "list"))
        assert _flag(call["argv"], "--state") == "open"
        assert _flag(call["argv"], "--search") == f'in:title "{TITLE}"'

    def test_prints_exists_and_creates_nothing_when_in_title_search_hits(self, fake_gh):
        fake_gh.rules([_dup(17)])
        _ok(_run(fake_gh.repo, "create", *BASE), "exists:17\n")
        assert _writes(fake_gh) == []

    def test_exists_takes_first_line_of_search_output(self, fake_gh):
        fake_gh.rules([{"argv_prefix": ["issue", "list"], "stdout": "17\n18\n"}])
        _ok(_run(fake_gh.repo, "create", *BASE), "exists:17\n")

    def test_failed_dedup_search_is_swallowed_and_create_proceeds(self, fake_gh):
        fake_gh.rules([{"argv_prefix": ["issue", "list"], "stderr": "HTTP 502\n", "exit": 1}, CREATED])
        _ok(_run(fake_gh.repo, "create", *BASE), "created:42\n")

    @pytest.mark.parametrize("labels", [None, "bug,high-priority"], ids=["no-labels", "labels"])
    def test_dry_run_matches_golden_and_writes_nothing(self, fake_gh, labels):
        fake_gh.rules([NO_DUP])
        extra = ["--labels", labels] if labels else []
        result = _run(fake_gh.repo, "create", *BASE, *extra, "--dry-run")
        _ok(result, "dry-run: would create issue\n"
                    f"  title:  {TITLE}\n"
                    f"  labels: {labels or '<none>'}\n"
                    "  board:  false (status: todo)\n"
                    "  body:\n"
                    "    Line one\n"
                    "    Line two\n")
        assert _writes(fake_gh) == []

    def test_dry_run_dedup_hit_prints_exists(self, fake_gh):
        fake_gh.rules([_dup(17)])
        _ok(_run(fake_gh.repo, "create", *BASE, "--dry-run"), "exists:17\n")
        assert _writes(fake_gh) == []

    def test_warns_and_still_prints_created_when_board_add_fails(self, fake_gh):
        _write_project_env(fake_gh.repo)
        fake_gh.rules([NO_DUP, CREATED, {"argv_prefix": ["project", "item-add"], "stderr": "boom\n", "exit": 1}])
        _ok(_run(fake_gh.repo, "create", *BASE, "--add-to-board"), "created:42\n",
            "Warning: failed to add #42 to board\n")

    def test_warns_and_still_creates_when_project_env_missing(self, fake_gh):
        fake_gh.rules([NO_DUP, CREATED])
        _ok(_run(fake_gh.repo, "create", *BASE, "--add-to-board"), "created:42\n",
            "Warning: failed to add #42 to board\n")
        assert len(_calls(fake_gh, "issue", "create")) == 1

    def test_warns_when_board_set_fails(self, fake_gh):
        _write_project_env(fake_gh.repo)
        fake_gh.rules([NO_DUP, CREATED, ITEM_ADD_OK,
                       {"argv_prefix": ["project", "item-edit"], "stderr": "nope\n", "exit": 1}])
        _ok(_run(fake_gh.repo, "create", *BASE, "--add-to-board"), "created:42\n",
            "Warning: failed to add #42 to board\n")

    def test_add_to_board_adds_then_sets_board_status(self, fake_gh):
        _write_project_env(fake_gh.repo)
        fake_gh.rules([NO_DUP, CREATED, ITEM_ADD_OK, ITEM_EDIT_OK])
        result = _run(fake_gh.repo, "create", *BASE, "--add-to-board", "--board-status", "In Progress")
        _ok(result, "created:42\n")
        add = _only(_calls(fake_gh, "project", "item-add"))
        assert _flag(add["argv"], "--url") == "https://github.com/owner/repo/issues/42"
        edit = _only(_calls(fake_gh, "project", "item-edit"))
        assert _flag(edit["argv"], "--id") == "PVTI_new"
        assert _flag(edit["argv"], "--single-select-option-id") == PROJECT_ENV["STATUS_IN_PROGRESS"]

    def test_issue_create_failure_reports_gh_output(self, fake_gh):
        fake_gh.rules([NO_DUP, {"argv_prefix": ["issue", "create"], "stderr": "HTTP 422: Validation Failed\n",
                                "exit": 1}])
        result = _run(fake_gh.repo, "create", *BASE)
        assert result.returncode == 1
        assert result.stdout == ""
        assert result.stderr.startswith("Error: gh issue create failed: HTTP 422: Validation Failed")

    def test_fails_when_title_is_missing(self, fake_gh):
        result = _run(fake_gh.repo, "create", "--body", "B")
        assert (result.returncode, result.stdout, result.stderr) == (1, "", "Error: --title is required\n")
        assert fake_gh.calls() == []


# ---------------------------------------------------------------- create — new flags


class TestCreateType:
    """#119 AC2 — `--type epic` adds the `epic` label once and changes nothing else."""

    @pytest.mark.parametrize(("labels", "expected"), [
        (None, "epic"),
        ("bug", "bug,epic"),
        ("epic,bug", "epic,bug"),
        ("bug,epic", "bug,epic"),
    ], ids=["no-labels", "appends", "already-first", "already-last"])
    def test_epic_label(self, fake_gh, labels, expected):
        fake_gh.rules([NO_DUP, CREATED])
        extra = ["--labels", labels] if labels else []
        _ok(_run(fake_gh.repo, "create", *BASE, *extra, "--type", "epic"), "created:42\n")
        call = _only(_calls(fake_gh, "issue", "create"))
        assert _flag(call["argv"], "--label") == expected
        assert _flag(call["argv"], "--label").split(",").count("epic") == 1

    def test_epic_changes_nothing_else(self, fake_gh):
        fake_gh.rules([NO_DUP, CREATED])
        _ok(_run(fake_gh.repo, "create", *BASE, "--type", "epic"), "created:42\n")
        call = _only(_calls(fake_gh, "issue", "create"))
        assert _flag(call["argv"], "--title") == TITLE
        assert call["stdin"] == BODY
        assert [c["argv"][:2] for c in fake_gh.calls()] == [["issue", "list"], ["issue", "create"]]

    def test_task_type_adds_no_label(self, fake_gh):
        fake_gh.rules([NO_DUP, CREATED])
        _ok(_run(fake_gh.repo, "create", *BASE, "--type", "task"), "created:42\n")
        assert "--label" not in _only(_calls(fake_gh, "issue", "create"))["argv"]

    def test_epic_dry_run_shows_epic_label(self, fake_gh):
        fake_gh.rules([NO_DUP])
        result = _run(fake_gh.repo, "create", *BASE, "--labels", "bug", "--type", "epic", "--dry-run")
        assert result.returncode == 0, result.stderr
        assert "  labels: bug,epic\n" in result.stdout
        assert _writes(fake_gh) == []

    def test_unknown_type_is_an_error(self, fake_gh):
        fake_gh.rules([NO_DUP, CREATED])
        result = _run(fake_gh.repo, "create", *BASE, "--type", "story")
        assert result.returncode == 1
        assert result.stdout == ""
        assert result.stderr.startswith("Error: ")
        assert "story" in result.stderr, result.stderr  # names the rejected value
        assert len(result.stderr.strip().splitlines()) == 1, result.stderr
        assert "Traceback" not in result.stderr
        assert _writes(fake_gh) == []


class TestCreateParent:
    """#119 AC3, AC4, I9 — `--parent` validation, epic checklist and task back-link."""

    @pytest.mark.parametrize("ref", ["#7", "7"])
    def test_errors_parent_not_found_and_writes_nothing(self, fake_gh, ref):
        fake_gh.rules([_missing_rule(7), NO_DUP, CREATED, EDIT_OK])
        result = _run(fake_gh.repo, "create", *BASE, "--parent", ref)
        assert (result.returncode, result.stdout, result.stderr) == (1, "", "Error: parent #7 not found\n")
        assert _writes(fake_gh) == []

    def test_parent_not_found_on_dry_run_errors_too(self, fake_gh):
        fake_gh.rules([_missing_rule(7), NO_DUP])
        result = _run(fake_gh.repo, "create", *BASE, "--parent", "#7", "--dry-run")
        assert (result.returncode, result.stdout, result.stderr) == (1, "", "Error: parent #7 not found\n")

    def test_parent_not_found_writes_nothing_even_on_dedup_hit(self, fake_gh):
        fake_gh.rules([_missing_rule(7), _dup(17), EDIT_OK])
        result = _run(fake_gh.repo, "create", *BASE, "--parent", "#7")
        assert (result.returncode, result.stderr) == (1, "Error: parent #7 not found\n")
        assert _writes(fake_gh) == []

    def test_parent_lookup_failure_other_than_not_found_writes_nothing(self, fake_gh):
        fake_gh.rules([{"argv_prefix": ["api", "graphql"], "stderr": "HTTP 502: Bad Gateway\n", "exit": 1},
                       NO_DUP, CREATED, EDIT_OK])
        result = _run(fake_gh.repo, "create", *BASE, "--parent", "#7")
        assert result.returncode == 1
        assert result.stderr.startswith("Error: gh api graphql failed")
        assert "Traceback" not in result.stderr
        assert _writes(fake_gh) == []

    def test_invalid_parent_reference_is_an_error(self, fake_gh):
        fake_gh.rules([NO_DUP, CREATED])
        result = _run(fake_gh.repo, "create", *BASE, "--parent", "epic-seven")
        assert (result.returncode, result.stderr) == (1, "Error: invalid GitHub reference 'epic-seven'\n")
        assert _writes(fake_gh) == []

    def test_prepends_parent_epic_section_to_new_task_body(self, fake_gh):
        fake_gh.rules([_issue_rule(7, title="Epic", body="## Tasks\n" + PLACEHOLDER + "\n"), NO_DUP, CREATED,
                       EDIT_OK])
        _ok(_run(fake_gh.repo, "create", *BASE, "--parent", "#7"), "created:42\n")
        assert _only(_calls(fake_gh, "issue", "create"))["stdin"] == f"## Parent epic\n#7\n\n{BODY}"

    def test_keeps_task_body_when_parent_epic_section_present(self, fake_gh):
        body = "## Parent epic\n#7\n\n## What\nStuff"
        fake_gh.rules([_issue_rule(7, body="## Tasks\n"), NO_DUP, CREATED, EDIT_OK])
        _ok(_run(fake_gh.repo, "create", "--title", TITLE, "--body", body, "--parent", "7"), "created:42\n")
        stdin = _only(_calls(fake_gh, "issue", "create"))["stdin"]
        assert stdin == body
        assert stdin.count("## Parent epic") == 1

    def test_appends_checklist_line_replacing_architect_placeholder(self, fake_gh):
        epic_body = f"## Summary\nEpic text\n\n## Tasks\n{PLACEHOLDER}\n\n## Notes\nN"
        fake_gh.rules([_issue_rule(7, title="Epic", body=epic_body), NO_DUP, CREATED, EDIT_OK])
        _ok(_run(fake_gh.repo, "create", *BASE, "--parent", "#7"), "created:42\n")
        assert _epic_body_written(fake_gh) == f"## Summary\nEpic text\n\n## Tasks\n- [ ] #42 — {TITLE}\n\n## Notes\nN"

    def test_inserts_after_last_checklist_line_in_tasks_section(self, fake_gh):
        epic_body = "### Tasks\n- [ ] #10 — Other\n- [x] #11 — Done one\n\n## Notes\n- [ ] not a task\n"
        fake_gh.rules([_issue_rule(7, body=epic_body), NO_DUP, CREATED, EDIT_OK])
        _ok(_run(fake_gh.repo, "create", *BASE, "--parent", "#7"), "created:42\n")
        assert _epic_body_written(fake_gh) == (
            "### Tasks\n- [ ] #10 — Other\n- [x] #11 — Done one\n"
            f"- [ ] #42 — {TITLE}\n\n## Notes\n- [ ] not a task\n"
        )

    def test_inserts_directly_under_empty_tasks_heading(self, fake_gh):
        epic_body = "## Tasks\n\n## Notes\nN"
        fake_gh.rules([_issue_rule(7, body=epic_body), NO_DUP, CREATED, EDIT_OK])
        _ok(_run(fake_gh.repo, "create", *BASE, "--parent", "#7"), "created:42\n")
        written = _epic_body_written(fake_gh)
        assert written.startswith(f"## Tasks\n- [ ] #42 — {TITLE}\n")
        assert written.endswith("## Notes\nN")
        assert written.count("#42") == 1

    def test_appends_tasks_section_when_epic_has_none(self, fake_gh):
        epic_body = "## Summary\nEpic text"
        fake_gh.rules([_issue_rule(7, body=epic_body), NO_DUP, CREATED, EDIT_OK])
        _ok(_run(fake_gh.repo, "create", *BASE, "--parent", "#7"), "created:42\n")
        assert _epic_body_written(fake_gh) == f"{epic_body}\n### Tasks\n- [ ] #42 — {TITLE}\n"

    def test_replaces_matching_t_line_instead_of_appending(self, fake_gh):
        epic_body = f"## Tasks\n- [ ] T1 — Other thing\n- [ ] T2 — {TITLE}\n- [ ] T3 — Later\n"
        fake_gh.rules([_issue_rule(7, body=epic_body), NO_DUP, CREATED, EDIT_OK])
        _ok(_run(fake_gh.repo, "create", *BASE, "--parent", "#7"), "created:42\n")
        assert _epic_body_written(fake_gh) == (
            f"## Tasks\n- [ ] T1 — Other thing\n- [ ] #42 — {TITLE}\n- [ ] T3 — Later\n"
        )

    def test_t_line_with_different_title_is_not_replaced(self, fake_gh):
        epic_body = f"## Tasks\n- [ ] T2 — {TITLE} v2\n"
        fake_gh.rules([_issue_rule(7, body=epic_body), NO_DUP, CREATED, EDIT_OK])
        _ok(_run(fake_gh.repo, "create", *BASE, "--parent", "#7"), "created:42\n")
        assert _epic_body_written(fake_gh) == f"## Tasks\n- [ ] T2 — {TITLE} v2\n- [ ] #42 — {TITLE}\n"

    def test_t_line_is_preferred_over_placeholder(self, fake_gh):
        epic_body = f"## Tasks\n{PLACEHOLDER}\n- [ ] T1 — {TITLE}\n"
        fake_gh.rules([_issue_rule(7, body=epic_body), NO_DUP, CREATED, EDIT_OK])
        _ok(_run(fake_gh.repo, "create", *BASE, "--parent", "#7"), "created:42\n")
        assert _epic_body_written(fake_gh) == f"## Tasks\n{PLACEHOLDER}\n- [ ] #42 — {TITLE}\n"

    def test_writes_epic_body_through_stdin(self, fake_gh):
        fake_gh.rules([_issue_rule(7, body="## Tasks\n"), NO_DUP, CREATED, EDIT_OK])
        _run(fake_gh.repo, "create", *BASE, "--parent", "#7")
        call = _only(_calls(fake_gh, "issue", "edit"))
        assert call["argv"][:3] == ["issue", "edit", "7"]
        assert _flag(call["argv"], "--body-file") == "-"
        assert "--body" not in call["argv"]

    def test_link_failure_warns_and_still_prints_created(self, fake_gh):
        fake_gh.rules([_issue_rule(7, body="## Tasks\n"), NO_DUP, CREATED,
                       {"argv_prefix": ["issue", "edit", "7"], "stderr": "HTTP 403\n", "exit": 1}])
        _ok(_run(fake_gh.repo, "create", *BASE, "--parent", "#7"), "created:42\n",
            "Warning: failed to link #42 to epic #7: failed to update epic #7: HTTP 403\n")

    def test_parent_lookup_needs_no_project_scope(self, fake_gh):
        # PR #125 review: projectItems needs read:project; the parent lookup must not ask for it.
        fake_gh.rules([_issue_rule(7, body="## Tasks\n"), NO_DUP, CREATED, EDIT_OK])
        _ok(_run(fake_gh.repo, "create", *BASE, "--parent", "#7"), "created:42\n")
        lookup = _only(_calls(fake_gh, "api", "graphql"))
        assert "projectItems" not in _flag(lookup["argv"], "-f") + " ".join(lookup["argv"])

    def test_dedup_hit_links_existing_issue_both_ways(self, fake_gh):
        fake_gh.rules([_issue_rule(7, body=f"## Tasks\n{PLACEHOLDER}\n"), _issue_rule(17, title=TITLE, body="Old"),
                       _dup(17), EDIT_OK])
        _ok(_run(fake_gh.repo, "create", *BASE, "--parent", "#7"), "exists:17\n")
        assert _calls(fake_gh, "issue", "create") == []
        assert _epic_body_written(fake_gh) == f"## Tasks\n- [ ] #17 — {TITLE}\n"
        task = _only(_calls(fake_gh, "issue", "edit", "17"))
        assert _flag(task["argv"], "--body-file") == "-"
        assert task["stdin"] == "## Parent epic\n#7\n\nOld"

    def test_dedup_hit_task_write_failure_names_gh_error(self, fake_gh):
        # PR #125 review round 2: the existing-issue body write carries gh's stderr too.
        fake_gh.rules([_issue_rule(7, body=f"## Tasks\n{PLACEHOLDER}\n"), _issue_rule(17, title=TITLE, body="Old"),
                       _dup(17), {"argv_prefix": ["issue", "edit", "17"], "stderr": "HTTP 403\n", "exit": 1}])
        result = _run(fake_gh.repo, "create", *BASE, "--parent", "#7")
        _ok(result, "exists:17\n", "Warning: failed to link #17 to epic #7: failed to update issue #17: HTTP 403\n")

    def test_dedup_near_match_is_not_linked(self, fake_gh):
        # PR #125 review: in:title is fuzzy; an issue whose title only contains ours is left alone.
        fake_gh.rules([_issue_rule(7, body=f"## Tasks\n{PLACEHOLDER}\n"),
                       _issue_rule(17, title=f"{TITLE} rate limiting", body="Old"), _dup(17), EDIT_OK])
        result = _run(fake_gh.repo, "create", *BASE, "--parent", "#7")
        _ok(result, "exists:17\n", "Warning: failed to link #17 to epic #7: issue #17 title differs\n")
        assert _writes(fake_gh) == []

    @pytest.mark.parametrize("box", [" ", "x", "X"])
    def test_does_not_duplicate_checklist_line_on_exists_rerun(self, fake_gh, box):
        epic_body = f"## Tasks\n- [{box}] #17 — {TITLE}\n"
        fake_gh.rules([_issue_rule(7, body=epic_body), _issue_rule(17, title=TITLE, body=f"## Parent epic\n#7\n\n{BODY}"),
                       _dup(17), EDIT_OK])
        _ok(_run(fake_gh.repo, "create", *BASE, "--parent", "#7"), "exists:17\n")
        for call in _calls(fake_gh, "issue", "edit", "7"):
            assert call["stdin"].count("#17") == 1, call["stdin"]
        for call in _calls(fake_gh, "issue", "edit", "17"):
            assert call["stdin"].count("## Parent epic") == 1, call["stdin"]
        assert _calls(fake_gh, "issue", "create") == []

    def test_checklist_match_is_number_exact(self, fake_gh):
        # "#170" in the epic must not count as "#17" already being linked.
        epic_body = "## Tasks\n- [ ] #170 — Something else\n"
        fake_gh.rules([_issue_rule(7, body=epic_body), _issue_rule(17, title=TITLE, body=f"## Parent epic\n#7\n\n{BODY}"),
                       _dup(17), EDIT_OK])
        _ok(_run(fake_gh.repo, "create", *BASE, "--parent", "#7"), "exists:17\n")
        assert _epic_body_written(fake_gh) == f"## Tasks\n- [ ] #170 — Something else\n- [ ] #17 — {TITLE}\n"

    def test_prints_parent_line_on_dry_run_and_writes_nothing(self, fake_gh):
        fake_gh.rules([_issue_rule(7, body="## Tasks\n"), NO_DUP])
        result = _run(fake_gh.repo, "create", *BASE, "--labels", "bug", "--parent", "#7", "--dry-run")
        _ok(result, "dry-run: would create issue\n"
                    f"  title:  {TITLE}\n"
                    "  labels: bug\n"
                    "  parent: #7\n"
                    "  board:  false (status: todo)\n"
                    "  body:\n"
                    "    Line one\n"
                    "    Line two\n")
        assert len(_calls(fake_gh, "api", "graphql")) >= 1  # parent lookup still runs
        assert len(_calls(fake_gh, "issue", "list")) == 1  # dedup still runs
        assert _writes(fake_gh) == []

    def test_dry_run_dedup_hit_with_parent_writes_nothing(self, fake_gh):
        fake_gh.rules([_issue_rule(7, body=f"## Tasks\n{PLACEHOLDER}\n"), _issue_rule(17, title=TITLE, body="Old"), _dup(17),
                       EDIT_OK])
        _ok(_run(fake_gh.repo, "create", *BASE, "--parent", "#7", "--dry-run"), "exists:17\n")
        assert _writes(fake_gh) == []

    def test_parent_and_board_together(self, fake_gh):
        _write_project_env(fake_gh.repo)
        fake_gh.rules([_issue_rule(7, body="## Tasks\n"), NO_DUP, CREATED, EDIT_OK, ITEM_ADD_OK, ITEM_EDIT_OK])
        _ok(_run(fake_gh.repo, "create", *BASE, "--parent", "#7", "--add-to-board"), "created:42\n")
        assert len(_calls(fake_gh, "project", "item-add")) == 1
        assert f"- [ ] #42 — {TITLE}" in _epic_body_written(fake_gh)


class TestCreateQuoting:
    """#119 AC5 — titles with `"`, `\\` and `'` reach gh as one intact argv element."""

    TRICKY = "Fix \"quoted\" path C:\\temp\\x and it's $HOME `id` ; rm -rf"

    def test_passes_title_with_quotes_and_backslashes_as_single_argv_element(self, fake_gh):
        fake_gh.rules([NO_DUP, CREATED])
        _ok(_run(fake_gh.repo, "create", "--title", self.TRICKY, "--body", BODY), "created:42\n")
        assert _flag(_only(_calls(fake_gh, "issue", "create"))["argv"], "--title") == self.TRICKY
        search = _flag(_only(_calls(fake_gh, "issue", "list"))["argv"], "--search")
        assert search == f'in:title "{self.TRICKY}"'

    def test_tricky_title_through_shim(self, fake_gh):
        fake_gh.rules([NO_DUP, CREATED])
        _ok(_shim(fake_gh.repo, CREATE_SHIM, "--title", self.TRICKY, "--body", BODY), "created:42\n")
        assert _flag(_only(_calls(fake_gh, "issue", "create"))["argv"], "--title") == self.TRICKY

    def test_tricky_title_lands_intact_in_epic_checklist(self, fake_gh):
        fake_gh.rules([_issue_rule(7, body="## Tasks\n"), NO_DUP, CREATED, EDIT_OK])
        _ok(_run(fake_gh.repo, "create", "--title", self.TRICKY, "--body", BODY, "--parent", "#7"), "created:42\n")
        assert _epic_body_written(fake_gh) == f"## Tasks\n- [ ] #42 — {self.TRICKY}\n"

    def test_tricky_title_matches_t_line_literally(self, fake_gh):
        # Regex metacharacters in the title must not break or widen the T-line match.
        title = "Parse (a|b) [x] .* + ?"
        fake_gh.rules([_issue_rule(7, body=f"## Tasks\n- [ ] T1 — Parse a\n- [ ] T2 — {title}\n"), NO_DUP, CREATED,
                       EDIT_OK])
        _ok(_run(fake_gh.repo, "create", "--title", title, "--body", BODY, "--parent", "#7"), "created:42\n")
        assert _epic_body_written(fake_gh) == f"## Tasks\n- [ ] T1 — Parse a\n- [ ] #42 — {title}\n"


# ---------------------------------------------------------------- status


class TestStatus:
    """#119 — describe("github status — parity") and Story 1.5 AC7."""

    def test_prints_issue_in_progress_after_item_edit(self, fake_gh):
        _write_project_env(fake_gh.repo)
        fake_gh.rules([ON_BOARD, ITEM_EDIT_OK])
        _ok(_run(fake_gh.repo, "status", "42", "in progress"), "Issue #42 → in progress\n")
        edit = _only(_calls(fake_gh, "project", "item-edit"))
        assert _flag(edit["argv"], "--project-id") == "PVT_abc"
        assert _flag(edit["argv"], "--id") == "PVTI_item"
        assert _flag(edit["argv"], "--field-id") == "PVTSSF_xyz"
        assert _flag(edit["argv"], "--single-select-option-id") == "in-progress-id"

    def test_lookup_uses_project_env_repo(self, fake_gh):
        _write_project_env(fake_gh.repo)
        fake_gh.rules([ON_BOARD, ITEM_EDIT_OK])
        _run(fake_gh.repo, "status", "42", "todo")
        argv = _only(_calls(fake_gh, "api", "graphql"))["argv"]
        assert {"owner=owner", "name=repo", "number=42"} <= set(argv), argv

    def test_accepts_hash_reference(self, fake_gh):
        _write_project_env(fake_gh.repo)
        fake_gh.rules([ON_BOARD, ITEM_EDIT_OK])
        _ok(_run(fake_gh.repo, "status", "#42", "done"), "Issue #42 → done\n")
        assert "number=42" in _only(_calls(fake_gh, "api", "graphql"))["argv"]

    @pytest.mark.parametrize(("raw", "option"), [
        ("In Progress", "in-progress-id"), ("DONE", "done-id"), ("Blocked", "blocked-id"), ("todo", "todo-id"),
    ])
    def test_echoes_status_exactly_as_caller_passed_it(self, fake_gh, raw, option):
        _write_project_env(fake_gh.repo)
        fake_gh.rules([ON_BOARD, ITEM_EDIT_OK])
        _ok(_run(fake_gh.repo, "status", "42", raw), f"Issue #42 → {raw}\n")
        assert _flag(_only(_calls(fake_gh, "project", "item-edit"))["argv"], "--single-select-option-id") == option

    def test_prints_not_on_board_error_on_stdout_with_exit_1(self, fake_gh):
        _write_project_env(fake_gh.repo)
        fake_gh.rules([{"argv_prefix": ["api", "graphql"],
                        "stdout": json.dumps({"data": {"repository": {"issue": _node(42, project_id="PVT_other")}}})}])
        result = _run(fake_gh.repo, "status", "42", "todo")
        assert (result.returncode, result.stdout, result.stderr) == (
            1, "Error: issue #42 not found on the project board\n", "")
        assert _writes(fake_gh) == []

    def test_adds_then_sets_status_for_add_to_board(self, fake_gh):
        _write_project_env(fake_gh.repo)
        fake_gh.rules([ITEM_ADD_OK, ITEM_EDIT_OK])
        _ok(_run(fake_gh.repo, "status", "42", "blocked", "--add-to-board"), "Issue #42 → added → blocked\n")
        assert [c["argv"][:2] for c in fake_gh.calls()] == [["project", "item-add"], ["project", "item-edit"]]
        add = fake_gh.calls()[0]["argv"]
        assert add[2] == "4"
        assert _flag(add, "--owner") == "owner"
        assert _flag(add, "--url") == "https://github.com/owner/repo/issues/42"
        assert _flag(add, "--format") == "json"
        edit = fake_gh.calls()[1]["argv"]
        assert _flag(edit, "--id") == "PVTI_new"
        assert _flag(edit, "--single-select-option-id") == "blocked-id"

    def test_errors_on_missing_project_env_naming_the_path(self, fake_gh):
        result = _run(fake_gh.repo, "status", "42", "todo")
        assert result.returncode == 1
        assert result.stdout == ""
        assert result.stderr == (
            f"Error: config file not found: {fake_gh.repo}/.github/project.env\n"
            "Create it with REPO, PROJECT_NUMBER, PROJECT_ID, FIELD_ID, and STATUS_* values.\n"
            "See this script's header for the format.\n"
        )
        assert fake_gh.calls() == []

    def test_errors_outside_a_git_repository(self, fake_gh, tmp_path):
        outside = tmp_path / "not-a-repo"
        outside.mkdir()
        result = _run(outside, "status", "42", "todo")
        assert (result.returncode, result.stdout, result.stderr) == (
            1, "", "Error: not inside a git repository — run from your project directory\n")
        assert fake_gh.calls() == []

    def test_errors_on_missing_config_var(self, fake_gh):
        path = _write_project_env(fake_gh.repo, "".join(f"{k}={v}\n" for k, v in PROJECT_ENV.items()
                                                        if k != "STATUS_DONE"))
        result = _run(fake_gh.repo, "status", "42", "todo")
        assert (result.returncode, result.stdout, result.stderr) == (
            1, "", f"Error: STATUS_DONE not set in {path}\n")

    def test_loads_project_env_with_crlf_comments_and_quotes(self, fake_gh):
        lines = ["# board config", ""] + [f'{k}="{v}"' if k == "PROJECT_ID" else f"  {k} = {v}  "
                                         for k, v in PROJECT_ENV.items()]
        _write_project_env(fake_gh.repo, "\r\n".join(lines) + "\r\n")
        fake_gh.rules([ON_BOARD, ITEM_EDIT_OK])
        _ok(_run(fake_gh.repo, "status", "42", "todo"), "Issue #42 → todo\n")
        edit = _only(_calls(fake_gh, "project", "item-edit"))["argv"]
        assert _flag(edit, "--project-id") == "PVT_abc"
        assert _flag(edit, "--single-select-option-id") == "todo-id"

    def test_passes_through_item_edit_failure(self, fake_gh):
        _write_project_env(fake_gh.repo)
        fake_gh.rules([ON_BOARD, {"argv_prefix": ["project", "item-edit"], "stderr": "edit failed\n", "exit": 1}])
        result = _run(fake_gh.repo, "status", "42", "done")
        assert (result.returncode, result.stdout, result.stderr) == (1, "", "edit failed\n")

    def test_unknown_status_end_to_end(self, fake_gh):
        """Carry-over from #118: the exact unknown-status message through the CLI."""
        _write_project_env(fake_gh.repo)
        result = _run(fake_gh.repo, "status", "42", "bogus")
        assert (result.returncode, result.stdout, result.stderr) == (1, "", UNKNOWN_STATUS_MSG + "\n")
        assert _writes(fake_gh) == []

    def test_unknown_issue_prints_gh_line_without_traceback(self, fake_gh):
        _write_project_env(fake_gh.repo)
        fake_gh.rules([{"argv_prefix": ["api", "graphql"],
                        "stderr": "gh: Could not resolve to an Issue with the number of 999.\n", "exit": 1}])
        result = _run(fake_gh.repo, "status", "999", "todo")
        assert result.returncode == 1
        assert result.stderr.splitlines()[0] == "gh: Could not resolve to an Issue with the number of 999."
        assert "Traceback" not in result.stderr
        assert _writes(fake_gh) == []


class TestMalformedGraphql:
    """#119 evaluator silent risks: odd gh api graphql replies follow the Error contract."""

    @pytest.mark.parametrize("stdout", ["not json\n", '{"errors": []}\n'], ids=["not-json", "no-data"])
    @pytest.mark.parametrize(
        "argv",
        [pytest.param(["status", "42", "todo"], id="status"),
         pytest.param(["create", "--title", "T", "--body", "B", "--parent", "7"], id="create-parent")],
    )
    def test_malformed_reply_is_one_error_line(self, fake_gh, stdout, argv):
        _write_project_env(fake_gh.repo)
        fake_gh.rules([{"argv_prefix": ["api", "graphql"], "stdout": stdout}])
        result = _run(fake_gh.repo, *argv)
        assert result.returncode == 1
        assert result.stderr == "Error: unexpected gh api graphql response\n"
        assert _writes(fake_gh) == []

    def test_status_with_null_issue_reports_not_on_board(self, fake_gh):
        _write_project_env(fake_gh.repo)
        null = json.dumps({"data": {"repository": {"issue": None}}}) + "\n"
        fake_gh.rules([{"argv_prefix": ["api", "graphql"], "stdout": null}])
        result = _run(fake_gh.repo, "status", "42", "todo")
        assert (result.returncode, result.stdout, result.stderr) == (
            1, "Error: issue #42 not found on the project board\n", "")

    def test_create_with_null_parent_is_not_found(self, fake_gh):
        null = json.dumps({"data": {"repository": {"issue": None}}}) + "\n"
        fake_gh.rules([{"argv_prefix": ["api", "graphql"], "stdout": null}])
        result = _run(fake_gh.repo, "create", "--title", "T", "--body", "B", "--parent", "7")
        assert (result.returncode, result.stderr) == (1, "Error: parent #7 not found\n")
        assert _writes(fake_gh) == []


class TestBoardAddReply:
    def test_status_add_with_non_json_reply_names_the_reply(self, fake_gh):
        # PR #125 review: a malformed item-add reply is reported, not swallowed.
        _write_project_env(fake_gh.repo)
        fake_gh.rules([{"argv_prefix": ["project", "item-add"], "stdout": "oops\n"}])
        result = _run(fake_gh.repo, "status", "42", "todo", "--add-to-board")
        assert (result.returncode, result.stdout) == (1, "")
        assert result.stderr == "unexpected gh project item-add reply: oops\n"


class TestShims:
    """#119 — the bash scripts are shims onto tracker.py (Open question 4 changes)."""

    def test_status_shim_remove_prints_usage(self, fake_gh):
        _write_project_env(fake_gh.repo)
        result = _shim(fake_gh.repo, STATUS_SHIM, "remove", "42")
        assert result.returncode == 1
        assert result.stdout == (
            f"Usage: {STATUS_SHIM} <issue-number> <status>\n"
            f"       {STATUS_SHIM} add <issue-number> [status]\n"
            f"       {STATUS_SHIM} remove <issue-number>\n"
            'Status: todo | blocked | "in progress" | done\n'
        )
        assert _writes(fake_gh) == []

    def test_status_shim_prints_usage_before_missing_config(self, fake_gh):
        result = _shim(fake_gh.repo, STATUS_SHIM, "42")
        assert result.returncode == 1
        assert result.stdout.startswith(f"Usage: {STATUS_SHIM} <issue-number> <status>\n")

    def test_create_shim_value_flag_without_value(self, fake_gh):
        result = _shim(fake_gh.repo, CREATE_SHIM, "--body", "B", "--title")
        assert (result.returncode, result.stdout, result.stderr) == (1, "", "Error: --title needs a value\n")

    def test_create_shim_forwards_new_flags(self, fake_gh):
        fake_gh.rules([_issue_rule(7, body="## Tasks\n"), NO_DUP, CREATED, EDIT_OK])
        _ok(_shim(fake_gh.repo, CREATE_SHIM, *BASE, "--type", "epic", "--parent", "#7"), "created:42\n")
        assert _flag(_only(_calls(fake_gh, "issue", "create"))["argv"], "--label") == "epic"

    def test_status_shim_unknown_status(self, fake_gh):
        _write_project_env(fake_gh.repo)
        result = _shim(fake_gh.repo, STATUS_SHIM, "42", "bogus")
        assert (result.returncode, result.stdout, result.stderr) == (1, "", UNKNOWN_STATUS_MSG + "\n")


# ---------------------------------------------------------------- gh never reads the caller's stdin


def _run_with_open_stdin(cwd: pathlib.Path, *args: str, limit: float = 20.0) -> tuple[int, str, str]:
    """Run tracker.py with stdin an open pipe holding data that is never closed.

    A gh call that inherits stdin would block in read() until EOF, so the run would not finish.
    """
    out, err = cwd.parent / "open-stdin.out", cwd.parent / "open-stdin.err"
    with out.open("w") as fout, err.open("w") as ferr:
        proc = subprocess.Popen([sys.executable, str(TRACKER), *args], cwd=cwd, stdin=subprocess.PIPE,
                                stdout=fout, stderr=ferr, text=True)
        assert proc.stdin is not None
        proc.stdin.write("LEAKED-STDIN\n")
        proc.stdin.flush()
        deadline = time.monotonic() + limit
        try:
            while proc.poll() is None and time.monotonic() < deadline:
                time.sleep(0.05)
            finished = proc.poll() is not None
        finally:
            proc.stdin.close()
            if proc.poll() is None:
                proc.kill()
            proc.wait()
    assert finished, f"tracker.py {args} hung: a gh call inherited the caller's stdin"
    return proc.returncode, out.read_text(), err.read_text()


class TestStdinSafety:
    """#119 — every gh call gets explicit input or DEVNULL (never the caller's stdin)."""

    def test_create_with_parent_and_board(self, fake_gh):
        _write_project_env(fake_gh.repo)
        fake_gh.rules([_issue_rule(7, body="## Tasks\n"), NO_DUP, CREATED, EDIT_OK, ITEM_ADD_OK, ITEM_EDIT_OK])
        code, stdout, _ = _run_with_open_stdin(fake_gh.repo, "create", *BASE, "--parent", "#7", "--add-to-board")
        assert (code, stdout) == (0, "created:42\n")
        assert all("LEAKED-STDIN" not in c["stdin"] for c in fake_gh.calls())

    def test_status(self, fake_gh):
        _write_project_env(fake_gh.repo)
        fake_gh.rules([ON_BOARD, ITEM_EDIT_OK])
        code, stdout, _ = _run_with_open_stdin(fake_gh.repo, "status", "42", "todo")
        assert (code, stdout) == (0, "Issue #42 → todo\n")
        assert all("LEAKED-STDIN" not in c["stdin"] for c in fake_gh.calls())


# ---------------------------------------------------------------- I8


class TestNoShell:
    """#119 I8 — no gh call is built by string concatenation or shell=True."""

    def test_shell_true_absent(self):
        assert "shell=True" not in GITHUB_BACKEND.read_text(encoding="utf-8")

    def test_every_subprocess_call_takes_a_list(self):
        tree = ast.parse(GITHUB_BACKEND.read_text(encoding="utf-8"))
        calls = [
            node for node in ast.walk(tree)
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
            and isinstance(node.func.value, ast.Name) and node.func.value.id == "subprocess"
        ]
        assert calls, "expected the backend to call gh through subprocess"
        for call in calls:
            assert call.func.attr in {"run", "Popen"}, ast.unparse(call)  # no check_output(str), getoutput, …
            assert call.args and isinstance(call.args[0], ast.List), ast.unparse(call)
            for kw in call.keywords:
                if kw.arg == "shell":
                    assert isinstance(kw.value, ast.Constant) and kw.value.value is False

    def test_no_os_system_or_popen(self):
        source = GITHUB_BACKEND.read_text(encoding="utf-8")
        assert "os.system" not in source
        assert "os.popen" not in source


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
        assert (result.returncode, result.stdout, result.stderr) == (1, "", UNKNOWN_STATUS_MSG + "\n")
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


class TestTokenScope:
    """Board fields need the read:project scope; they are requested only when project.env exists."""

    @staticmethod
    def _queries(fake_gh) -> list[str]:
        return [" ".join(c["argv"]) for c in _calls(fake_gh, "api", "graphql")]

    @pytest.mark.parametrize(
        ("argv", "rules"),
        [
            pytest.param(["edit", "5", "--title", "T"], [_issue_rule(5), EDIT_OK], id="edit"),
            pytest.param(["comment", "5", "--body", "B"], [_issue_rule(5), COMMENT_OK], id="comment"),
            pytest.param(["view", "5"], [_issue_rule(5)], id="view-without-project-env"),
            pytest.param(["list"], [_list_rule([])], id="list-without-project-env"),
        ],
    )
    def test_does_not_request_board_fields(self, fake_gh, argv, rules):
        fake_gh.rules(rules)
        result = _run(fake_gh.repo, *argv)
        assert result.returncode == 0, result.stderr
        assert all("projectItems" not in q for q in self._queries(fake_gh))

    @pytest.mark.parametrize(
        ("argv", "rules"),
        [
            pytest.param(["view", "5"], [_issue_rule(5)], id="view"),
            pytest.param(["list"], [_list_rule([])], id="list"),
        ],
    )
    def test_requests_board_fields_with_project_env(self, fake_gh, argv, rules):
        _write_project_env(fake_gh.repo)
        fake_gh.rules(rules)
        result = _run(fake_gh.repo, *argv)
        assert result.returncode == 0, result.stderr
        assert any("projectItems" in q for q in self._queries(fake_gh))
