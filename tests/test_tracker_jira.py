"""#132 — Jira backend `create` (LLD v3-e3-2 §1.3, invariants C1-C5).

Runs tracker.py as a subprocess against the `fake_jira` fixture (local HTTPS http.server), not
respx: the plugin is standard-library only (ADR-0041).
"""

from __future__ import annotations

import json
import pathlib
import subprocess
import sys

import pytest

from _tracker_jira import _jql_phrase, _jql_str

BIN_DIR = pathlib.Path(__file__).resolve().parent.parent / "plugins" / "edf" / "bin"
TRACKER = BIN_DIR / "tracker.py"

pytestmark = pytest.mark.skipif(sys.platform == "win32", reason="fake_jira is POSIX only")


def _run(cwd, *args):
    return subprocess.run([sys.executable, str(TRACKER), *args], cwd=cwd, capture_output=True, text=True, timeout=30)


def _create(cwd, title="Add widget", body="Some **body**", *extra):
    return _run(cwd, "create", "--title", title, "--body", body, *extra)


def _writes(fake):
    return [c for c in fake.calls() if c["method"] != "GET" and not c["path"].endswith("/search/jql")]


class TestCreate:
    def test_creates_task_with_adf_body_and_labels(self, fake_jira, tmp_path):
        r = _create(tmp_path, "Add widget", "Some **body**", "--labels", "a, b,,c")
        assert r.returncode == 0, r.stderr
        assert r.stdout.strip() == "created:SCRUM-1"
        issue = fake_jira.issue("SCRUM-1")
        assert issue["type"] == "Task"
        assert issue["labels"] == ["a", "b", "c"]
        assert issue["description"]["type"] == "doc"
        assert issue["description"]["content"][0]["type"] == "paragraph"

    def test_prints_exists_for_open_issue_with_exact_title(self, fake_jira, tmp_path):
        key = fake_jira.add_issue("Add widget")
        r = _create(tmp_path)
        assert r.stdout.strip() == f"exists:{key}"
        assert _writes(fake_jira) == []

    def test_substring_title_is_not_a_duplicate(self, fake_jira, tmp_path):
        fake_jira.add_issue("Add widget now")
        assert _create(tmp_path).stdout.strip() == "created:SCRUM-2"

    def test_creates_when_only_closed_issue_has_the_title(self, fake_jira, tmp_path):
        fake_jira.add_issue("Add widget", status="Done")
        assert _create(tmp_path).stdout.strip() == "created:SCRUM-2"

    def test_creates_epic(self, fake_jira, tmp_path):
        assert _create(tmp_path, "E", "b", "--type", "epic").returncode == 0
        assert fake_jira.issue("SCRUM-1")["type"] == "Epic"

    def test_sets_parent(self, fake_jira, tmp_path):
        parent = fake_jira.add_issue("Epic", type="Epic")
        r = _create(tmp_path, "Child", "b", "--parent", parent.lower())
        assert r.stdout.strip() == "created:SCRUM-2"
        assert fake_jira.issue("SCRUM-2")["parent"] == parent

    def test_missing_parent_errors_and_writes_nothing(self, fake_jira, tmp_path):  # C1
        r = _create(tmp_path, "Child", "b", "--parent", "SCRUM-9")
        assert r.returncode == 1
        assert r.stderr.strip() == "Error: parent SCRUM-9 not found"
        assert _writes(fake_jira) == []
        assert not any(c["path"].endswith("/search/jql") for c in fake_jira.calls())

    def test_dry_run_prints_block_and_writes_nothing(self, fake_jira, tmp_path):  # C2
        parent = fake_jira.add_issue("Epic", type="Epic")
        r = _create(tmp_path, "T", "l1\nl2", "--dry-run", "--parent", parent, "--labels", "x")
        assert r.stdout.splitlines() == [
            "dry-run: would create issue", "  title:  T", "  labels: x", f"  parent: {parent}",
            "  body:", "    l1", "    l2",
        ]
        assert _writes(fake_jira) == []

    def test_dry_run_without_labels_shows_none(self, fake_jira, tmp_path):
        assert "  labels: <none>" in _create(tmp_path, "T", "b", "--dry-run").stdout

    @pytest.mark.parametrize("title", [
        'He said "hi"', "back\\slash", "a OR b", "x) OR (y", "tilde~ star* q?", "line1\nline2",
        "ends with quote\"", "a+b-c:d",
    ])
    def test_hostile_title_creates_then_matches_only_itself(self, fake_jira, tmp_path, title):  # C3
        first = _create(tmp_path, title)
        assert first.returncode == 0, first.stderr
        assert first.stdout.strip() == "created:SCRUM-1"
        again = _create(tmp_path, title)
        assert again.stdout.strip() == "exists:SCRUM-1"

    def test_titles_differing_by_one_special_character_are_not_confused(self, fake_jira, tmp_path):
        fake_jira.add_issue("a*b")
        assert _create(tmp_path, "a?b").stdout.strip() == "created:SCRUM-2"

    def test_creates_with_raw_html_body(self, fake_jira, tmp_path):
        r = _create(tmp_path, "H", "<div>hi</div>\n\n<script>x</script>")
        assert r.returncode == 0, r.stderr
        assert fake_jira.issue("SCRUM-1")["description"]["type"] == "doc"

    def test_labels_are_sent_one_to_one(self, fake_jira, tmp_path):  # C5
        _create(tmp_path, "T", "b", "--labels", "epic,created:SCRUM-1")
        post = next(c for c in fake_jira.calls() if c["method"] == "POST" and c["path"].endswith("/issue"))
        assert post["body"]["fields"]["labels"] == ["epic", "created:SCRUM-1"]

    def test_ignores_add_to_board_and_board_status(self, fake_jira, tmp_path):
        r = _create(tmp_path, "T", "b", "--add-to-board", "--board-status", "blocked")
        assert r.stdout.strip() == "created:SCRUM-1"
        assert r.stderr == ""

    def test_unknown_type_uses_github_message(self, fake_jira, tmp_path):
        r = _create(tmp_path, "T", "b", "--type", "bug")
        assert r.returncode == 1
        assert r.stderr.strip() == "Error: unknown type 'bug'. Use: task | epic"
        assert fake_jira.calls() == []


class TestJqlEscaping:
    def test_jql_str_escapes_backslash_quote_and_control(self):
        assert _jql_str('a\\b"c\nd') == '"a\\\\b\\"c\\nd"'

    def test_jql_phrase_wraps_in_phrase_quotes_and_escapes_specials(self):
        assert _jql_phrase("a+b") == '"\\"a\\\\+b\\""'


class TestRobustness:
    def test_repeating_next_page_token_terminates(self, fake_jira, tmp_path):
        from _jira_client import JiraClient
        from _tracker_jira import _search_all
        from tracker import JiraConfig

        env = fake_jira.env
        client = JiraClient(JiraConfig(env["JIRA_HOST"], env["JIRA_EMAIL"], env["JIRA_API_TOKEN"], env["JIRA_SPACE"]))
        client.request = lambda *a, **k: (200, {"issues": [], "nextPageToken": "x", "isLast": False})
        assert _search_all(client, 'project = "SCRUM"', fields=["summary"], limit=100) == []

    def test_create_response_without_key_is_a_tracker_error(self, fake_jira, tmp_path):
        fake_jira.fail_next(200, "{}")  # search answer without issues
        fake_jira.fail_next(201, "{}")  # create answer without key
        r = _create(tmp_path)
        assert r.returncode == 1
        assert r.stderr.strip() == "Error: Jira returned an unreadable response"


# ---------------------------------------------------------------------------------------------
# #133 — Jira backend `view` and `list` (LLD v3-e3-2 §1.4, invariants V1-V5)
# ---------------------------------------------------------------------------------------------
SEVEN_KEYS = ["ref", "title", "body", "labels", "status", "parent", "children"]


def _view(cwd, ref):
    return _run(cwd, "view", ref)


def _list(cwd, *args):
    return _run(cwd, "list", *args)


def _doc(text):
    return {"type": "doc", "version": 1, "content": [{"type": "paragraph", "content": [{"type": "text", "text": text}]}]}


def _refs(result):
    assert result.returncode == 0, result.stderr
    return [i["ref"] for i in json.loads(result.stdout)]


def _view_json(result):
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout)


class TestView:
    def test_returns_seven_key_json_for_task_with_parent(self, fake_jira, tmp_path):  # V1, AC1
        epic = fake_jira.add_issue("Epic", type="Epic")
        key = fake_jira.add_issue("Child", labels=["kind:task", "x"], parent=epic, description=_doc("hello"))
        data = _view_json(_view(tmp_path, key))
        assert list(data.keys()) == SEVEN_KEYS
        assert data["ref"] == key
        assert data["title"] == "Child"
        assert "hello" in data["body"]
        assert data["labels"] == ["kind:task", "x"]
        assert data["status"] == "todo"
        assert data["parent"] == epic
        assert data["children"] == []

    def test_issue_without_parent_has_null_parent(self, fake_jira, tmp_path):
        key = fake_jira.add_issue("Solo")
        assert _view_json(_view(tmp_path, key))["parent"] is None

    def test_epic_children_are_child_keys_in_rank_order(self, fake_jira, tmp_path):  # AC2
        epic = fake_jira.add_issue("Epic", type="Epic")
        c1 = fake_jira.add_issue("C1", parent=epic)
        fake_jira.add_issue("Other")
        c2 = fake_jira.add_issue("C2", parent=epic)
        fake_jira.set_rank(c2, 0)
        data = _view_json(_view(tmp_path, epic))
        assert data["children"] == [c2, c1]
        assert data["parent"] is None

    def test_task_with_sub_issues_has_empty_children(self, fake_jira, tmp_path):  # V4
        task = fake_jira.add_issue("Task", type="Task")
        fake_jira.add_issue("Sub", parent=task)
        assert _view_json(_view(tmp_path, task))["children"] == []

    def test_epic_without_children_has_empty_list(self, fake_jira, tmp_path):
        epic = fake_jira.add_issue("Epic", type="Epic")
        assert _view_json(_view(tmp_path, epic))["children"] == []

    @pytest.mark.parametrize("name,expected", [
        ("To Do", "todo"), ("In Progress", "in progress"), ("Blocked", "blocked"), ("Done", "done"),
    ])
    def test_maps_status_name_to_edf_status(self, fake_jira, tmp_path, name, expected):  # V3
        key = fake_jira.add_issue("T", status=name)
        assert _view_json(_view(tmp_path, key))["status"] == expected

    @pytest.mark.parametrize("name,category,expected", [
        ("In Review", "indeterminate", "in progress"),
        ("Backlog", "new", "todo"),
        ("Closed", "done", "done"),
    ])
    def test_maps_unmapped_status_by_category(self, fake_jira, tmp_path, name, category, expected):  # V3
        fake_jira.statuses[name] = category
        key = fake_jira.add_issue("T", status=name)
        assert _view_json(_view(tmp_path, key))["status"] == expected

    def test_null_description_gives_empty_body(self, fake_jira, tmp_path):
        key = fake_jira.add_issue("T", description=None)
        assert _view_json(_view(tmp_path, key))["body"] == ""

    def test_ui_authored_body_is_markdown(self, fake_jira, tmp_path):  # AC3
        desc = {"type": "doc", "version": 1, "content": [
            {"type": "heading", "attrs": {"level": 2}, "content": [{"type": "text", "text": "Title"}]},
            {"type": "paragraph", "content": [{"type": "text", "text": "plain"}]},
        ]}
        key = fake_jira.add_issue("T", description=desc)
        body = _view_json(_view(tmp_path, key))["body"]
        assert "## Title" in body
        assert "plain" in body

    def test_unknown_key_errors_not_found(self, fake_jira, tmp_path):  # AC5
        r = _view(tmp_path, "SCRUM-99")
        assert r.returncode == 1
        assert r.stderr.strip() == "Error: SCRUM-99 not found"
        assert r.stdout == ""

    def test_lower_case_key_is_accepted(self, fake_jira, tmp_path):
        key = fake_jira.add_issue("T")
        data = _view_json(_view(tmp_path, key.lower()))
        assert data["ref"] == key

    def test_lower_case_unknown_key_reports_upper_case(self, fake_jira, tmp_path):
        r = _view(tmp_path, "scrum-99")
        assert r.stderr.strip() == "Error: SCRUM-99 not found"

    def test_round_trips_full_subset_body_through_create_and_view(self, fake_jira, tmp_path):  # AC2
        body = (
            "# Heading\n\n- item one\n- item two\n\n```python\nx = 1\n```\n\n"
            "[link text](https://example.com/a)\n\n| a | b |\n|---|---|\n| 1 | 2 |"
        )
        assert _create(tmp_path, "RT", body).stdout.strip() == "created:SCRUM-1"
        out = _view_json(_view(tmp_path, "SCRUM-1"))["body"]
        assert "# Heading" in out
        assert "- item one" in out and "- item two" in out
        assert "```python" in out and "x = 1" in out
        assert "[link text](https://example.com/a)" in out
        lines = [ln.replace(" ", "") for ln in out.splitlines()]
        assert "|a|b|" in lines and "|1|2|" in lines

    def test_create_then_view_title_labels_and_parent(self, fake_jira, tmp_path):
        parent = fake_jira.add_issue("Epic", type="Epic")
        _create(tmp_path, "Child", "b", "--labels", "x,y", "--parent", parent)
        data = _view_json(_view(tmp_path, "SCRUM-2"))
        assert (data["title"], data["labels"], data["parent"]) == ("Child", ["x", "y"], parent)


class TestList:
    def test_each_element_has_seven_keys_in_order(self, fake_jira, tmp_path):  # V1
        epic = fake_jira.add_issue("Epic", type="Epic", labels=["epic"])
        fake_jira.add_issue("Child", parent=epic, description=_doc("hi"))
        items = _view_json(_list(tmp_path))
        assert len(items) == 2
        for item in items:
            assert list(item.keys()) == SEVEN_KEYS
        assert items[1]["parent"] == epic

    def test_empty_result_is_empty_array(self, fake_jira, tmp_path):
        r = _list(tmp_path)
        assert r.returncode == 0, r.stderr
        assert _view_json(r) == []

    def test_children_are_empty_for_epics_in_list(self, fake_jira, tmp_path):
        epic = fake_jira.add_issue("Epic", type="Epic")
        fake_jira.add_issue("Child", parent=epic)
        items = {i["ref"]: i for i in _view_json(_list(tmp_path))}
        assert items[epic]["children"] == []

    def test_status_todo_returns_only_todo_in_rank_order(self, fake_jira, tmp_path):  # AC6
        a = fake_jira.add_issue("A", status="To Do")
        fake_jira.add_issue("B", status="In Progress")
        c = fake_jira.add_issue("C", status="To Do")
        fake_jira.add_issue("D", status="Done")
        assert _refs(_list(tmp_path, "--status", "todo")) == [a, c]

    def test_status_filter_is_case_insensitive(self, fake_jira, tmp_path):
        a = fake_jira.add_issue("A", status="Blocked")
        assert _refs(_list(tmp_path, "--status", "BLOCKED")) == [a]

    def test_invalid_status_errors(self, fake_jira, tmp_path):
        r = _list(tmp_path, "--status", "bogus")
        assert r.returncode == 1
        assert r.stderr.startswith("Error:")

    def test_unmapped_in_review_appears_under_in_progress_not_todo(self, fake_jira, tmp_path):  # V2, V3
        fake_jira.statuses["In Review"] = "indeterminate"
        key = fake_jira.add_issue("Rev", status="In Review")
        assert _refs(_list(tmp_path, "--status", "in progress")) == [key]
        assert _refs(_list(tmp_path, "--status", "todo")) == []
        printed = _view_json(_list(tmp_path))
        assert [i["status"] for i in printed] == ["in progress"]

    def test_status_matches_printed_status_for_in_progress(self, fake_jira, tmp_path):
        a = fake_jira.add_issue("A", status="In Progress")
        fake_jira.add_issue("B", status="Blocked")
        assert _refs(_list(tmp_path, "--status", "in progress")) == [a]

    def test_label_filter(self, fake_jira, tmp_path):  # AC7
        a = fake_jira.add_issue("A", labels=["kind:task"])
        fake_jira.add_issue("B", labels=["other"])
        c = fake_jira.add_issue("C", labels=["kind:task", "x"])
        assert _refs(_list(tmp_path, "--label", "kind:task")) == [a, c]

    def test_label_with_quote_is_escaped_not_a_jql_error(self, fake_jira, tmp_path):
        a = fake_jira.add_issue("A", labels=['we"ird'])
        fake_jira.add_issue("B", labels=["plain"])
        r = _list(tmp_path, "--label", 'we"ird')
        assert _refs(r) == [a]

    def test_label_and_status_combine(self, fake_jira, tmp_path):
        a = fake_jira.add_issue("A", labels=["k"], status="To Do")
        fake_jira.add_issue("B", labels=["k"], status="In Progress")
        fake_jira.add_issue("C", labels=["z"], status="To Do")
        assert _refs(_list(tmp_path, "--label", "k", "--status", "todo")) == [a]

    def test_open_means_status_category_not_done(self, fake_jira, tmp_path):
        a = fake_jira.add_issue("A", status="To Do")
        b = fake_jira.add_issue("B", status="In Progress")
        fake_jira.add_issue("C", status="Done")
        assert _refs(_list(tmp_path)) == [a, b]
        post = [c for c in fake_jira.calls() if c["path"].endswith("/search/jql")]
        assert post and all("project" in c["body"]["jql"] for c in post)
        assert "statusCategory != Done" in post[0]["body"]["jql"]

    def test_status_done_returns_done_issues(self, fake_jira, tmp_path):
        fake_jira.add_issue("A", status="To Do")
        d = fake_jira.add_issue("D", status="Done")
        assert _refs(_list(tmp_path, "--status", "done")) == [d]
        post = next(c for c in fake_jira.calls() if c["path"].endswith("/search/jql"))
        assert "statusCategory = Done" in post["body"]["jql"]

    def test_list_order_follows_rank(self, fake_jira, tmp_path):  # V5, AC6
        a = fake_jira.add_issue("A")
        b = fake_jira.add_issue("B")
        c = fake_jira.add_issue("C")
        assert _refs(_list(tmp_path)) == [a, b, c]
        fake_jira.set_rank(c, 0.5)
        fake_jira.set_rank(a, 10)
        assert _refs(_list(tmp_path)) == [c, b, a]

    def test_caps_at_100_across_pages(self, fake_jira, tmp_path):  # V2, AC8
        keys = [fake_jira.add_issue(f"I{n}") for n in range(130)]
        refs = _refs(_list(tmp_path))
        assert len(refs) == 100
        assert refs == keys[:100]

    def test_cap_applies_to_filtered_results(self, fake_jira, tmp_path):
        for n in range(130):
            fake_jira.add_issue(f"I{n}", labels=["k"] if n % 2 else [])
        assert len(_refs(_list(tmp_path, "--label", "k"))) == 65

    def test_status_filter_in_code_still_fills_the_cap(self, fake_jira, tmp_path):
        fake_jira.statuses["In Review"] = "indeterminate"
        for n in range(250):
            fake_jira.add_issue(f"R{n}", status="In Review" if n % 2 == 0 else "To Do")
        # 125 match; the 100 come from scanning past the first page (In Review maps to in progress)
        assert len(_refs(_list(tmp_path, "--status", "in progress"))) == 100

    def test_search_failure_is_an_error_line(self, fake_jira, tmp_path):
        fake_jira.add_issue("A")
        fake_jira.fail_next(500, "boom")
        r = _list(tmp_path)
        assert r.returncode == 1
        assert r.stderr.startswith("Error:")
        assert "Traceback" not in r.stderr
        assert r.stdout == ""

    def test_list_does_not_write(self, fake_jira, tmp_path):
        fake_jira.add_issue("A")
        _list(tmp_path)
        assert _writes(fake_jira) == []
