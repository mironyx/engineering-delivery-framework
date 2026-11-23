"""#168 — bin/unblock-dependants.py: after `close <ref>`, Blocked dependants whose every
`## Depends on` ref is now closed move to Todo.

`main` is driven through the module's `_tracker` seam (the single call to tracker.py), replaced
here by a fake board that answers `list`/`view` with the tracker's Issue JSON and records
`status` calls. The tracker backends themselves are covered by test_tracker*.py.
"""

from __future__ import annotations

import importlib.util
import json
import pathlib
import subprocess
import sys

import pytest

BIN_DIR = pathlib.Path(__file__).resolve().parent.parent / "plugins" / "edf" / "bin"
sys.path.insert(0, str(BIN_DIR))


def _load_module():
    spec = importlib.util.spec_from_file_location("unblock_dependants", BIN_DIR / "unblock-dependants.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


ub = _load_module()


def _issue(ref: str, status: str, depends: str | None = None) -> dict:
    body = "## What\nSomething.\n"
    if depends is not None:
        body += f"\n## Depends on\n{depends}\n"
    body += "\n## Layer\nbin\n"
    return {"ref": ref, "title": f"Issue {ref}", "body": body, "labels": [], "status": status,
            "parent": None, "children": [], "child_statuses": {}}


def _key(ref: str) -> str:
    return ref.lstrip("#")


class FakeBoard:
    """Answers tracker.py list/view/status from an in-memory set of issues."""

    def __init__(self, issues: list[dict], fail_list: bool = False):
        self.issues = {_key(i["ref"]): i for i in issues}
        self.fail_list = fail_list
        self.calls: list[tuple[str, ...]] = []

    def __call__(self, *args: str) -> subprocess.CompletedProcess[str]:
        self.calls.append(args)
        op = args[0]
        if op == "list":
            if self.fail_list:
                return subprocess.CompletedProcess(args, 1, "", "Error: gh: HTTP 502\n")
            issues = list(self.issues.values())
            if "--status" in args:
                wanted = args[args.index("--status") + 1]
                issues = [i for i in issues if i["status"] == wanted]
            return subprocess.CompletedProcess(args, 0, json.dumps(issues, indent=2), "")
        if op == "view":
            issue = self.issues.get(_key(args[1]))
            if issue is None:
                return subprocess.CompletedProcess(args, 1, "", f"Error: issue {args[1]} not found\n")
            return subprocess.CompletedProcess(args, 0, json.dumps(issue, indent=2), "")
        if op == "status":
            return subprocess.CompletedProcess(args, 0, "", "")
        return subprocess.CompletedProcess(args, 1, "", f"Error: unexpected op {op}\n")

    def moved(self) -> dict[str, str]:
        """ref (no '#') -> new status, for every `status` call."""
        return {_key(c[1]): c[2] for c in self.calls if c[0] == "status"}


def _run(monkeypatch, capsys, board: FakeBoard, ref: str) -> tuple[int, list[str]]:
    monkeypatch.setattr(ub, "_tracker", board)
    code = ub.main([ref])
    lines = [ln.strip() for ln in capsys.readouterr().out.splitlines() if ln.strip()]
    return code, lines


# ── pure helpers ─────────────────────────────────────────────────────────────


class TestNormaliseRef:
    @pytest.mark.parametrize("raw", ["12", "#12"])
    def test_github_forms_become_hash_number(self, raw):
        assert ub.normalise_ref(raw) == "#12"

    def test_jira_key_unchanged(self):
        assert ub.normalise_ref("SCRUM-12") == "SCRUM-12"


class TestDependsOnRefs:
    def test_hash_refs_in_order(self):
        body = _issue("#5", "blocked", "- #3\n- #4 (schema)")["body"]
        assert ub.depends_on_refs(body) == ["#3", "#4"]

    def test_jira_keys(self):
        body = _issue("SCRUM-5", "blocked", "- SCRUM-3\n- SCRUM-4")["body"]
        assert ub.depends_on_refs(body) == ["SCRUM-3", "SCRUM-4"]

    def test_deduplicated(self):
        body = _issue("#5", "blocked", "#3 and #3 again, then #4")["body"]
        assert ub.depends_on_refs(body) == ["#3", "#4"]

    def test_none_text_yields_empty_even_when_it_mentions_a_ref(self):
        body = _issue("#5", "blocked", "None — parallel-safe with #9's design task.")["body"]
        assert ub.depends_on_refs(body) == []

    def test_plain_none_yields_empty(self):
        body = _issue("#5", "blocked", "None — parallel-safe.")["body"]
        assert ub.depends_on_refs(body) == []

    def test_absent_section_yields_empty(self):
        assert ub.depends_on_refs(_issue("#5", "blocked")["body"]) == []

    def test_refs_outside_the_section_are_ignored(self):
        body = "## What\nSee #99.\n\n## Depends on\n- #3\n\n## Layer\nRelated: #100\n"
        assert ub.depends_on_refs(body) == ["#3"]


# ── main ─────────────────────────────────────────────────────────────────────


class TestUnblock:
    def test_dependant_whose_only_blocker_closed_moves_to_todo(self, monkeypatch, capsys):
        board = FakeBoard([_issue("#3", "done"), _issue("#5", "blocked", "- #3")])
        code, lines = _run(monkeypatch, capsys, board, "3")
        assert code == 0
        assert board.moved() == {"5": "todo"}
        assert lines == ["unblocked: #5"]

    def test_all_blockers_closed_moves_to_todo(self, monkeypatch, capsys):
        board = FakeBoard([_issue("#3", "done"), _issue("#4", "done"),
                           _issue("#5", "blocked", "- #3\n- #4")])
        code, lines = _run(monkeypatch, capsys, board, "#4")
        assert code == 0
        assert board.moved() == {"5": "todo"}
        assert "unblocked: #5" in lines

    def test_open_blocker_keeps_dependant_blocked(self, monkeypatch, capsys):
        board = FakeBoard([_issue("#3", "done"), _issue("#4", "in progress"),
                           _issue("#5", "blocked", "- #3\n- #4")])
        code, lines = _run(monkeypatch, capsys, board, "3")
        assert code == 0
        assert board.moved() == {}
        assert lines == ["unblock: none"]

    def test_dependant_not_naming_the_closed_ref_is_untouched(self, monkeypatch, capsys):
        # #6 is blocked on #4 only; closing #3 must not move it, even though #4 is done.
        board = FakeBoard([_issue("#3", "done"), _issue("#4", "done"),
                           _issue("#6", "blocked", "- #4")])
        code, lines = _run(monkeypatch, capsys, board, "3")
        assert code == 0
        assert board.moved() == {}
        assert lines == ["unblock: none"]

    def test_non_blocked_issue_is_never_moved(self, monkeypatch, capsys):
        board = FakeBoard([_issue("#3", "done"), _issue("#7", "in progress", "- #3")])
        code, lines = _run(monkeypatch, capsys, board, "3")
        assert code == 0
        assert board.moved() == {}
        assert lines == ["unblock: none"]

    def test_closed_ref_counts_as_done_without_lookup(self, monkeypatch, capsys):
        # The tracker may still report the just-closed issue stale; it must not be consulted.
        board = FakeBoard([_issue("#3", "in progress"), _issue("#5", "blocked", "- #3")])
        _code, _lines = _run(monkeypatch, capsys, board, "3")
        assert board.moved() == {"5": "todo"}
        assert not any(c[0] == "view" and _key(c[1]) == "3" for c in board.calls)

    def test_several_dependants_each_reported(self, monkeypatch, capsys):
        board = FakeBoard([_issue("#3", "done"), _issue("#4", "todo"),
                           _issue("#5", "blocked", "- #3"),
                           _issue("#6", "blocked", "- #3\n- #4"),
                           _issue("#8", "blocked", "#3")])
        code, lines = _run(monkeypatch, capsys, board, "3")
        assert code == 0
        assert board.moved() == {"5": "todo", "8": "todo"}
        assert sorted(lines) == ["unblocked: #5", "unblocked: #8"]

    def test_nothing_blocked(self, monkeypatch, capsys):
        board = FakeBoard([_issue("#3", "done")])
        code, lines = _run(monkeypatch, capsys, board, "3")
        assert code == 0
        assert lines == ["unblock: none"]
        assert board.moved() == {}

    def test_jira_keys(self, monkeypatch, capsys):
        board = FakeBoard([_issue("SCRUM-3", "done"), _issue("SCRUM-4", "done"),
                           _issue("SCRUM-5", "blocked", "- SCRUM-3\n- SCRUM-4"),
                           _issue("SCRUM-6", "blocked", "- SCRUM-30")])
        code, lines = _run(monkeypatch, capsys, board, "SCRUM-3")
        assert code == 0
        assert board.moved() == {"SCRUM-5": "todo"}
        assert lines == ["unblocked: SCRUM-5"]


class TestBestEffort:
    def test_tracker_failure_prints_one_skipped_line_and_exits_0(self, monkeypatch, capsys):
        board = FakeBoard([], fail_list=True)
        code, lines = _run(monkeypatch, capsys, board, "3")
        assert code == 0
        assert len(lines) == 1
        assert lines[0].startswith("unblock: skipped")
        assert board.moved() == {}

    def test_missing_argument_exits_2(self, monkeypatch):
        monkeypatch.setattr(ub, "_tracker", FakeBoard([]))
        try:
            code = ub.main([])
        except SystemExit as exc:
            code = exc.code
        assert code == 2
