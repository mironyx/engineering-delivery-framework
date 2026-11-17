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
EIGHT_KEYS = ["ref", "title", "body", "labels", "status", "parent", "children", "child_statuses"]


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
    def test_returns_eight_key_json_for_task_with_parent(self, fake_jira, tmp_path):  # V1, AC1
        epic = fake_jira.add_issue("Epic", type="Epic")
        key = fake_jira.add_issue("Child", labels=["kind:task", "x"], parent=epic, description=_doc("hello"))
        data = _view_json(_view(tmp_path, key))
        assert list(data.keys()) == EIGHT_KEYS
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


class TestViewChildStatuses:
    """#144 — Jira view fills child_statuses from the existing child search (+0 requests)."""

    def test_maps_each_child_through_status_of(self, fake_jira, tmp_path):
        epic = fake_jira.add_issue("Epic", type="Epic")
        a = fake_jira.add_issue("A", parent=epic, status="Done")
        b = fake_jira.add_issue("B", parent=epic, status="In Progress")
        c = fake_jira.add_issue("C", parent=epic, status="To Do")
        fake_jira.statuses["In Review"] = "indeterminate"
        d = fake_jira.add_issue("D", parent=epic, status="In Review")
        data = _view_json(_view(tmp_path, epic))
        assert data["children"] == [a, b, c, d]
        assert data["child_statuses"] == {a: "done", b: "in progress", c: "todo", d: "in progress"}
        assert list(data["child_statuses"]) == data["children"]

    def test_keys_are_a_subset_of_children(self, fake_jira, tmp_path):  # I8
        epic = fake_jira.add_issue("Epic", type="Epic")
        other = fake_jira.add_issue("Elsewhere")
        fake_jira.add_issue("Sub", parent=other)
        fake_jira.add_issue("Child", parent=epic)
        data = _view_json(_view(tmp_path, epic))
        assert set(data["child_statuses"]) <= set(data["children"])

    @pytest.mark.parametrize("count", [1, 20])
    def test_request_count_for_an_epic_view_does_not_depend_on_child_count(self, fake_jira, tmp_path, count):  # I7
        epic = fake_jira.add_issue("Epic", type="Epic")
        for n in range(count):
            fake_jira.add_issue(f"C{n}", parent=epic)
        before = len(fake_jira.calls())
        data = _view_json(_view(tmp_path, epic))
        assert len(data["child_statuses"]) == count
        assert len(fake_jira.calls()) - before == 2  # the issue GET and one child search

    def test_request_counts_are_equal_for_one_and_twenty_children(self, fake_jira, tmp_path):
        counts = []
        for count in (1, 20):
            epic = fake_jira.add_issue(f"Epic {count}", type="Epic")
            for n in range(count):
                fake_jira.add_issue(f"C{count}-{n}", parent=epic)
            before = len(fake_jira.calls())
            _view_json(_view(tmp_path, epic))
            counts.append(len(fake_jira.calls()) - before)
        assert counts[0] == counts[1]

    def test_child_search_requests_the_status_field(self, fake_jira, tmp_path):
        epic = fake_jira.add_issue("Epic", type="Epic")
        fake_jira.add_issue("C", parent=epic)
        _view_json(_view(tmp_path, epic))
        searches = [c for c in fake_jira.calls() if c["path"].endswith("/search/jql")]
        assert len(searches) == 1
        assert "status" in searches[0]["body"]["fields"]

    def test_non_epic_has_empty_child_statuses(self, fake_jira, tmp_path):
        task = fake_jira.add_issue("Task", type="Task")
        fake_jira.add_issue("Sub", parent=task)
        assert _view_json(_view(tmp_path, task))["child_statuses"] == {}

    def test_epic_without_children_has_empty_child_statuses(self, fake_jira, tmp_path):
        epic = fake_jira.add_issue("Epic", type="Epic")
        assert _view_json(_view(tmp_path, epic))["child_statuses"] == {}

    def test_list_carries_empty_child_statuses_for_epics(self, fake_jira, tmp_path):
        epic = fake_jira.add_issue("Epic", type="Epic")
        fake_jira.add_issue("Child", parent=epic, status="Done")
        items = {i["ref"]: i for i in _view_json(_list(tmp_path))}
        assert items[epic]["child_statuses"] == {}


class TestList:
    def test_each_element_has_eight_keys_in_order(self, fake_jira, tmp_path):  # V1
        epic = fake_jira.add_issue("Epic", type="Epic", labels=["epic"])
        fake_jira.add_issue("Child", parent=epic, description=_doc("hi"))
        items = _view_json(_list(tmp_path))
        assert len(items) == 2
        for item in items:
            assert list(item.keys()) == EIGHT_KEYS
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


# ---- #134 — Jira backend edit, comment, status, close (LLD v3-e3-2 §1.5, invariants W1-W6) ----


def _edit(cwd, ref, *args):
    return _run(cwd, "edit", ref, *args)


def _comment(cwd, ref, body="A **note**"):
    return _run(cwd, "comment", ref, "--body", body)


def _status(cwd, ref, status, *extra):
    return _run(cwd, "status", ref, status, *extra)


def _close(cwd, ref):
    return _run(cwd, "close", ref)


def _puts(fake):
    return [c for c in fake.calls() if c["method"] == "PUT"]


def _transition_posts(fake):
    return [c for c in fake.calls() if c["method"] == "POST" and c["path"].endswith("/transitions")]


def _not_found(result, key):
    assert result.returncode == 1
    assert result.stderr.strip() == f"Error: {key} not found"


class TestEdit:
    def test_replaces_body_as_adf_and_prints_updated(self, fake_jira, tmp_path):  # W4
        key = fake_jira.add_issue("T")
        r = _edit(tmp_path, key, "--body", "New **body**")
        assert r.returncode == 0, r.stderr
        assert r.stdout.strip() == f"updated:{key}"
        sent = _puts(fake_jira)[0]["body"]["fields"]["description"]
        assert sent["type"] == "doc"
        assert fake_jira.issue(key)["description"]["type"] == "doc"

    def test_adds_and_removes_labels_in_one_put_and_leaves_others(self, fake_jira, tmp_path):
        key = fake_jira.add_issue("T", labels=["b", "keep"])
        r = _edit(tmp_path, key, "--add-label", "a", "--remove-label", "b")
        assert r.stdout.strip() == f"updated:{key}"
        assert sorted(fake_jira.issue(key)["labels"]) == ["a", "keep"]
        assert len(_puts(fake_jira)) == 1
        ops = _puts(fake_jira)[0]["body"]["update"]["labels"]
        assert {"add": "a"} in ops and {"remove": "b"} in ops

    def test_skips_removal_of_a_label_the_issue_lacks(self, fake_jira, tmp_path):  # W1
        key = fake_jira.add_issue("T", labels=["keep"])
        r = _edit(tmp_path, key, "--add-label", "a", "--remove-label", "ghost")
        assert r.returncode == 0, r.stderr
        assert r.stdout.strip() == f"updated:{key}"
        for put in _puts(fake_jira):
            ops = put["body"].get("update", {}).get("labels", [])
            assert not any(op.get("remove") == "ghost" for op in ops)
        assert sorted(fake_jira.issue(key)["labels"]) == ["a", "keep"]

    def test_removing_only_an_absent_label_succeeds_with_no_change(self, fake_jira, tmp_path):  # W1
        key = fake_jira.add_issue("T", labels=["keep"])
        r = _edit(tmp_path, key, "--remove-label", "ghost")
        assert r.returncode == 0, r.stderr
        assert r.stdout.strip() == f"updated:{key}"
        assert fake_jira.issue(key)["labels"] == ["keep"]
        assert not any(op.get("remove") == "ghost" for p in _puts(fake_jira)
                       for op in p["body"].get("update", {}).get("labels", []))

    def test_removes_only_the_present_labels_among_several(self, fake_jira, tmp_path):  # W1
        key = fake_jira.add_issue("T", labels=["x", "y"])
        _edit(tmp_path, key, "--remove-label", "x", "--remove-label", "ghost")
        assert fake_jira.issue(key)["labels"] == ["y"]
        removes = [op["remove"] for p in _puts(fake_jira) for op in p["body"]["update"]["labels"] if "remove" in op]
        assert removes == ["x"]

    def test_renames_the_issue_with_title(self, fake_jira, tmp_path):
        key = fake_jira.add_issue("Old")
        r = _edit(tmp_path, key, "--title", "New title")
        assert r.stdout.strip() == f"updated:{key}"
        assert fake_jira.issue(key)["summary"] == "New title"

    def test_edit_without_remove_label_does_not_read_the_issue(self, fake_jira, tmp_path):
        key = fake_jira.add_issue("T")
        assert _edit(tmp_path, key, "--add-label", "a").stdout.strip() == f"updated:{key}"
        assert [c for c in fake_jira.calls() if c["method"] == "GET"] == []

    def test_unknown_key_errors_before_writing(self, fake_jira, tmp_path):  # W6
        r = _edit(tmp_path, "SCRUM-99", "--body", "x")
        _not_found(r, "SCRUM-99")
        assert r.stdout == ""
        # LLD §1.5: without --remove-label the only request is the PUT that Jira rejects with 404,
        # so nothing is persisted (the call log records attempts, not outcomes).
        assert [(c["method"], c["path"]) for c in _writes(fake_jira)] == [("PUT", "/rest/api/3/issue/SCRUM-99")]

    def test_unknown_key_with_remove_label_errors_before_writing(self, fake_jira, tmp_path):  # W6
        r = _edit(tmp_path, "SCRUM-99", "--remove-label", "a")
        _not_found(r, "SCRUM-99")
        assert _writes(fake_jira) == []

    def test_accepts_lowercase_ref(self, fake_jira, tmp_path):
        key = fake_jira.add_issue("T")
        r = _edit(tmp_path, key.lower(), "--title", "Z")
        assert r.stdout.strip() == f"updated:{key}"


class TestComment:
    def test_posts_adf_comment_and_prints_commented(self, fake_jira, tmp_path):  # W4
        key = fake_jira.add_issue("T")
        r = _comment(tmp_path, key, "A **note**")
        assert r.returncode == 0, r.stderr
        assert r.stdout.strip() == f"commented:{key}"
        post = next(c for c in fake_jira.calls() if c["path"].endswith("/comment"))
        assert post["body"]["body"]["type"] == "doc"
        assert len(fake_jira.issue(key)["comments"]) == 1

    def test_comment_does_not_read_first(self, fake_jira, tmp_path):
        key = fake_jira.add_issue("T")
        assert _comment(tmp_path, key).stdout.strip() == f"commented:{key}"
        assert [c for c in fake_jira.calls() if c["method"] == "GET"] == []

    def test_unknown_key_errors_and_writes_nothing(self, fake_jira, tmp_path):  # W6
        r = _comment(tmp_path, "SCRUM-99")
        _not_found(r, "SCRUM-99")
        assert r.stdout == ""
        assert fake_jira.calls() == [] or all(c["path"].endswith("/SCRUM-99/comment") for c in fake_jira.calls())


class TestStatus:
    def test_moves_via_the_transition_to_the_mapped_status(self, fake_jira, tmp_path):
        key = fake_jira.add_issue("T")
        r = _status(tmp_path, key, "in progress")
        assert r.returncode == 0, r.stderr
        assert r.stdout.strip() == f"{key} → in progress"
        assert fake_jira.issue(key)["status"] == "In Progress"
        assert len(_transition_posts(fake_jira)) == 1

    @pytest.mark.parametrize("start,raw,expected_name", [
        ("To Do", "blocked", "Blocked"), ("In Progress", "done", "Done"),
        ("Done", "todo", "To Do"), ("Blocked", "in progress", "In Progress"),
    ])
    def test_moves_between_all_four_statuses(self, fake_jira, tmp_path, start, raw, expected_name):
        key = fake_jira.add_issue("T", status=start)
        r = _status(tmp_path, key, raw)
        assert r.returncode == 0, r.stderr
        assert r.stdout.strip() == f"{key} → {raw}"
        assert fake_jira.issue(key)["status"] == expected_name

    def test_status_value_is_case_insensitive(self, fake_jira, tmp_path):
        key = fake_jira.add_issue("T")
        assert _status(tmp_path, key, "DONE").returncode == 0
        assert fake_jira.issue(key)["status"] == "Done"

    def test_is_a_no_op_when_already_in_the_target_status(self, fake_jira, tmp_path):  # W2
        key = fake_jira.add_issue("T", status="In Progress")
        r = _status(tmp_path, key, "in progress")
        assert r.returncode == 0, r.stderr
        assert r.stdout.strip() == f"{key} → in progress"
        assert _transition_posts(fake_jira) == []
        assert _writes(fake_jira) == []

    def test_names_the_missing_blocked_status(self, fake_jira, tmp_path):  # W5
        fake_jira.set_workflow(with_blocked=False)
        key = fake_jira.add_issue("T")
        r = _status(tmp_path, key, "blocked")
        assert r.returncode == 1
        assert r.stderr.strip() == 'Error: space SCRUM has no "Blocked" status — add it to the workflow'
        assert _transition_posts(fake_jira) == []

    def test_names_current_and_target_when_no_transition_leads_there(self, fake_jira, tmp_path):  # W5
        fake_jira.set_workflow(transitions={"To Do": ["In Progress"], "In Progress": ["Done"],
                                            "Blocked": ["To Do"], "Done": ["To Do"]})
        key = fake_jira.add_issue("T", status="To Do")
        r = _status(tmp_path, key, "done")
        assert r.returncode == 1
        assert r.stderr.strip() == 'Error: no transition from "To Do" to "Done"'
        assert "has no" not in r.stderr
        assert _transition_posts(fake_jira) == []

    def test_lists_the_four_values_for_an_unknown_status(self, fake_jira, tmp_path):
        key = fake_jira.add_issue("T")
        r = _status(tmp_path, key, "wip")
        assert r.returncode == 1
        assert r.stderr.strip() == "Error: unknown status 'wip'. Use: todo | blocked | \"in progress\" | done"
        assert _writes(fake_jira) == []

    def test_unknown_key_errors_and_writes_nothing(self, fake_jira, tmp_path):  # W6
        r = _status(tmp_path, "SCRUM-99", "done")
        _not_found(r, "SCRUM-99")
        assert _writes(fake_jira) == []

    def test_add_to_board_is_accepted_and_ignored(self, fake_jira, tmp_path):
        key = fake_jira.add_issue("T")
        r = _status(tmp_path, key, "done", "--add-to-board")
        assert r.returncode == 0, r.stderr
        assert r.stdout.strip() == f"{key} → done"
        assert r.stderr == ""
        assert fake_jira.issue(key)["status"] == "Done"


class TestClose:
    def test_transitions_to_done_and_prints_closed(self, fake_jira, tmp_path):
        key = fake_jira.add_issue("T", status="In Progress")
        r = _close(tmp_path, key)
        assert r.returncode == 0, r.stderr
        assert r.stdout.strip() == f"closed:{key}"
        assert fake_jira.issue(key)["status"] == "Done"

    def test_is_a_no_op_for_an_issue_already_done(self, fake_jira, tmp_path):  # W3
        key = fake_jira.add_issue("T", status="Done")
        r = _close(tmp_path, key)
        assert r.returncode == 0, r.stderr
        assert r.stdout.strip() == f"closed:{key}"
        assert _writes(fake_jira) == []
        assert all(c["method"] == "GET" and c["path"].endswith(f"/issue/{key}") for c in fake_jira.calls())

    def test_closing_twice_is_idempotent(self, fake_jira, tmp_path):  # W3
        key = fake_jira.add_issue("T")
        assert _close(tmp_path, key).stdout.strip() == f"closed:{key}"
        writes_after_first = len(_writes(fake_jira))
        assert _close(tmp_path, key).stdout.strip() == f"closed:{key}"
        assert len(_writes(fake_jira)) == writes_after_first

    def test_unknown_key_errors_with_nothing_written(self, fake_jira, tmp_path):  # W6
        r = _close(tmp_path, "SCRUM-99")
        _not_found(r, "SCRUM-99")
        assert r.stdout == ""
        assert _writes(fake_jira) == []

    def test_close_without_a_done_transition_names_current_and_target(self, fake_jira, tmp_path):  # W5
        fake_jira.set_workflow(transitions={"To Do": ["In Progress"], "In Progress": ["To Do"],
                                            "Blocked": ["To Do"], "Done": ["To Do"]})
        key = fake_jira.add_issue("T")
        r = _close(tmp_path, key)
        assert r.returncode == 1
        assert r.stderr.strip() == 'Error: no transition from "To Do" to "Done"'
