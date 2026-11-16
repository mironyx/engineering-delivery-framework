"""Stateful fake Jira Cloud server for the tracker's Jira backend tests (ADR-0041, issue #130).

Serves the Jira Cloud REST v3 endpoints the backend uses, over TLS, from a local
`ThreadingHTTPServer`. It mirrors Atlassian's OpenAPI spec (shapes and status codes), not real
Jira behaviour: it cannot prove JQL text-search semantics or search-index lag — the `SCRUM`
smoke run does that.

Endpoints (anything else answers 501 so a typo fails the test instead of looking like a 404):
    POST /rest/api/3/issue                       201 {id, key, self}
    GET  /rest/api/3/issue/{key}                 200 | 404
    PUT  /rest/api/3/issue/{key}                 204 | 400 | 404
    GET  /rest/api/3/issue/{key}/transitions     200 | 404
    POST /rest/api/3/issue/{key}/transitions     204 | 400 | 404
    POST /rest/api/3/issue/{key}/comment         201 | 400 | 404
    GET  /rest/api/3/project/{key}/statuses      200 | 404
    POST /rest/api/3/search/jql                  200 | 400

JQL is limited to the grammar the backend emits; anything else is a 400 with `errorMessages`:
    project = "K"  issuetype = "T"  summary ~ "<phrase>"  status = "<name>"
    statusCategory = Done | statusCategory != Done  labels = "<v>"  parent = KEY
    joined by AND, optionally followed by ORDER BY Rank ASC; string escapes are \\" and \\\\.
A query must contain a `project =` clause (real Jira rejects unbounded queries).
"""

from __future__ import annotations

import base64
import copy
import json
import re
import shutil
import ssl
import subprocess
import sys
import threading
import time
import traceback
from collections import deque
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qsl, urlsplit

TOKEN = "tok-SECRET"
EMAIL = "dev@example.com"
SPACE = "SCRUM"

_CATEGORY_NAMES = {"new": "To Do", "indeterminate": "In Progress", "done": "Done"}
_DEFAULT_STATUSES = {"To Do": "new", "In Progress": "indeterminate", "Blocked": "indeterminate", "Done": "done"}
_ISSUE_TYPES = ("Task", "Epic")
_MAX_RESULTS_CAP = 5000
_DEFAULT_PAGE = 50
_SETTABLE_FIELDS = ("summary", "description", "labels", "parent")


class FakeJiraSetupError(RuntimeError):
    """The fixture cannot start (e.g. openssl missing). Never a reason to skip."""


def generate_certificate(directory: Path) -> tuple[Path, Path]:
    """Create a 2-day self-signed certificate for localhost / 127.0.0.1 with openssl."""
    if shutil.which("openssl") is None:
        raise FakeJiraSetupError(
            "fake_jira needs the `openssl` executable on PATH to generate its TLS certificate; "
            "install openssl — the Jira backend tests cannot run without it"
        )
    cert, key = directory / "fake_jira_cert.pem", directory / "fake_jira_key.pem"
    result = subprocess.run(
        [
            "openssl", "req", "-x509", "-newkey", "rsa:2048", "-nodes",
            "-subj", "/CN=localhost",
            "-addext", "subjectAltName=DNS:localhost,IP:127.0.0.1",
            "-days", "2", "-keyout", str(key), "-out", str(cert),
        ],
        capture_output=True, text=True, check=False,
    )
    if result.returncode != 0:
        raise FakeJiraSetupError(f"openssl could not generate the fake_jira certificate: {result.stderr.strip()}")
    return cert, key


class JqlError(ValueError):
    """The query is outside the grammar the backend is allowed to emit."""


_TOKEN_RE = re.compile(r'\s*(?:(?P<str>"(?:[^"\\]|\\.)*")|(?P<op>!=|=|~)|(?P<word>[A-Za-z_][A-Za-z0-9_-]*))')
_KEY_RE = re.compile(r"^[A-Za-z][A-Za-z0-9_]*-\d+$")


def _tokenise(jql: str) -> list[tuple[str, str]]:
    tokens, pos = [], 0
    while jql[pos:].strip():
        match = _TOKEN_RE.match(jql, pos)
        if not match:
            raise JqlError(f"unexpected character at position {pos}")
        kind = match.lastgroup or ""
        tokens.append((kind, match.group(kind)))
        pos = match.end()
    return tokens


def _unquote(raw: str) -> str:
    out, i, inner = [], 0, raw[1:-1]
    while i < len(inner):
        if inner[i] == "\\":
            if inner[i + 1] not in '"\\':
                raise JqlError(f"unsupported escape \\{inner[i + 1]}")
            i += 1
        out.append(inner[i])
        i += 1
    return "".join(out)


def parse_jql(jql: str) -> list[tuple[str, str, str]]:
    """Return [(field, op, value)] for the supported grammar; ORDER BY Rank ASC is accepted and dropped."""
    tokens = _tokenise(jql)
    clauses: list[tuple[str, str, str]] = []
    i = 0
    while True:
        if i + 3 > len(tokens) or tokens[i][0] != "word" or tokens[i + 1][0] != "op":
            raise JqlError("expected `<field> <operator> <value>`")
        field, (_, op), (vkind, vraw) = tokens[i][1], tokens[i + 1], tokens[i + 2]
        value = _unquote(vraw) if vkind == "str" else vraw
        _check_clause(field, op, vkind, value)
        clauses.append((field, op, value))
        i += 3
        if i == len(tokens):
            break
        if tokens[i] == ("word", "AND"):
            i += 1
            continue
        if [t[1] for t in tokens[i:]] == ["ORDER", "BY", "Rank", "ASC"]:
            break
        raise JqlError(f"unexpected `{tokens[i][1]}`")
    if not any(c[0] == "project" for c in clauses):
        raise JqlError("unbounded query: add a `project =` clause")
    return clauses


def _check_clause(field: str, op: str, vkind: str, value: str) -> None:
    allowed = {
        "project": ({"="}, "str"), "issuetype": ({"="}, "str"), "summary": ({"~"}, "str"),
        "status": ({"="}, "str"), "labels": ({"="}, "str"),
        "statusCategory": ({"=", "!="}, "word"), "parent": ({"="}, "word"),
    }
    if field not in allowed:
        raise JqlError(f"field `{field}` is not supported")
    ops, kind = allowed[field]
    if op not in ops:
        raise JqlError(f"operator `{op}` is not supported for `{field}`")
    if vkind != kind:
        raise JqlError(f"`{field}` value must be a {'quoted string' if kind == 'str' else 'bare word'}")
    if field == "statusCategory" and value != "Done":
        raise JqlError("statusCategory supports only Done")
    if field == "parent" and not _KEY_RE.match(value):
        raise JqlError(f"`{value}` is not an issue key")


class FakeJira:
    """The server plus its state. Created and torn down by the `fake_jira` fixture."""

    def __init__(self, cert: Path, key: Path, *, email: str = EMAIL, token: str = TOKEN, space: str = SPACE):
        self.email, self.token, self.space = email, token, space
        self._lock = threading.RLock()
        self._issues: dict[str, dict] = {}
        self._next_n = 1
        self._next_rank = 1
        self._comment_id = 10000
        self._faults: deque[dict] = deque()
        self._calls: list[dict] = []
        self.errors: list[str] = []  # tracebacks from unexpected handler failures
        self.set_workflow()
        ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        ctx.load_cert_chain(str(cert), str(key))
        self._server = _TlsServer(("127.0.0.1", 0), _Handler, ctx)
        self._server.fake = self
        self._thread = threading.Thread(target=self._server.serve_forever, kwargs={"poll_interval": 0.02}, daemon=True)

    # -- lifecycle ---------------------------------------------------------------------------
    @property
    def host(self) -> str:
        return f"https://localhost:{self._server.server_address[1]}"

    @property
    def env(self) -> dict[str, str]:
        return {"JIRA_HOST": self.host, "JIRA_EMAIL": self.email, "JIRA_API_TOKEN": self.token, "JIRA_SPACE": self.space}

    def start(self) -> None:
        self._thread.start()

    def stop(self) -> None:
        self._server.shutdown()
        self._server.server_close()
        self._thread.join(timeout=5)

    # -- test API ----------------------------------------------------------------------------
    def set_workflow(self, *, with_blocked: bool = True, transitions: dict[str, list[str]] | None = None) -> None:
        """Statuses (name → category key) and allowed transitions (from → [to]); default fully connected."""
        statuses = {n: c for n, c in _DEFAULT_STATUSES.items() if with_blocked or n != "Blocked"}
        with self._lock:
            self.statuses = statuses
            self.transitions = transitions or {s: [t for t in statuses if t != s] for s in statuses}

    def add_issue(self, summary: str = "Seeded issue", *, type: str = "Task", status: str = "To Do",  # noqa: A002
                  labels: list[str] | tuple[str, ...] = (), parent: str | None = None,
                  description: dict | None = None) -> str:
        with self._lock:
            key = f"{self.space}-{self._next_n}"
            self._next_n += 1
            self._issues[key] = {
                "key": key, "id": str(10000 + self._next_n), "summary": summary, "type": type, "status": status,
                "labels": list(labels), "parent": parent, "description": description, "comments": [],
                "rank": self._next_rank,
            }
            self._next_rank += 1
            return key

    def issue(self, key: str) -> dict:
        """The live record (summary, type, status, labels, parent, description, comments, rank)."""
        with self._lock:
            return self._issues[key]

    def set_rank(self, key: str, rank: float) -> None:
        with self._lock:
            self._issues[key]["rank"] = rank

    def calls(self) -> list[dict]:
        """Every request received: method, path, query, body, has_auth, authorization."""
        with self._lock:
            return copy.deepcopy(self._calls)

    def fail_next(self, status: int, body: str | None = None, *, echo_auth: bool = False) -> None:
        """Answer the next request with `status` and an errorMessages body; echo_auth leaks the Authorization header into it."""
        self._faults.append({"kind": "fail", "status": status, "body": body, "echo_auth": echo_auth})

    def redirect_next(self, location: str, status: int = 302) -> None:
        self._faults.append({"kind": "redirect", "status": status, "location": location})

    def delay_next(self, seconds: float) -> None:
        """Sleep before handling the next request, then answer it normally."""
        self._faults.append({"kind": "delay", "seconds": seconds})

    # -- request handling (called from handler threads) --------------------------------------
    def _next_fault(self) -> dict | None:
        try:
            return self._faults.popleft()
        except IndexError:
            return None

    def _status_obj(self, name: str) -> dict:
        cat = self.statuses.get(name, "new")
        return {"name": name, "id": str(1000 + list(self.statuses).index(name)) if name in self.statuses else "0",
                "statusCategory": {"key": cat, "name": _CATEGORY_NAMES[cat]}}

    def _fields(self, issue: dict, wanted: set[str] | None) -> dict:
        full = {
            "summary": issue["summary"], "description": copy.deepcopy(issue["description"]),
            "status": self._status_obj(issue["status"]), "labels": list(issue["labels"]),
            "issuetype": {"name": issue["type"]},
        }
        if issue["parent"]:
            full["parent"] = {"key": issue["parent"]}
        if wanted is None or "*all" in wanted:
            return full
        return {k: v for k, v in full.items() if k in wanted}

    def _issue_json(self, issue: dict, wanted: set[str] | None) -> dict:
        return {"id": issue["id"], "key": issue["key"], "self": f"{self.host}/rest/api/3/issue/{issue['id']}",
                "fields": self._fields(issue, wanted)}

    def dispatch(self, method: str, path: str, query: dict[str, str], body: dict | None) -> tuple[int, dict | None]:
        with self._lock:
            return self._route(method, path, query, body)

    def _route(self, method, path, query, body):  # noqa: C901 — flat route table, one branch per endpoint
        base = "/rest/api/3/"
        if not path.startswith(base):
            return _unsupported(method, path)
        parts = path[len(base):].split("/")
        if parts == ["issue"] and method == "POST":
            return self._create(body)
        if parts == ["search", "jql"] and method == "POST":
            return self._search(body)
        if len(parts) == 3 and parts[0] == "project" and parts[2] == "statuses" and method == "GET":
            return self._project_statuses(parts[1])
        if parts[0] == "issue" and len(parts) in (2, 3):
            issue = self._issues.get(parts[1])
            sub = parts[2] if len(parts) == 3 else None
            if (sub, method) in ((None, "GET"), (None, "PUT"), ("transitions", "GET"), ("transitions", "POST"),
                                 ("comment", "POST")):
                if issue is None:
                    return 404, _errors("Issue does not exist or you do not have permission to see it.")
                return {
                    (None, "GET"): lambda: self._view(issue, query),
                    (None, "PUT"): lambda: self._edit(issue, body),
                    ("transitions", "GET"): lambda: self._list_transitions(issue),
                    ("transitions", "POST"): lambda: self._transition(issue, body),
                    ("comment", "POST"): lambda: self._comment(issue, body),
                }[(sub, method)]()
        return _unsupported(method, path)

    def _create(self, body):
        fields = (body or {}).get("fields")
        if not isinstance(fields, dict):
            return 400, _errors("Request body must contain `fields`.")
        errors = {}
        if (fields.get("project") or {}).get("key") != self.space:
            errors["project"] = "valid project is required"
        if not str(fields.get("summary") or "").strip():
            errors["summary"] = "You must specify a summary of the issue."
        issue_type = (fields.get("issuetype") or {}).get("name")
        if issue_type not in _ISSUE_TYPES:
            errors["issuetype"] = "valid issue type is required"
        parent = (fields.get("parent") or {}).get("key")
        if parent and parent not in self._issues:
            errors["parent"] = "Given parent issue does not exist"
        if errors:
            return 400, {"errorMessages": [], "errors": errors}
        key = self.add_issue(fields["summary"], type=issue_type, labels=fields.get("labels") or [], parent=parent,
                             description=fields.get("description"))
        issue = self._issues[key]
        return 201, {"id": issue["id"], "key": key, "self": f"{self.host}/rest/api/3/issue/{issue['id']}"}

    def _view(self, issue, query):
        wanted = set(query["fields"].split(",")) if query.get("fields") else None
        return 200, self._issue_json(issue, wanted)

    def _edit(self, issue, body):
        body = body or {}
        fields, update = body.get("fields") or {}, body.get("update") or {}
        bad = [f for f in fields if f not in _SETTABLE_FIELDS] + [f for f in update if f != "labels"]
        if bad:
            return 400, {"errorMessages": [], "errors": {f: f"Field '{f}' cannot be set." for f in bad}}
        labels = list(fields.get("labels", issue["labels"]))
        ops = update.get("labels") or []
        if not all(isinstance(op, dict) for op in ops):
            return 400, _errors("update.labels entries must be objects with add or remove.")
        for op in ops:
            if "add" in op and op["add"] not in labels:
                labels.append(op["add"])
            if "remove" in op and op["remove"] in labels:
                labels.remove(op["remove"])
        issue["labels"] = labels
        if "summary" in fields:
            issue["summary"] = fields["summary"]
        if "description" in fields:
            issue["description"] = fields["description"]
        if "parent" in fields:
            issue["parent"] = (fields["parent"] or {}).get("key")
        return 204, None

    def _transition_id(self, name: str) -> str:
        return str(10 * (list(self.statuses).index(name) + 1) + 1)

    def _list_transitions(self, issue):
        out = [{"id": self._transition_id(to), "name": to, "to": self._status_obj(to)}
               for to in self.transitions.get(issue["status"], [])]
        return 200, {"transitions": out}

    def _transition(self, issue, body):
        tid = str(((body or {}).get("transition") or {}).get("id", ""))
        for to in self.transitions.get(issue["status"], []):
            if self._transition_id(to) == tid:
                issue["status"] = to
                return 204, None
        return 400, _errors(f"Transition id '{tid}' is not valid for this issue.")

    def _comment(self, issue, body):
        adf = (body or {}).get("body")
        if not isinstance(adf, dict) or adf.get("type") != "doc":
            return 400, _errors("Comment body must be an Atlassian Document Format document.")
        self._comment_id += 1
        issue["comments"].append({"id": str(self._comment_id), "body": adf})
        return 201, {"id": str(self._comment_id), "body": adf}

    def _project_statuses(self, key):
        if key != self.space:
            return 404, _errors("No project could be found with key '" + key + "'.")
        listing = [{"id": str(i), "name": s, "statusCategory": self._status_obj(s)["statusCategory"]}
                   for i, s in enumerate(self.statuses)]
        return 200, [{"id": str(i), "name": t, "subtask": False, "statuses": listing} for i, t in enumerate(_ISSUE_TYPES)]

    def _search(self, body):
        body = body or {}
        try:
            clauses = parse_jql(str(body.get("jql", "")))
        except JqlError as exc:
            return 400, _errors(f"Error in the JQL Query: {exc}")
        size = body.get("maxResults", _DEFAULT_PAGE)
        if not isinstance(size, int) or size < 1:
            return 400, _errors("maxResults must be a positive integer")
        size = min(size, _MAX_RESULTS_CAP)
        token = body.get("nextPageToken")
        offset = 0
        if token is not None:
            if not (isinstance(token, str) and re.fullmatch(r"page-\d+", token)):
                return 400, _errors("Invalid nextPageToken")
            offset = int(token[5:])
        wanted = set(body.get("fields") or ["id"])
        hits = sorted((i for i in self._issues.values() if self._matches(i, clauses)), key=lambda i: i["rank"])
        page = hits[offset:offset + size]
        out: dict = {"issues": [self._issue_json(i, wanted - {"id"}) for i in page], "isLast": offset + size >= len(hits)}
        if not out["isLast"]:
            out["nextPageToken"] = f"page-{offset + size}"
        return 200, out

    def _matches(self, issue, clauses) -> bool:
        checks = {
            ("project", "="): lambda v: v == self.space,
            ("issuetype", "="): lambda v: issue["type"] == v,
            ("summary", "~"): lambda v: v.strip('"').lower() in issue["summary"].lower(),
            ("status", "="): lambda v: issue["status"] == v,
            ("statusCategory", "="): lambda v: self.statuses.get(issue["status"]) == "done",
            ("statusCategory", "!="): lambda v: self.statuses.get(issue["status"]) != "done",
            ("labels", "="): lambda v: v in issue["labels"],
            ("parent", "="): lambda v: (issue["parent"] or "").lower() == v.lower(),
        }
        return all(checks[(f, op)](v) for f, op, v in clauses)


def _errors(message: str) -> dict:
    return {"errorMessages": [message], "errors": {}}


def _unsupported(method: str, path: str) -> tuple[int, dict]:
    return 501, _errors(f"fake_jira does not implement {method} {path}")


class _TlsServer(ThreadingHTTPServer):
    daemon_threads = True
    fake: FakeJira

    def __init__(self, addr, handler, context: ssl.SSLContext):
        self._context = context
        super().__init__(addr, handler)

    def get_request(self):
        sock, addr = super().get_request()
        # Handshake in the handler thread, so one bad client cannot stall accept().
        return self._context.wrap_socket(sock, server_side=True, do_handshake_on_connect=False), addr

    def handle_error(self, request, client_address):
        # Clients that time out, hang up or reject the cert are expected; anything else is a fake bug
        # and is recorded so the fixture fails the test instead of leaving a dropped connection.
        exc = sys.exc_info()[1]
        if not isinstance(exc, (ssl.SSLError, ConnectionError, TimeoutError)):
            self.fake.errors.append("".join(traceback.format_exception(exc)))


class _Handler(BaseHTTPRequestHandler):
    server: _TlsServer

    def setup(self):
        super().setup()
        self.connection.do_handshake()

    def log_message(self, format, *args):  # noqa: A002 — keep pytest output clean
        pass

    def _reply(self, status: int, payload=None, headers: dict | None = None):
        data = b"" if payload is None else json.dumps(payload).encode()
        self.send_response(status)
        for name, value in (headers or {}).items():
            self.send_header(name, value)
        if data:
            self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _handle(self):
        fake = self.server.fake
        split = urlsplit(self.path)
        query = dict(parse_qsl(split.query))
        raw = self.rfile.read(int(self.headers.get("Content-Length") or 0))
        auth = self.headers.get("Authorization")
        try:
            body = json.loads(raw) if raw else None
        except ValueError:
            body = None
            bad_json = True
        else:
            bad_json = False
        with fake._lock:
            fake._calls.append({"method": self.command, "path": split.path, "query": query, "body": body,
                                "has_auth": auth is not None, "authorization": auth})
        fault = fake._next_fault()
        while fault and fault["kind"] == "delay":
            time.sleep(fault["seconds"])
            fault = fake._next_fault()
        if fault and fault["kind"] == "redirect":
            return self._reply(fault["status"], None, {"Location": fault["location"]})
        if fault:
            message = fault["body"] or "injected failure"
            if fault["echo_auth"]:
                message += f" (request carried Authorization: {auth})"
            return self._reply(fault["status"], _errors(message))
        expected = "Basic " + base64.b64encode(f"{fake.email}:{fake.token}".encode()).decode()
        if auth != expected:
            return self._reply(401, _errors("You are not authenticated."))
        if bad_json:
            return self._reply(400, _errors("Request body is not valid JSON."))
        status, payload = fake.dispatch(self.command, split.path, query, body)
        self._reply(status, payload)

    do_GET = do_POST = do_PUT = do_DELETE = _handle
