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
from dataclasses import dataclass

from _tracker_contract import TrackerError, normalise_status

# TODO(#120, #121): replace these stubs with the GitHub implementation.
_NOT_IMPLEMENTED = "not implemented"

_BOARD_VARS = ("REPO", "PROJECT_NUMBER", "PROJECT_ID", "FIELD_ID",
               "STATUS_TODO", "STATUS_BLOCKED", "STATUS_IN_PROGRESS", "STATUS_DONE")
_STATUS_VARS = {"todo": "STATUS_TODO", "blocked": "STATUS_BLOCKED",
                "in progress": "STATUS_IN_PROGRESS", "done": "STATUS_DONE"}
_NOT_FOUND = "Could not resolve to an Issue"
_TYPES = ("task", "epic")

ISSUE_FIELDS = (
    "number title body state labels(first:50){nodes{name}} "
    "projectItems(first:10){nodes{id project{id} fieldValues(first:20){nodes{"
    "... on ProjectV2ItemFieldSingleSelectValue{optionId field{... on ProjectV2SingleSelectField{id}}}}}}}"
)
ISSUE_QUERY = (
    "query($owner:String!,$name:String!,$number:Int!){repository(owner:$owner,name:$name){"
    f"issue(number:$number){{{ISSUE_FIELDS}}}}}}}"
)


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
def _issue_query(number: int, repo: str | None) -> subprocess.CompletedProcess[str]:
    if repo is None:
        owner = ["-F", "owner={owner}", "-F", "name={repo}"]
    else:
        name_owner, _, name = repo.partition("/")
        owner = ["-f", f"owner={name_owner}", "-f", f"name={name}"]
    return _gh(["api", "graphql", *owner, "-F", f"number={number}", "-f", f"query={ISSUE_QUERY}"])


# Justification: parses the GraphQL envelope once for both call paths (create --parent, status).
def _issue_node(result: subprocess.CompletedProcess[str]) -> dict | None:
    """The issue node, or None when the reply says the issue does not exist (issue: null)."""
    try:
        return json.loads(result.stdout)["data"]["repository"]["issue"]
    except (json.JSONDecodeError, KeyError, TypeError) as e:
        raise TrackerError("unexpected gh api graphql response") from e


def _fetch_issue(number: int, repo: str | None = None) -> dict | None:
    result = _issue_query(number, repo)
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
    """Add the issue to the board; returns the item id, "" when gh returned none.

    Raises TrackerError when gh fails (its stderr is passed through to the caller)."""
    result = _gh(["project", "item-add", board.number, "--owner", board.owner,
                  "--url", f"https://github.com/{board.repo}/issues/{number}", "--format", "json"])
    if result.returncode != 0:
        raise TrackerError(result.stderr.strip() or "gh project item-add failed")
    try:
        return str(json.loads(result.stdout).get("id") or "")
    except (json.JSONDecodeError, AttributeError):
        return ""


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
    if new_body is not None and _write_body(epic_node["number"], new_body).returncode != 0:
        raise TrackerError(f"failed to update epic #{epic_node['number']}")


# Justification: an issue found by dedup may predate --parent; its body gets the same
# '## Parent epic' section a new issue is created with (AC: "new (or existing)").
def _ensure_parent_section(number: int, parent: int) -> None:
    node = _fetch_issue(number)
    if node is None:
        raise TrackerError(f"issue #{number} not found")
    body = _with_parent_section(node["body"], parent)
    if body != node["body"] and _write_body(number, body).returncode != 0:
        raise TrackerError(f"failed to update issue #{number}")


# Justification: shared by the created and dedup-hit paths of create; one place turns any link
# failure into the parity-style warning so the create itself still succeeds.
def _link_parent(parent_node: dict, number: int, title: str, *, existing: bool) -> None:
    parent = parent_node["number"]
    try:
        if existing:
            _ensure_parent_section(number, parent)
        _link_child(parent_node, number, title)
    except (TrackerError, KeyError, ValueError):
        print(f"Warning: failed to link #{number} to epic #{parent}", file=sys.stderr)


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
        print(f"Warning: failed to add #{number} to board", file=sys.stderr)


def create(args: argparse.Namespace, ctx: object) -> int:
    labels = _labels(args.labels, args.type)
    board_status = args.board_status if args.board_status is not None else "todo"
    parent_node = None
    if args.parent is not None:
        parent = _parse_ref(args.parent)
        parent_node = _fetch_issue(parent)
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


# ---------------------------------------------------------------- not yet ported (#120, #121)


def view(args: argparse.Namespace, ctx: object) -> int:
    raise TrackerError(_NOT_IMPLEMENTED)


def list_issues(args: argparse.Namespace, ctx: object) -> int:
    raise TrackerError(_NOT_IMPLEMENTED)


def edit(args: argparse.Namespace, ctx: object) -> int:
    raise TrackerError(_NOT_IMPLEMENTED)


def comment(args: argparse.Namespace, ctx: object) -> int:
    raise TrackerError(_NOT_IMPLEMENTED)


def close(args: argparse.Namespace, ctx: object) -> int:
    raise TrackerError(_NOT_IMPLEMENTED)
