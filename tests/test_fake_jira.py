"""Self-tests for the `fake_jira` fixture (issue #130): the fake must follow the spec shapes and
reject anything outside the JQL grammar, otherwise the Jira backend tests built on it prove nothing."""

import base64
import json
import os
import socket
import ssl
import urllib.error
import urllib.request

import pytest

from tests.fixtures.fake_jira import FakeJiraSetupError, generate_certificate

API = "/rest/api/3"


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None


def call(fake, method, path, body=None, *, auth=True, timeout=10):
    """One real HTTPS request using only OS-level trust (SSL_CERT_FILE) — returns (status, json | None, headers)."""
    headers = {"Content-Type": "application/json", "Accept": "application/json"}
    if auth:
        creds = base64.b64encode(f"{fake.email}:{fake.token}".encode()).decode()
        headers["Authorization"] = f"Basic {creds}"
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(os.environ["JIRA_HOST"] + path, data=data, headers=headers, method=method)
    try:
        resp = urllib.request.build_opener(_NoRedirect()).open(req, timeout=timeout)
    except urllib.error.HTTPError as err:
        resp = err
    raw = resp.read()
    return resp.status if hasattr(resp, "status") else resp.code, (json.loads(raw) if raw else None), resp.headers


def search(fake, jql, **extra):
    return call(fake, "POST", f"{API}/search/jql", {"jql": jql, **extra})


def keys(payload):
    return [i["key"] for i in payload["issues"]]


def create_body(summary="Do it", type_="Task", **fields):
    return {"fields": {"project": {"key": "SCRUM"}, "summary": summary, "issuetype": {"name": type_}, **fields}}


# --- fixture wiring -------------------------------------------------------------------------

def test_fixture_sets_jira_env_and_trust_anchor(fake_jira):
    assert os.environ["JIRA_HOST"].startswith("https://localhost:")
    assert os.environ["JIRA_EMAIL"] and os.environ["JIRA_SPACE"] == "SCRUM"
    assert os.environ["JIRA_API_TOKEN"] == "tok-SECRET"
    assert os.path.isfile(os.environ["SSL_CERT_FILE"])
    assert fake_jira.env["JIRA_HOST"] == os.environ["JIRA_HOST"]


def test_tls_is_verified_against_generated_certificate(fake_jira):
    status, _, _ = call(fake_jira, "GET", f"{API}/project/SCRUM/statuses")
    assert status == 200


def test_untrusted_client_cannot_connect(fake_jira, monkeypatch, tmp_path):
    """Without the cert as trust anchor the handshake must fail — tests cannot silently skip verification."""
    other = tmp_path / "other.pem"
    other.write_text("")
    monkeypatch.setenv("SSL_CERT_FILE", str(other))
    monkeypatch.setenv("SSL_CERT_DIR", str(tmp_path))
    ctx = ssl.create_default_context()
    port = int(os.environ["JIRA_HOST"].rsplit(":", 1)[1])
    with pytest.raises(ssl.SSLError), socket.create_connection(("localhost", port), timeout=5) as sock:
        ctx.wrap_socket(sock, server_hostname="localhost")


def test_missing_openssl_fails_loudly(tmp_path, monkeypatch):
    monkeypatch.setenv("PATH", str(tmp_path))
    with pytest.raises(FakeJiraSetupError, match="openssl"):
        generate_certificate(tmp_path)


# --- issue endpoints ------------------------------------------------------------------------

def test_create_returns_201_with_id_key_self_and_view_roundtrips(fake_jira):
    status, body, _ = call(fake_jira, "POST", f"{API}/issue", create_body("First", labels=["a"]))
    assert status == 201 and body["key"] == "SCRUM-1" and body["id"] and body["self"]
    status, issue, _ = call(fake_jira, "GET", f"{API}/issue/SCRUM-1")
    assert status == 200
    assert issue["fields"]["summary"] == "First"
    assert issue["fields"]["status"] == {"name": "To Do", "id": "1000", "statusCategory": {"key": "new", "name": "To Do"}}
    assert issue["fields"]["labels"] == ["a"] and issue["fields"]["issuetype"] == {"name": "Task"}


def test_create_validation_errors_are_400_with_errors_map(fake_jira):
    status, body, _ = call(fake_jira, "POST", f"{API}/issue", create_body(""))
    assert status == 400 and "summary" in body["errors"]
    status, body, _ = call(fake_jira, "POST", f"{API}/issue", create_body("x", type_="Bug"))
    assert status == 400 and "issuetype" in body["errors"]
    status, body, _ = call(fake_jira, "POST", f"{API}/issue", create_body("x", parent={"key": "SCRUM-99"}))
    assert status == 400 and "parent" in body["errors"]


def test_view_missing_issue_is_404(fake_jira):
    status, body, _ = call(fake_jira, "GET", f"{API}/issue/SCRUM-404")
    assert status == 404 and body["errorMessages"]


def test_view_honours_fields_parameter(fake_jira):
    key = fake_jira.add_issue("S", labels=["x"])
    _, issue, _ = call(fake_jira, "GET", f"{API}/issue/{key}?fields=summary,labels")
    assert set(issue["fields"]) == {"summary", "labels"}


def test_edit_sets_fields_and_adds_removes_labels_with_204(fake_jira):
    key = fake_jira.add_issue("Old", labels=["keep", "drop"])
    body = {"fields": {"summary": "New", "description": {"type": "doc", "version": 1, "content": []}},
            "update": {"labels": [{"add": "new"}, {"remove": "drop"}]}}
    status, payload, _ = call(fake_jira, "PUT", f"{API}/issue/{key}", body)
    assert status == 204 and payload is None
    rec = fake_jira.issue(key)
    assert rec["summary"] == "New" and rec["labels"] == ["keep", "new"] and rec["description"]["type"] == "doc"


def test_edit_unknown_field_is_400_and_missing_issue_404(fake_jira):
    key = fake_jira.add_issue()
    status, _, _ = call(fake_jira, "PUT", f"{API}/issue/{key}", {"fields": {"duedate": "x"}})
    assert status == 400
    status, _, _ = call(fake_jira, "PUT", f"{API}/issue/SCRUM-77", {"fields": {"summary": "x"}})
    assert status == 404


def test_comment_returns_201_and_rejects_non_adf(fake_jira):
    key = fake_jira.add_issue()
    adf = {"type": "doc", "version": 1, "content": []}
    status, body, _ = call(fake_jira, "POST", f"{API}/issue/{key}/comment", {"body": adf})
    assert status == 201 and body["id"] and fake_jira.issue(key)["comments"][0]["body"] == adf
    status, _, _ = call(fake_jira, "POST", f"{API}/issue/{key}/comment", {"body": "plain text"})
    assert status == 400
    status, _, _ = call(fake_jira, "POST", f"{API}/issue/SCRUM-77/comment", {"body": adf})
    assert status == 404


# --- transitions and workflow ---------------------------------------------------------------

def test_transitions_list_then_apply_changes_status(fake_jira):
    key = fake_jira.add_issue()
    _, listing, _ = call(fake_jira, "GET", f"{API}/issue/{key}/transitions")
    by_name = {t["name"]: t for t in listing["transitions"]}
    assert set(by_name) == {"In Progress", "Blocked", "Done"}
    assert by_name["Done"]["to"]["statusCategory"]["key"] == "done"
    status, body, _ = call(fake_jira, "POST", f"{API}/issue/{key}/transitions", {"transition": {"id": by_name["Done"]["id"]}})
    assert status == 204 and body is None
    assert fake_jira.issue(key)["status"] == "Done"


def test_unknown_transition_id_is_400_and_missing_issue_404(fake_jira):
    key = fake_jira.add_issue()
    status, _, _ = call(fake_jira, "POST", f"{API}/issue/{key}/transitions", {"transition": {"id": "999"}})
    assert status == 400 and fake_jira.issue(key)["status"] == "To Do"
    status, _, _ = call(fake_jira, "GET", f"{API}/issue/SCRUM-77/transitions")
    assert status == 404


def test_workflow_without_blocked_hides_it_from_transitions_and_statuses(fake_jira):
    fake_jira.set_workflow(with_blocked=False)
    key = fake_jira.add_issue()
    _, listing, _ = call(fake_jira, "GET", f"{API}/issue/{key}/transitions")
    assert "Blocked" not in {t["name"] for t in listing["transitions"]}
    _, statuses, _ = call(fake_jira, "GET", f"{API}/project/SCRUM/statuses")
    assert "Blocked" not in {s["name"] for s in statuses[0]["statuses"]}


def test_custom_transition_graph_limits_moves(fake_jira):
    fake_jira.set_workflow(transitions={"To Do": ["In Progress"], "In Progress": ["Done"], "Blocked": [], "Done": []})
    key = fake_jira.add_issue()
    _, listing, _ = call(fake_jira, "GET", f"{API}/issue/{key}/transitions")
    assert [t["name"] for t in listing["transitions"]] == ["In Progress"]


def test_project_statuses_groups_by_issue_type_and_404s_other_projects(fake_jira):
    status, body, _ = call(fake_jira, "GET", f"{API}/project/SCRUM/statuses")
    assert status == 200 and {g["name"] for g in body} == {"Task", "Epic"}
    assert call(fake_jira, "GET", f"{API}/project/OTHER/statuses")[0] == 404


# --- search: JQL grammar, rank order, paging ------------------------------------------------

def test_search_returns_rank_order_not_creation_or_key_order(fake_jira):
    a, b, c = (fake_jira.add_issue(s) for s in ("A", "B", "C"))
    fake_jira.set_rank(c, 0.5)
    _, out, _ = search(fake_jira, 'project = "SCRUM" ORDER BY Rank ASC')
    assert keys(out) == [c, a, b]


def test_search_filters_each_supported_clause(fake_jira):
    epic = fake_jira.add_issue("Epic one", type="Epic")
    t1 = fake_jira.add_issue("Fix login bug", labels=["blocked"], parent=epic)
    t2 = fake_jira.add_issue("Other thing", status="Done")
    cases = {
        'project = "SCRUM" AND issuetype = "Epic"': [epic],
        'project = "SCRUM" AND summary ~ "\\"login\\""': [t1],
        'project = "SCRUM" AND status = "Done"': [t2],
        'project = "SCRUM" AND statusCategory = Done': [t2],
        'project = "SCRUM" AND statusCategory != Done': [epic, t1],
        'project = "SCRUM" AND labels = "blocked"': [t1],
        f'project = "SCRUM" AND parent = {epic}': [t1],
        'project = "OTHER"': [],
    }
    for jql, expected in cases.items():
        status, out, _ = search(fake_jira, jql)
        assert (status, keys(out)) == (200, expected), jql


def test_search_honours_string_escapes(fake_jira):
    k = fake_jira.add_issue('He said "hi"')
    _, out, _ = search(fake_jira, 'project = "SCRUM" AND summary ~ "He said \\"hi\\""')
    assert keys(out) == [k]


@pytest.mark.parametrize("jql", [
    "",
    "order by rank",
    'summary ~ "x"',                                   # unbounded: no project clause
    'project = "SCRUM" OR labels = "a"',               # OR is outside the grammar
    'project = "SCRUM" AND assignee = "me"',           # unsupported field
    'project = "SCRUM" AND status ~ "Done"',           # wrong operator for field
    'project = "SCRUM" AND summary = "x"',             # `=` is not supported on text fields
    'project = SCRUM',                                 # value must be quoted
    'project = "SCRUM" AND statusCategory = "Done"',   # must be bare
    'project = "SCRUM" AND statusCategory = Open',
    'project = "SCRUM" AND parent = "SCRUM-1"',
    'project = "SCRUM" AND parent = nonsense',
    'project = "SCRUM" AND',
    'project = "SCRUM" ORDER BY Rank DESC',
    'project = "SCRUM" ORDER BY created ASC',
    'project = "SCRUM" AND labels = "a\\x"',           # unsupported escape
    'project = "SCRUM" ; drop',
    'project = "SCRUM" AND labels IN ("a")',
])
def test_search_rejects_jql_outside_grammar_with_400(fake_jira, jql):
    fake_jira.add_issue()
    status, body, _ = search(fake_jira, jql)
    assert status == 400 and body["errorMessages"] and "issues" not in body


def test_search_pages_with_next_page_token_until_is_last(fake_jira):
    created = [fake_jira.add_issue(f"T{i}") for i in range(5)]
    _, p1, _ = search(fake_jira, 'project = "SCRUM"', maxResults=2)
    assert keys(p1) == created[:2] and p1["isLast"] is False and p1["nextPageToken"]
    _, p2, _ = search(fake_jira, 'project = "SCRUM"', maxResults=2, nextPageToken=p1["nextPageToken"])
    assert keys(p2) == created[2:4] and p2["isLast"] is False
    _, p3, _ = search(fake_jira, 'project = "SCRUM"', maxResults=2, nextPageToken=p2["nextPageToken"])
    assert keys(p3) == created[4:] and p3["isLast"] is True and "nextPageToken" not in p3


def test_search_exact_page_boundary_is_last(fake_jira):
    for i in range(4):
        fake_jira.add_issue(f"T{i}")
    _, out, _ = search(fake_jira, 'project = "SCRUM"', maxResults=4)
    assert out["isLast"] is True and "nextPageToken" not in out


def test_search_rejects_bad_token_and_bad_max_results(fake_jira):
    assert search(fake_jira, 'project = "SCRUM"', nextPageToken="garbage")[0] == 400
    assert search(fake_jira, 'project = "SCRUM"', maxResults=0)[0] == 400


def test_search_returns_only_id_and_key_unless_fields_requested(fake_jira):
    fake_jira.add_issue("S", labels=["l"])
    _, bare, _ = search(fake_jira, 'project = "SCRUM"')
    assert bare["issues"][0]["fields"] == {} and bare["issues"][0]["key"] == "SCRUM-1"
    _, full, _ = search(fake_jira, 'project = "SCRUM"', fields=["summary", "status"])
    assert set(full["issues"][0]["fields"]) == {"summary", "status"}


# --- auth, unsupported routes, request log --------------------------------------------------

def test_missing_credentials_are_401(fake_jira):
    assert call(fake_jira, "GET", f"{API}/project/SCRUM/statuses", auth=False)[0] == 401


def test_unsupported_endpoint_is_501_not_404(fake_jira):
    status, body, _ = call(fake_jira, "GET", f"{API}/myself")
    assert status == 501 and "does not implement" in body["errorMessages"][0]


def test_request_log_records_method_path_query_body_and_auth(fake_jira):
    call(fake_jira, "POST", f"{API}/issue", create_body("Logged"))
    call(fake_jira, "GET", f"{API}/issue/SCRUM-1?fields=summary", auth=False)
    first, second = fake_jira.calls()
    assert (first["method"], first["path"], first["has_auth"]) == ("POST", f"{API}/issue", True)
    assert first["body"]["fields"]["summary"] == "Logged"
    assert first["authorization"].startswith("Basic ")
    assert (second["query"], second["has_auth"], second["authorization"]) == ({"fields": "summary"}, False, None)


# --- fault injection ------------------------------------------------------------------------

def test_fail_next_answers_once_with_status_then_recovers(fake_jira):
    fake_jira.fail_next(503, "maintenance")
    status, body, _ = call(fake_jira, "GET", f"{API}/project/SCRUM/statuses")
    assert status == 503 and body["errorMessages"] == ["maintenance"]
    assert call(fake_jira, "GET", f"{API}/project/SCRUM/statuses")[0] == 200
    assert len(fake_jira.calls()) == 2


def test_fail_next_can_echo_the_authorization_header(fake_jira):
    fake_jira.fail_next(400, echo_auth=True)
    _, body, _ = call(fake_jira, "GET", f"{API}/project/SCRUM/statuses")
    creds = base64.b64encode(f"{fake_jira.email}:{fake_jira.token}".encode()).decode()
    assert creds in body["errorMessages"][0]


def test_redirect_next_answers_302_with_location_and_logs_one_request(fake_jira):
    fake_jira.redirect_next("/rest/api/3/elsewhere")
    status, _, headers = call(fake_jira, "GET", f"{API}/project/SCRUM/statuses")
    assert status == 302 and headers["Location"] == "/rest/api/3/elsewhere"
    assert len(fake_jira.calls()) == 1


def test_delay_next_outlasts_client_timeout_then_recovers(fake_jira):
    fake_jira.delay_next(1.0)
    with pytest.raises((TimeoutError, urllib.error.URLError, socket.timeout)):
        call(fake_jira, "GET", f"{API}/project/SCRUM/statuses", timeout=0.2)
    assert call(fake_jira, "GET", f"{API}/project/SCRUM/statuses")[0] == 200


def test_faults_apply_in_order_one_per_request(fake_jira):
    fake_jira.fail_next(429)
    fake_jira.fail_next(500)
    codes = [call(fake_jira, "GET", f"{API}/project/SCRUM/statuses")[0] for _ in range(3)]
    assert codes == [429, 500, 200]


def test_malformed_edit_payload_is_400_not_a_dropped_connection(fake_jira):
    key = fake_jira.add_issue()
    status, _, _ = call(fake_jira, "PUT", f"{API}/issue/{key}", {"update": {"labels": [1]}})
    assert status == 400
