"""#131 — JiraClient and Jira backend registration (LLD v3-e3-2 §1.2, invariants J1-J6).

Runs against the `fake_jira` fixture (local HTTPS http.server), not respx: the plugin is
standard-library only, so respx (which mocks httpx) cannot intercept it (ADR-0041).
"""

from __future__ import annotations

import base64
import pathlib
import re
import subprocess
import sys

import pytest

from _jira_client import JiraClient
from _tracker_contract import TrackerError
from tracker import JiraConfig

BIN_DIR = pathlib.Path(__file__).resolve().parent.parent / "plugins" / "edf" / "bin"
TRACKER = BIN_DIR / "tracker.py"

pytestmark = pytest.mark.skipif(sys.platform == "win32", reason="fake_jira / fake_gh are POSIX only")

ISSUE_PATH = "/rest/api/3/issue/SCRUM-1"


def _client(fake, *, timeout: float = 5.0) -> JiraClient:
    env = fake.env
    cfg = JiraConfig(env["JIRA_HOST"], env["JIRA_EMAIL"], env["JIRA_API_TOKEN"], env["JIRA_SPACE"])
    return JiraClient(cfg, timeout=timeout)


def _b64(fake) -> str:
    return base64.b64encode(f"{fake.email}:{fake.token}".encode()).decode()


def _run_tracker(cwd, *args):
    return subprocess.run([sys.executable, str(TRACKER), *args], cwd=cwd, capture_output=True, text=True, timeout=30)


def _error_text(fake, **kw) -> str:
    """Request the seeded issue and return the TrackerError message (fails if none raised)."""
    with pytest.raises(TrackerError) as info:
        _client(fake, **kw).request("GET", ISSUE_PATH)
    return str(info.value)


class TestJiraClient:
    def test_success_returns_status_and_parsed_body(self, fake_jira):
        key = fake_jira.add_issue("Hello")
        status, body = _client(fake_jira).request("GET", f"/rest/api/3/issue/{key}")
        assert status == 200
        assert body["key"] == key

    def test_sends_basic_auth_built_from_email_and_token(self, fake_jira):
        fake_jira.add_issue()
        _client(fake_jira).request("GET", ISSUE_PATH)
        (call,) = fake_jira.calls()
        assert call["authorization"] == f"Basic {_b64(fake_jira)}"

    def test_sends_query_and_json_body(self, fake_jira):
        fake_jira.add_issue()
        _client(fake_jira).request("GET", ISSUE_PATH, query={"fields": "summary"})
        status, body = _client(fake_jira).request(
            "POST", "/rest/api/3/issue",
            body={"fields": {"project": {"key": "SCRUM"}, "summary": "S", "issuetype": {"name": "Task"}}},
        )
        assert status == 201
        calls = fake_jira.calls()
        assert calls[0]["query"] == {"fields": "summary"}
        assert calls[1]["body"]["fields"]["summary"] == "S"
        assert body["key"].startswith("SCRUM-")

    def test_204_returns_none_body(self, fake_jira):
        fake_jira.add_issue()
        status, body = _client(fake_jira).request("PUT", ISSUE_PATH, body={"fields": {"summary": "New"}})
        assert (status, body) == (204, None)

    @pytest.mark.parametrize("status", [401, 403])
    def test_maps_401_and_403_to_authentication_error(self, fake_jira, status):
        fake_jira.fail_next(status)
        assert _error_text(fake_jira) == f"Jira authentication failed ({status})"

    def test_wrong_credentials_are_an_authentication_error(self, fake_jira):
        fake_jira.add_issue()
        env = fake_jira.env
        client = JiraClient(JiraConfig(env["JIRA_HOST"], env["JIRA_EMAIL"], "wrong-token", env["JIRA_SPACE"]), timeout=5)
        with pytest.raises(TrackerError, match=r"^Jira authentication failed \(401\)$"):
            client.request("GET", ISSUE_PATH)

    @pytest.mark.parametrize("status", [429, 500, 502, 503])
    def test_maps_429_and_5xx_to_request_failed_without_retry(self, fake_jira, status):
        """J3: exactly one request."""
        fake_jira.fail_next(status)
        assert _error_text(fake_jira) == f"Jira request failed ({status})"
        assert len(fake_jira.calls()) == 1

    @pytest.mark.parametrize("status", [301, 302, 307])
    def test_does_not_follow_a_redirect(self, fake_jira, status):
        """J2: one request only; the credentials never reach the Location."""
        fake_jira.add_issue()
        fake_jira.add_issue()
        fake_jira.redirect_next("/rest/api/3/issue/SCRUM-2", status=status)
        assert _error_text(fake_jira) == f"Jira request failed ({status})"
        assert len(fake_jira.calls()) == 1

    def test_returns_404_to_the_caller_instead_of_raising(self, fake_jira):
        assert _client(fake_jira).request("GET", "/rest/api/3/issue/SCRUM-99") == (404, None)

    def test_other_4xx_includes_detail(self, fake_jira):
        fake_jira.fail_next(400, body="bad field")
        assert _error_text(fake_jira) == "Jira request failed (400): bad field"

    @pytest.mark.parametrize("status", [400, 401, 403, 429, 500])
    def test_redacts_token_and_credential_from_echoed_error_body(self, fake_jira, status):
        """J1: the fake echoes the Authorization header into the error body."""
        fake_jira.fail_next(status, echo_auth=True)
        with pytest.raises(TrackerError) as info:
            _client(fake_jira).request("GET", ISSUE_PATH)
        message = str(info.value)
        assert fake_jira.token not in message
        assert _b64(fake_jira) not in message

    def test_echoed_detail_is_replaced_with_stars(self, fake_jira):
        fake_jira.fail_next(400, body="bad", echo_auth=True)
        message = _error_text(fake_jira)
        assert message.startswith("Jira request failed (400): bad")
        assert "***" in message

    def test_other_4xx_detail_is_cut_to_200_characters(self, fake_jira):
        fake_jira.fail_next(400, body="x" * 500)
        message = _error_text(fake_jira)
        prefix = "Jira request failed (400): "
        assert message.startswith(prefix)
        assert len(message) - len(prefix) <= 200
        assert "x" * 200 in message
        assert "x" * 201 not in message

    def test_redaction_happens_before_the_cut(self, fake_jira):
        """A credential straddling the 200-char boundary must not leak as a fragment."""
        fake_jira.fail_next(400, body="y" * 180, echo_auth=True)
        message = _error_text(fake_jira)
        assert fake_jira.token not in message
        assert _b64(fake_jira)[:12] not in message

    def test_unreachable_host_timeout_reports_cannot_reach(self, fake_jira):
        """J6: a slow server fails with a named error rather than hanging."""
        fake_jira.add_issue()
        fake_jira.delay_next(2.0)
        message = _error_text(fake_jira, timeout=0.3)
        assert message.startswith("Jira request failed: cannot reach ")
        assert "localhost" in message
        assert fake_jira.token not in message

    def test_connection_refused_reports_cannot_reach(self, fake_jira):
        cfg = JiraConfig("https://127.0.0.1:1", fake_jira.email, fake_jira.token, fake_jira.space)
        with pytest.raises(TrackerError, match=r"^Jira request failed: cannot reach 127\.0\.0\.1"):
            JiraClient(cfg, timeout=2).request("GET", ISSUE_PATH)

    def test_repr_has_no_token_or_credential(self, fake_jira):
        client = _client(fake_jira)
        text = f"{client!r} {client}"
        assert fake_jira.token not in text
        assert _b64(fake_jira) not in text


class TestSourceInvariants:
    def test_jira_client_source_has_no_jira_env_names(self):
        """J5: `_jira_client.py` must not contain the text `JIRA_`."""
        assert "JIRA_" not in (BIN_DIR / "_jira_client.py").read_text(encoding="utf-8")

    def test_only_jira_client_imports_urllib_or_http(self):
        """J4."""
        pattern = re.compile(r"^\s*(import|from) (urllib|http)", re.MULTILINE)
        for name in ("_tracker_jira.py", "_adf.py"):
            assert not pattern.search((BIN_DIR / name).read_text(encoding="utf-8")), name
        assert pattern.search((BIN_DIR / "_jira_client.py").read_text(encoding="utf-8"))


class TestRegistration:
    def test_dispatches_to_the_jira_backend_when_jira_host_is_set(self, fake_gh, fake_jira):
        result = _run_tracker(fake_gh.repo, "tracker")
        assert (result.returncode, result.stdout) == (0, "jira\n")

    @pytest.mark.parametrize(
        "argv",
        [["view", "1"], ["list"], ["create", "--title", "T", "--body", "B"], ["edit", "1", "--title", "T"],
         ["comment", "1", "--body", "B"], ["status", "1", "todo"], ["close", "1"]],
        ids=lambda a: a[0],
    )
    def test_stub_operation_fails_not_implemented_with_no_gh_call(self, fake_gh, fake_jira, argv):
        result = _run_tracker(fake_gh.repo, *argv)
        assert result.returncode == 1
        assert result.stderr == "Error: not implemented\n"
        assert result.stdout == ""
        assert fake_gh.calls() == []
        assert "Jira backend is not available" not in result.stderr

    def test_keeps_the_github_backend_when_jira_host_is_unset(self, fake_gh):
        result = _run_tracker(fake_gh.repo, "tracker")
        assert (result.returncode, result.stdout) == (0, "github\n")
