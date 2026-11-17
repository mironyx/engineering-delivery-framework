"""#132 — Jira backend `create` (LLD v3-e3-2 §1.3, invariants C1-C5).

Runs tracker.py as a subprocess against the `fake_jira` fixture (local HTTPS http.server), not
respx: the plugin is standard-library only (ADR-0041).
"""

from __future__ import annotations

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
