"""#144 — bin/epic-progress.py, the epic progress reader (LLD v3 E3.3 §1.2, story 2.1 AC2, invariants I6-I9).

Runs the reader as a subprocess. It reaches the tracker only through `tracker.py view`, so the
backend is faked underneath: `fake_gh` (GitHub) and `fake_jira` (Jira). Reusable fixtures come from
tests/conftest.py; no HTTP stubs or monkeypatching of the unit.
"""

from __future__ import annotations

import json
import pathlib
import subprocess
import sys

import pytest

BIN_DIR = pathlib.Path(__file__).resolve().parent.parent / "plugins" / "edf" / "bin"
READER = BIN_DIR / "epic-progress.py"

pytestmark = pytest.mark.skipif(sys.platform == "win32", reason="fake_gh and fake_jira are POSIX only")

WRITE_PREFIXES = (["issue", "create"], ["issue", "edit"], ["issue", "comment"], ["issue", "close"],
                  ["project", "item-edit"], ["project", "item-add"])


def _read(cwd, *args):
    return subprocess.run([sys.executable, str(READER), *args], cwd=cwd, capture_output=True, text=True,
                          timeout=60, stdin=subprocess.DEVNULL)


# ---------------------------------------------------------------- GitHub scenarios


def _node(state: str = "OPEN") -> dict:
    return {"state": state, "projectItems": {"nodes": []}}


def _epic_rule(number: int, children: list[int]) -> dict:
    body = "## Tasks\n" + "".join(f"- [ ] #{n} — child {n}\n" for n in children)
    node = {"number": number, "title": "Epic", "body": body, "state": "OPEN",
            "labels": {"nodes": [{"name": "epic"}]}, "projectItems": {"nodes": []}}
    return {"argv_prefix": ["api", "graphql"], "argv_contains": [f"number={number}"],
            "stdout": json.dumps({"data": {"repository": {"issue": node}}}) + "\n"}


def _children_rule(nodes: list[dict | None]) -> dict:
    repo = {f"c{i}": n for i, n in enumerate(nodes)}
    return {"argv_prefix": ["api", "graphql"], "stdout": json.dumps({"data": {"repository": repo}}) + "\n"}


def _gh_epic(fake_gh, nodes: list[dict | None], children: list[int] | None = None) -> None:
    children = children or [21, 22, 23][: len(nodes)]
    fake_gh.rules([_epic_rule(7, children), _children_rule(nodes)])


class TestReaderOnGitHub:
    def test_prints_summary_then_one_indented_line_per_child(self, fake_gh):
        _gh_epic(fake_gh, [_node("CLOSED"), _node(), _node()])
        result = _read(fake_gh.repo, "#7")
        assert result.returncode == 0, result.stderr
        assert result.stdout == "#7: 1 of 3 done\n  #21 done\n  #22 todo\n  #23 todo\n"
        assert result.stderr == ""

    def test_all_children_done(self, fake_gh):
        _gh_epic(fake_gh, [_node("CLOSED"), _node("CLOSED")], [21, 22])
        assert _read(fake_gh.repo, "#7").stdout.splitlines()[0] == "#7: 2 of 2 done"

    def test_remaining_prints_only_children_that_are_not_done_one_per_line(self, fake_gh):
        _gh_epic(fake_gh, [_node("CLOSED"), _node(), _node()])
        result = _read(fake_gh.repo, "#7", "--remaining")
        assert result.returncode == 0, result.stderr
        assert result.stdout == "#22\n#23\n"

    def test_remaining_is_empty_when_everything_is_done(self, fake_gh):
        _gh_epic(fake_gh, [_node("CLOSED"), _node("CLOSED")], [21, 22])
        result = _read(fake_gh.repo, "#7", "--remaining")
        assert (result.returncode, result.stdout) == (0, "")

    def test_remaining_accepts_the_flag_before_the_ref(self, fake_gh):
        _gh_epic(fake_gh, [_node("CLOSED"), _node()], [21, 22])
        assert _read(fake_gh.repo, "--remaining", "#7").stdout == "#22\n"

    def test_missing_checklist_issue_is_unknown_counted_in_total_not_done(self, fake_gh):
        """#144 AC3 — the null alias is omitted by view; the reader reports it unknown."""
        rule = _children_rule([_node("CLOSED"), None, _node()])
        rule.update(stderr="gh: Could not resolve to an Issue with the number of 22.\n", exit=1)
        fake_gh.rules([_epic_rule(7, [21, 22, 23]), rule])
        result = _read(fake_gh.repo, "#7")
        assert result.returncode == 0, result.stderr
        assert result.stdout == "#7: 1 of 3 done\n  #21 done\n  #22 unknown\n  #23 todo\n"

    def test_unknown_child_is_listed_by_remaining(self, fake_gh):
        rule = _children_rule([_node("CLOSED"), None])
        rule.update(stderr="gh: Could not resolve to an Issue with the number of 22.\n", exit=1)
        fake_gh.rules([_epic_rule(7, [21, 22]), rule])
        assert _read(fake_gh.repo, "#7", "--remaining").stdout == "#22\n"

    def test_epic_with_no_children_reports_zero_of_zero(self, fake_gh):
        fake_gh.rules([_epic_rule(7, [])])
        result = _read(fake_gh.repo, "#7")
        assert (result.returncode, result.stdout) == (0, "#7: 0 of 0 done\n")

    def test_tracker_view_failure_prints_the_error_line_and_exits_1(self, fake_gh):
        fake_gh.rules([{"argv_prefix": ["api", "graphql"], "argv_contains": ["number=404"],
                        "stderr": "gh: Could not resolve to an Issue with the number of 404.\n", "exit": 1}])
        result = _read(fake_gh.repo, "#404")
        assert result.returncode == 1
        assert result.stdout == ""
        assert result.stderr == "Error: #404 not found\n"

    def test_gh_failure_is_surfaced_as_an_error_line(self, fake_gh):
        fake_gh.rules([{"argv_prefix": ["api", "graphql"], "stderr": "HTTP 502: Bad Gateway\n", "exit": 1}])
        result = _read(fake_gh.repo, "#7")
        assert result.returncode == 1
        assert result.stdout == ""
        assert result.stderr.startswith("Error: ")
        assert "HTTP 502" in result.stderr

    def test_missing_ref_argument_is_a_usage_error(self, fake_gh):
        result = _read(fake_gh.repo)
        assert result.returncode != 0
        assert result.stdout == ""
        assert fake_gh.calls() == []

    def test_reader_makes_no_write_calls(self, fake_gh):
        """#144 I9 — only reads reach gh, in both modes."""
        _gh_epic(fake_gh, [_node("CLOSED"), _node()], [21, 22])
        _read(fake_gh.repo, "#7")
        _read(fake_gh.repo, "#7", "--remaining")
        calls = fake_gh.calls()
        assert calls
        assert all(c["argv"][:2] == ["api", "graphql"] for c in calls), [c["argv"] for c in calls]
        assert not [c for c in calls if any(c["argv"][: len(p)] == p for p in WRITE_PREFIXES)]

    def test_request_count_is_equal_for_one_and_twenty_children(self, fake_gh):
        """#144 I7 — the reader adds no per-child calls."""
        counts = []
        for count in (1, 20):
            numbers = list(range(100, 100 + count))
            fake_gh.rules([_epic_rule(7, numbers), _children_rule([_node() for _ in numbers])])
            if fake_gh.log.exists():
                fake_gh.log.unlink()
            result = _read(fake_gh.repo, "#7")
            assert result.returncode == 0, result.stderr
            assert result.stdout.splitlines()[0] == f"#7: 0 of {count} done"
            counts.append(len(fake_gh.calls()))
        assert counts[0] == counts[1]


# ---------------------------------------------------------------- Jira scenarios


class TestReaderOnJira:
    def test_prints_summary_and_statuses_for_an_epic(self, fake_jira, tmp_path):
        epic = fake_jira.add_issue("Epic", type="Epic")
        a = fake_jira.add_issue("A", parent=epic, status="Done")
        b = fake_jira.add_issue("B", parent=epic, status="In Progress")
        c = fake_jira.add_issue("C", parent=epic, status="To Do")
        result = _read(tmp_path, epic)
        assert result.returncode == 0, result.stderr
        assert result.stdout == f"{epic}: 1 of 3 done\n  {a} done\n  {b} in progress\n  {c} todo\n"

    def test_remaining_lists_children_not_done(self, fake_jira, tmp_path):
        epic = fake_jira.add_issue("Epic", type="Epic")
        fake_jira.add_issue("A", parent=epic, status="Done")
        b = fake_jira.add_issue("B", parent=epic, status="In Progress")
        c = fake_jira.add_issue("C", parent=epic, status="To Do")
        result = _read(tmp_path, epic, "--remaining")
        assert result.returncode == 0, result.stderr
        assert result.stdout == f"{b}\n{c}\n"

    def test_unknown_key_prints_the_error_line_and_exits_1(self, fake_jira, tmp_path):
        result = _read(tmp_path, "SCRUM-99")
        assert (result.returncode, result.stdout, result.stderr) == (1, "", "Error: SCRUM-99 not found\n")

    def test_reader_makes_no_write_calls(self, fake_jira, tmp_path):  # I9
        epic = fake_jira.add_issue("Epic", type="Epic")
        fake_jira.add_issue("A", parent=epic)
        _read(tmp_path, epic)
        _read(tmp_path, epic, "--remaining")
        calls = fake_jira.calls()
        assert calls
        writes = [c for c in calls if c["method"] != "GET" and not c["path"].endswith("/search/jql")]
        assert writes == []

    def test_request_count_is_equal_for_one_and_twenty_children(self, fake_jira, tmp_path):  # I7
        counts = []
        for count in (1, 20):
            epic = fake_jira.add_issue(f"Epic {count}", type="Epic")
            for n in range(count):
                fake_jira.add_issue(f"C{count}-{n}", parent=epic)
            before = len(fake_jira.calls())
            result = _read(tmp_path, epic)
            assert result.returncode == 0, result.stderr
            counts.append(len(fake_jira.calls()) - before)
        assert counts[0] == counts[1]
