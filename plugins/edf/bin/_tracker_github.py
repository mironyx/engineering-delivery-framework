"""GitHub backend for tracker.py (ADR-0041).

create and status are ports of gh-create-issue.sh and gh-project-status.sh with byte-identical
output for the golden matrix (I6, tests/fixtures/tracker_golden/). Every gh call takes an argv
list and explicit stdin — never a shell string (I8).

Design reference: plugins/edf/docs/design/v3/lld-v3-e3-1-tracker-script.md §1.2–§1.4
"""

from __future__ import annotations

import argparse
import json
import pathlib
import re
import subprocess
import sys
from collections.abc import Callable
from dataclasses import dataclass, replace

from _tracker_contract import Issue, TrackerError, issue_json, normalise_status

_BOARD_VARS = ("REPO", "PROJECT_NUMBER", "PROJECT_ID", "FIELD_ID",
               "STATUS_TODO", "STATUS_BLOCKED", "STATUS_IN_PROGRESS", "STATUS_DONE")
_STATUS_VARS = {"todo": "STATUS_TODO", "blocked": "STATUS_BLOCKED",
                "in progress": "STATUS_IN_PROGRESS", "done": "STATUS_DONE"}
_NOT_FOUND = "Could not resolve to an Issue"
_TYPES = ("task", "epic")

_BASE_FIELDS = "number title body state labels(first:50){nodes{name}}"
# Board fields need the read:project token scope; only status, and view/list when project.env
# exists, request them.
_BOARD_FIELDS = (
    "projectItems(first:10){nodes{id project{id} fieldValues(first:20){nodes{"
    "... on ProjectV2ItemFieldSingleSelectValue{optionId field{... on ProjectV2SingleSelectField{id}}}}}}}"
)
ISSUE_FIELDS = _BASE_FIELDS + " " + _BOARD_FIELDS
_QUERY = ("query($owner:String!,$name:String!,$number:Int!){{repository(owner:$owner,name:$name){{"
          "issue(number:$number){{{fields}}}}}}}")
ISSUE_QUERY = _QUERY.format(fields=ISSUE_FIELDS)
_PLAIN_ISSUE_QUERY = _QUERY.format(fields=_BASE_FIELDS)
_ISSUES_QUERY = ("query($owner:String!,$name:String!,$first:Int!,$states:[IssueState!],$labels:[String!]){{"
                 "repository(owner:$owner,name:$name){{issues(first:$first,states:$states,labels:$labels,"
                 "orderBy:{{field:CREATED_AT,direction:DESC}}){{nodes{{{fields}}}}}}}}}")
ISSUES_QUERY = _ISSUES_QUERY.format(fields=ISSUE_FIELDS)
_PLAIN_ISSUES_QUERY = _ISSUES_QUERY.format(fields=_BASE_FIELDS)


class _ParityExit(Exception):
    """The parity text is already printed; return this exit code."""

    # Justification: carries the exit code the caller must return (gh's own code, or 1).
    def __init__(self, code: int):
        super().__init__(code)
        self.code = code


# ---------------------------------------------------------------- gh helpers


def _gh(args: list[str], stdin: str | None = None) -> subprocess.CompletedProcess[str]:
    """Run gh with an argv list (I8). stdin is always explicit so gh can never wait on a pipe."""
    return subprocess.run(["gh", *args], input=stdin if stdin is not None else "", capture_output=True, text=True)


def _parse_ref(ref: str) -> int:
    digits = ref[1:] if ref.startswith("#") else ref
    if not digits.isdigit():
        raise TrackerError(f"invalid GitHub reference '{ref}'")
    return int(digits)


# Justification: status needs the raw gh result (its not-found stderr is parity output), while
# _fetch_issue maps it to None/TrackerError — one query builder serves both.
def _issue_query(number: int, repo: str | None, *, board: bool = True) -> subprocess.CompletedProcess[str]:
    if repo is None:
        owner = ["-F", "owner={owner}", "-F", "name={repo}"]
    else:
        name_owner, _, name = repo.partition("/")
        owner = ["-f", f"owner={name_owner}", "-f", f"name={name}"]
    return _gh(["api", "graphql", *owner, "-F", f"number={number}", "-f", f"query={ISSUE_QUERY if board else _PLAIN_ISSUE_QUERY}"])


# Justification: parses the GraphQL envelope once for both call paths (create --parent, status).
def _issue_node(result: subprocess.CompletedProcess[str]) -> dict | None:
    """The issue node, or None when the reply says the issue does not exist (issue: null)."""
    try:
        return json.loads(result.stdout)["data"]["repository"]["issue"]
    except (json.JSONDecodeError, KeyError, TypeError) as e:
        raise TrackerError("unexpected gh api graphql response") from e


def _fetch_issue(number: int, repo: str | None = None, *, board: bool = True) -> dict | None:
    """The issue node, or None when it does not exist. board=False skips projectItems, which
    needs the read:project token scope — create uses it, since it never reads board fields."""
    result = _issue_query(number, repo, board=board)
    if result.returncode != 0:
        if _NOT_FOUND in result.stderr:
            return None
        raise TrackerError(f"gh api graphql failed: {result.stderr.strip()}")
    return _issue_node(result)


def _write_body(number: int, body: str) -> subprocess.CompletedProcess[str]:
    return _gh(["issue", "edit", str(number), "--body-file", "-"], stdin=body)


# ---------------------------------------------------------------- board helpers


@dataclass(frozen=True)
class Board:
    repo: str
    number: str
    project_id: str
    field_id: str
    options: dict[str, str]

    @property
    def owner(self) -> str:
        return self.repo.split("/", 1)[0]


# Justification: KEY=VALUE parsing with gh-project-status.sh's xargs quirks (whitespace incl. \r,
# one pair of surrounding quotes) is separate from the strict/lenient error policy in load_board.
def _read_project_env(path: pathlib.Path) -> dict[str, str]:
    values: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        key, _, value = line.partition("=")
        key, value = key.strip(), value.strip()
        if not key or key.startswith("#"):
            continue
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "'\"":
            value = value[1:-1]
        values[key] = value
    return values


def load_board(repo_root: pathlib.Path | None, *, strict: bool) -> Board | None:
    """Read .github/project.env. strict: print today's messages and raise _ParityExit(1)."""

    def fail(*lines: str) -> None:
        if strict:
            for line in lines:
                print(line, file=sys.stderr)
            raise _ParityExit(1)

    if repo_root is None:
        fail("Error: not inside a git repository — run from your project directory")
        return None
    path = f"{repo_root}/.github/project.env"
    if not pathlib.Path(path).is_file():
        fail(f"Error: config file not found: {path}",
             "Create it with REPO, PROJECT_NUMBER, PROJECT_ID, FIELD_ID, and STATUS_* values.",
             "See this script's header for the format.")
        return None
    values = _read_project_env(pathlib.Path(path))
    for var in _BOARD_VARS:
        if not values.get(var):
            fail(f"Error: {var} not set in {path}")
            return None
    return Board(values["REPO"], values["PROJECT_NUMBER"], values["PROJECT_ID"], values["FIELD_ID"],
                 {status: values[var] for status, var in _STATUS_VARS.items()})


def _board_item(board: Board, node: dict) -> tuple[str, str | None]:
    """(item id, option id) of the issue's item on this board; ("", None) when not on it."""
    for item in node["projectItems"]["nodes"]:
        if item["project"]["id"] == board.project_id:
            option = next((v.get("optionId") for v in item.get("fieldValues", {}).get("nodes", [])
                           if v.get("field", {}).get("id") == board.field_id), None)
            return item["id"], option
    return "", None


def _board_set(board: Board, item_id: str, status: str) -> subprocess.CompletedProcess[str]:
    return _gh(["project", "item-edit", "--project-id", board.project_id, "--id", item_id,
                "--field-id", board.field_id, "--single-select-option-id", board.options[status]])


def _board_add(board: Board, number: int) -> str:
    """Add the issue to the board; returns the item id, "" when the reply carries none.

    Raises TrackerError, carrying gh's stderr or reply, when gh fails or the reply is not JSON."""
    result = _gh(["project", "item-add", board.number, "--owner", board.owner,
                  "--url", f"https://github.com/{board.repo}/issues/{number}", "--format", "json"])
    if result.returncode != 0:
        raise TrackerError(result.stderr.strip() or "gh project item-add failed")
    try:
        return str(json.loads(result.stdout).get("id") or "")
    except (json.JSONDecodeError, AttributeError) as e:
        raise TrackerError(f"unexpected gh project item-add reply: {result.stdout.strip()}") from e


# ---------------------------------------------------------------- create


# Justification: --type epic must add the label exactly once and otherwise leave --labels
# byte-for-byte as given (dry-run and gh argv parity).
def _labels(labels: str | None, issue_type: str | None) -> str:
    if issue_type is not None and issue_type not in _TYPES:
        raise TrackerError(f"unknown type '{issue_type}'. Use: task | epic")
    labels = labels or ""
    if issue_type != "epic":
        return labels
    names = [name.strip() for name in labels.split(",") if name.strip()]
    if "epic" not in names:
        names.append("epic")
    return ",".join(names)


def _with_parent_section(body: str, parent: int) -> str:
    if "## Parent epic" in body:
        return body
    return f"## Parent epic\n#{parent}\n\n{body}"


_TASKS_HEADING = re.compile(r"^#{2,3} Tasks\s*$")
_PLACEHOLDER = "- [ ] (to be filled by edf:architect)"


# Justification: pure text transform of the epic body — the checklist placement rules
# (LLD Open question 3) are tested without gh.
def _add_checklist_line(body: str, child: int, title: str) -> str | None:
    """Epic body with '- [ ] #child — title' placed in its Tasks section; None if already there."""
    if re.search(rf"- \[[ xX]\] #{child}\b", body):
        return None
    line = f"- [ ] #{child} — {title}"
    lines = body.split("\n")
    start = next((i for i, text in enumerate(lines) if _TASKS_HEADING.match(text)), None)
    if start is None:
        return f"{body}\n### Tasks\n{line}\n"
    end = next((i for i in range(start + 1, len(lines)) if lines[i].startswith("#")), len(lines))
    section = range(start + 1, end)
    t_line = re.compile(rf"^- \[ \] T\d+ — {re.escape(title)}\s*$")
    for matches in (t_line.match, lambda text: text.strip() == _PLACEHOLDER):
        hit = next((i for i in section if matches(lines[i])), None)
        if hit is not None:
            lines[hit] = line
            return "\n".join(lines)
    last_item = max((i for i in section if lines[i].startswith("- [")), default=start)
    lines.insert(last_item + 1, line)
    return "\n".join(lines)


def _link_child(epic_node: dict, child: int, title: str) -> None:
    new_body = _add_checklist_line(epic_node["body"], child, title)
    if new_body is None:
        return
    result = _write_body(epic_node["number"], new_body)
    if result.returncode != 0:
        raise TrackerError(f"failed to update epic #{epic_node['number']}: {result.stderr.strip()}")


# Justification: an issue found by dedup may predate --parent; its body gets the same
# '## Parent epic' section a new issue is created with (AC: "new (or existing)").
def _ensure_parent_section(number: int, parent: int, title: str) -> None:
    node = _fetch_issue(number, board=False)
    if node is None:
        raise TrackerError(f"issue #{number} not found")
    if node["title"] != title:  # dedup is a fuzzy in:title match; never link a different issue
        raise TrackerError(f"issue #{number} title differs")
    body = _with_parent_section(node["body"], parent)
    if body == node["body"]:
        return
    result = _write_body(number, body)
    if result.returncode != 0:
        raise TrackerError(f"failed to update issue #{number}: {result.stderr.strip()}")


# Justification: shared by the created and dedup-hit paths of create; one place turns any link
# failure into the parity-style warning so the create itself still succeeds.
def _link_parent(parent_node: dict, number: int, title: str, *, existing: bool) -> None:
    parent = parent_node["number"]
    try:
        if existing:
            _ensure_parent_section(number, parent, title)
        _link_child(parent_node, number, title)
    except (TrackerError, KeyError, ValueError) as e:
        print(f"Warning: failed to link #{number} to epic #{parent}: {e}", file=sys.stderr)


# Justification: the dedup search is its own gh round trip with bash-parity quirks (failure
# swallowed, first line only); create would otherwise exceed the complexity gate.
def _find_existing(title: str) -> str:
    result = _gh(["issue", "list", "--state", "open", "--limit", "100", "--search", f'in:title "{title}"',
                  "--json", "number", "--jq", ".[0].number"])
    out = result.stdout.rstrip("\n")
    return out.split("\n", 1)[0] if out else ""


# Justification: the parity-bound dry-run block (plus the new parent line) kept out of create's
# control flow; complexity gate.
def _print_dry_run(args: argparse.Namespace, labels: str, parent: int | None, board_status: str) -> None:
    print("dry-run: would create issue")
    print(f"  title:  {args.title}")
    print(f"  labels: {labels or '<none>'}")
    if parent is not None:
        print(f"  parent: #{parent}")
    print(f"  board:  {'true' if args.add_to_board else 'false'} (status: {board_status})")
    print("  body:")
    for line in args.body.split("\n"):
        print(f"    {line}")


# Justification: every board failure (no config, bad --board-status, gh error) collapses into
# one warning, as the bash `gh-project-status.sh add ... || warn` did; complexity gate for create.
def _add_new_issue_to_board(ctx: object, number: int, board_status: str) -> None:
    try:
        board = load_board(getattr(ctx, "repo_root", None), strict=False)
        if board is None:
            raise TrackerError("no board")
        item_id = _board_add(board, number)
        if not item_id or _board_set(board, item_id, normalise_status(board_status)).returncode != 0:
            raise TrackerError("board update failed")
    except TrackerError:
        # Deliberately detail-free: golden create-add-to-board-fails pins stderr to this one line,
        # because the bash script ran the board step with >/dev/null 2>&1 (I6).
        print(f"Warning: failed to add #{number} to board", file=sys.stderr)


def create(args: argparse.Namespace, ctx: object) -> int:
    labels = _labels(args.labels, args.type)
    board_status = args.board_status if args.board_status is not None else "todo"
    parent_node = None
    if args.parent is not None:
        parent = _parse_ref(args.parent)
        parent_node = _fetch_issue(parent, board=False)
        if parent_node is None:
            raise TrackerError(f"parent #{parent} not found")

    existing = _find_existing(args.title)
    if existing:
        if parent_node is not None and not args.dry_run and existing.isdigit():
            _link_parent(parent_node, int(existing), args.title, existing=True)
        print(f"exists:{existing}")
        return 0

    if args.dry_run:
        _print_dry_run(args, labels, parent_node["number"] if parent_node else None, board_status)
        return 0

    body = _with_parent_section(args.body, parent_node["number"]) if parent_node else args.body
    create_args = ["issue", "create", "--title", args.title, "--body-file", "-"]
    if labels:
        create_args += ["--label", labels]
    result = _gh(create_args, stdin=body)
    output = (result.stdout + result.stderr).rstrip("\n")
    if result.returncode != 0:
        print(f"Error: gh issue create failed: {output}", file=sys.stderr)
        return 1
    match = re.search(r"(\d+)$", output)
    if match is None:
        print(f"Error: could not extract issue number from: {output}", file=sys.stderr)
        return 1
    number = int(match.group(1))

    if parent_node is not None:
        _link_parent(parent_node, number, args.title, existing=False)
    if args.add_to_board:
        _add_new_issue_to_board(ctx, number, board_status)
    print(f"created:{number}")
    return 0


# ---------------------------------------------------------------- status


# Justification: the not-found and item-edit failure paths pass gh's own output through
# (parity), which TrackerError's single "Error:" line cannot express.
def _passthrough(result: subprocess.CompletedProcess[str]) -> int:
    sys.stdout.write(result.stdout)
    sys.stderr.write(result.stderr)
    return result.returncode or 1


def status(args: argparse.Namespace, ctx: object) -> int:
    try:
        board = load_board(getattr(ctx, "repo_root", None), strict=True)
    except _ParityExit as e:
        return e.code
    assert board is not None  # strict mode never returns None
    new_status = normalise_status(args.status_raw)
    number = _parse_ref(args.ref)

    if args.add_to_board:
        try:
            item_id = _board_add(board, number)
        except TrackerError as e:
            print(str(e), file=sys.stderr)
            return 1
        if not item_id:
            print(f"Error: failed to add issue #{number} to the project board")
            return 1
        result = _board_set(board, item_id, new_status)
        if result.returncode != 0:
            return _passthrough(result)
        print(f"Issue #{number} → added → {args.status_raw}")
        return 0

    query = _issue_query(number, board.repo)
    if query.returncode != 0:
        return _passthrough(query)
    node = _issue_node(query)
    item_id, _ = _board_item(board, node) if node is not None else ("", None)
    if not item_id:
        print(f"Error: issue #{number} not found on the project board")
        return 1
    result = _board_set(board, item_id, new_status)
    if result.returncode != 0:
        return _passthrough(result)
    print(f"Issue #{number} → {args.status_raw}")
    return 0


# ---------------------------------------------------------------- view, list, edit, comment


def _derive_status(node: dict, board: Board | None) -> str:
    """LLD Open question 1: closed is done; open takes its board column, else todo."""
    if node["state"] == "CLOSED":
        return "done"
    if board is not None:
        _, option = _board_item(board, node)
        for name, option_id in board.options.items():
            if option is not None and option == option_id:
                return name
    return "todo"


_MAX_CHILDREN = 100


def _child_statuses(children: list[str], board: Board | None) -> dict[str, str]:
    """One aliased GraphQL call for up to 100 children (no per-child calls); a node that does
    not exist is omitted, so the reader shows it as unknown."""
    refs = children[:_MAX_CHILDREN]
    if not refs:
        return {}
    fields = "state" + (" " + _BOARD_FIELDS if board is not None else "")
    aliases = " ".join(f"c{i}:issue(number:{_parse_ref(ref)}){{{fields}}}" for i, ref in enumerate(refs))
    query = f"query($owner:String!,$name:String!){{repository(owner:$owner,name:$name){{{aliases}}}}}"
    result = _gh(["api", "graphql", "-F", "owner={owner}", "-F", "name={repo}", "-f", f"query={query}"])
    stderr_lines = [line for line in result.stderr.splitlines() if line.strip()]
    if result.returncode != 0 and not (stderr_lines and all(_NOT_FOUND in line for line in stderr_lines)):
        raise TrackerError(f"gh api graphql failed: {result.stderr.strip()}")
    try:
        nodes = json.loads(result.stdout)["data"]["repository"]
    except (json.JSONDecodeError, KeyError, TypeError) as e:
        raise TrackerError("unexpected gh api graphql response") from e
    return {ref: _derive_status(nodes[f"c{i}"], board) for i, ref in enumerate(refs) if nodes.get(f"c{i}")}


def parent_from_body(body: str) -> str | None:
    match = re.search(r"## Parent epic\s*\n+#(\d+)", body)
    return f"#{match.group(1)}" if match else None


def children_from_body(body: str) -> list[str]:
    refs = re.findall(r"^\s*- \[[ xX]\] #(\d+)\b", body, re.M)
    return [f"#{n}" for n in dict.fromkeys(refs)]


def _to_issue(node: dict, board: Board | None) -> Issue:
    labels = [label["name"] for label in node["labels"]["nodes"]]
    body = node.get("body") or ""
    return Issue(ref=f"#{node['number']}", title=node["title"], body=body, labels=labels,
                 status=_derive_status(node, board), parent=parent_from_body(body),
                 children=children_from_body(body) if "epic" in labels else [])


# Justification: view, edit and comment share the "#N not found" existence check (AC5).
def _require_issue(ref: str, *, board: bool = False) -> tuple[int, dict]:
    number = _parse_ref(ref)
    node = _fetch_issue(number, board=board)
    if node is None:
        raise TrackerError(f"#{number} not found")
    return number, node


def view(args: argparse.Namespace, ctx: object) -> int:
    board = load_board(getattr(ctx, "repo_root", None), strict=False)
    _, node = _require_issue(args.ref, board=board is not None)
    issue = _to_issue(node, board)
    print(issue_json(replace(issue, child_statuses=_child_statuses(issue.children, board))))
    return 0


def list_issues(args: argparse.Namespace, ctx: object) -> int:
    wanted = normalise_status(args.status) if args.status is not None else None
    query = ["api", "graphql", "-F", "owner={owner}", "-F", "name={repo}", "-F", "first=100",
             "-f", f"states[]={'CLOSED' if wanted == 'done' else 'OPEN'}"]
    if args.label:
        query += ["-f", f"labels[]={args.label}"]
    board = load_board(getattr(ctx, "repo_root", None), strict=False)
    result = _gh([*query, "-f", f"query={ISSUES_QUERY if board else _PLAIN_ISSUES_QUERY}"])
    if result.returncode != 0:
        raise TrackerError(f"gh api graphql failed: {result.stderr.strip()}")
    try:
        nodes = json.loads(result.stdout)["data"]["repository"]["issues"]["nodes"]
    except (json.JSONDecodeError, KeyError, TypeError) as e:
        raise TrackerError("unexpected gh api graphql response") from e
    issues = [_to_issue(node, board) for node in nodes]
    print(issue_json([i for i in issues if wanted is None or i.status == wanted]))
    return 0


def edit(args: argparse.Namespace, ctx: object) -> int:
    number, node = _require_issue(args.ref)
    current = {label["name"] for label in node["labels"]["nodes"]}
    remove = [label for label in args.remove_label if label in current]  # I12
    edit_args = ["issue", "edit", str(number)]
    if args.title is not None:
        edit_args += ["--title", args.title]
    if args.body is not None:
        edit_args += ["--body-file", "-"]
    if args.add_label:
        edit_args += ["--add-label", ",".join(args.add_label)]
    if remove:
        edit_args += ["--remove-label", ",".join(remove)]
    if len(edit_args) > 3:
        result = _gh(edit_args, stdin=args.body)
        if result.returncode != 0:
            raise TrackerError(f"gh issue edit failed: {result.stderr.strip()}")
    print(f"updated:#{number}")
    return 0


def comment(args: argparse.Namespace, ctx: object) -> int:
    number, _ = _require_issue(args.ref)
    result = _gh(["issue", "comment", str(number), "--body-file", "-"], stdin=args.body)
    if result.returncode != 0:
        raise TrackerError(f"gh issue comment failed: {result.stderr.strip()}")
    print(f"commented:#{number}")
    return 0


# ---------------------------------------------------------------- close


def tick_checkbox(body: str, child: str) -> str:
    return re.sub(r"- \[ \] (#" + re.escape(child) + r"\b)", r"- [x] \1", body)


def tick_parent_checkbox(child: int, body: str) -> tuple[str, str]:
    """Tick `child` in its parent epic. Returns (outcome, message); raises TrackerError on failure."""
    parent = parent_from_body(body)
    if parent is None:
        return "no-parent", f"No parent epic found for issue #{child}"
    epic = int(parent[1:])
    try:
        node = _fetch_issue(epic, board=False)
    except TrackerError:
        # TODO(#121): the cause is dropped to keep the old "Failed to read epic" text byte-identical.
        node = None
    if node is None:
        raise TrackerError(f"Failed to read epic #{epic}")
    epic_body = node["body"] or ""
    updated = tick_checkbox(epic_body, str(child))
    if updated == epic_body:
        return "already", f"Epic #{epic}: checkbox for #{child} already ticked or not found"
    result = _write_body(epic, updated)
    if result.returncode != 0:
        raise TrackerError(f"Failed to update epic #{epic}: {result.stderr}")
    return "ticked", f"Epic #{epic}: checked off #{child}"


# Justification: close's three sub-steps share one warn-and-continue policy (I16).
def _step(number: int, name: str, action: Callable[[], object]) -> None:
    try:
        result = action()
        failure = result.stderr if isinstance(result, subprocess.CompletedProcess) and result.returncode else None
    except TrackerError as e:
        failure = str(e)
    if failure is not None:
        detail = " ".join(failure.split()) or "no detail"
        print(f"Warning: close #{number}: {name} failed — {detail}", file=sys.stderr)


def close(args: argparse.Namespace, ctx: object) -> int:
    number = _parse_ref(args.ref)
    board = load_board(getattr(ctx, "repo_root", None), strict=False)
    node = _fetch_issue(number, board=board is not None)
    if node is None:
        raise TrackerError(f"#{number} not found")
    if board is not None:
        item_id, option = _board_item(board, node)
        if item_id and option != board.options["done"]:
            _step(number, "board", lambda: _board_set(board, item_id, "done"))
    _step(number, "epic", lambda: tick_parent_checkbox(number, node["body"] or ""))
    if node["state"] == "OPEN":
        _step(number, "issue close", lambda: _gh(["issue", "close", str(number)]))
    print(f"closed:#{number}")
    return 0
