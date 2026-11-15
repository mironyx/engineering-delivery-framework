"""Record the tracker golden matrix from the pre-port bash scripts (#119, LLD v3 E3.1 §1.2, I6).

Usage: python3 tests/fixtures/record_tracker_golden.py [--rev <git-rev>]

Extracts gh-create-issue.sh, gh-project-status.sh and parse-project-item-id.py as they were
at <rev> (default: the last commit before the port), runs every scenario below under the fake
`gh` (tests/fixtures/fake_gh.py) and writes tests/fixtures/tracker_golden/<name>.json with
{script, argv, tracker_argv, setup, rules, compare, stdout, stderr, exit}.

Paths that vary per run are tokenised: the script path ($0 in usage text) as {script} and the
scenario's working directory as {cwd}. `port_stdout`/`port_stderr`, when present, replace stdout/stderr as the port's expected output
(INTENTIONAL_CHANGES). `compare: "first_stderr_line"` marks scenarios where
only the exit code and first stderr line are parity-bound (LLD Open question 4).
"""

from __future__ import annotations

import argparse
import json
import os
import pathlib
import subprocess
import sys
import tempfile

HERE = pathlib.Path(__file__).resolve().parent
REPO_ROOT = HERE.parent.parent
GOLDEN_DIR = HERE / "tracker_golden"
PRE_PORT_REV = "0f8ad5f"
SCRIPTS = ("gh-create-issue.sh", "gh-project-status.sh", "parse-project-item-id.py")

PROJECT_ENV = {
    "REPO": "owner/repo",
    "PROJECT_NUMBER": "4",
    "PROJECT_ID": "PVT_abc",
    "FIELD_ID": "PVTSSF_xyz",
    "STATUS_TODO": "todo-id",
    "STATUS_BLOCKED": "blocked-id",
    "STATUS_IN_PROGRESS": "in-progress-id",
    "STATUS_DONE": "done-id",
}


def _issue_response(number: int, project_id: str) -> str:
    """Full ISSUE_FIELDS node — a superset of what the bash find_item_id query reads."""
    node = {
        "number": number,
        "title": "Some issue",
        "body": "Body",
        "state": "OPEN",
        "labels": {"nodes": []},
        "projectItems": {"nodes": [{"id": "PVTI_item", "project": {"id": project_id}, "fieldValues": {"nodes": []}}]},
    }
    return json.dumps({"data": {"repository": {"issue": node}}}) + "\n"


NO_DUP = {"argv_prefix": ["issue", "list"], "stdout": ""}
CREATED = {"argv_prefix": ["issue", "create"], "stdout": "https://github.com/owner/repo/issues/42\n"}
ON_BOARD = {"argv_prefix": ["api", "graphql"], "stdout": _issue_response(42, "PVT_abc")}
EDIT_OK = {"argv_prefix": ["project", "item-edit"], "stdout": ""}
ITEM_ADD_OK = {"argv_prefix": ["project", "item-add"], "stdout": '{"id":"PVTI_new"}\n'}

CREATE, STATUS = "gh-create-issue.sh", "gh-project-status.sh"
BASE = ["--title", "Add widget", "--body", "Line one\nLine two"]

# name: (script, argv, tracker_argv (None = shim only), setup, rules, compare)
SCENARIOS: dict[str, tuple] = {
    "create-created": (CREATE, BASE, ["create", *BASE], {}, [NO_DUP, CREATED], "exact"),
    "create-exists": (CREATE, BASE, ["create", *BASE], {},
                      [{"argv_prefix": ["issue", "list"], "stdout": "17\n"}], "exact"),
    "create-dry-run": (CREATE, [*BASE, "--dry-run"], ["create", *BASE, "--dry-run"], {}, [NO_DUP], "exact"),
    "create-dry-run-labels": (CREATE, [*BASE, "--labels", "bug,high-priority", "--dry-run"],
                              ["create", *BASE, "--labels", "bug,high-priority", "--dry-run"], {}, [NO_DUP], "exact"),
    "create-add-to-board-ok": (CREATE, [*BASE, "--add-to-board"], ["create", *BASE, "--add-to-board"],
                               {"project_env": True}, [NO_DUP, CREATED, ITEM_ADD_OK, EDIT_OK], "exact"),
    "create-add-to-board-fails": (CREATE, [*BASE, "--add-to-board"], ["create", *BASE, "--add-to-board"],
                                  {"project_env": True},
                                  [NO_DUP, CREATED, {"argv_prefix": ["project", "item-add"], "stderr": "boom\n",
                                                     "exit": 1}], "exact"),
    "create-gh-fails": (CREATE, BASE, ["create", *BASE], {},
                        [NO_DUP, {"argv_prefix": ["issue", "create"], "stderr": "HTTP 422: Validation Failed\n",
                                  "exit": 1}], "exact"),
    "create-url-without-number": (CREATE, BASE, ["create", *BASE], {},
                                  [NO_DUP, {"argv_prefix": ["issue", "create"],
                                            "stdout": "https://github.com/owner/repo/issues/new\n"}], "exact"),
    "create-missing-title": (CREATE, ["--body", "B"], ["create", "--body", "B"], {}, [], "exact"),
    "create-missing-body": (CREATE, ["--title", "T"], ["create", "--title", "T"], {}, [], "exact"),
    "create-unknown-option": (CREATE, [*BASE, "--bogus"], ["create", *BASE, "--bogus"], {}, [], "exact"),
    "create-dash-body": (CREATE, ["--title", "T", "--body", "--y", "--dry-run"],
                         ["create", "--title", "T", "--body", "--y", "--dry-run"], {}, [NO_DUP], "exact"),
    "status-set": (STATUS, ["42", "todo"], ["status", "42", "todo"], {"project_env": True},
                   [ON_BOARD, EDIT_OK], "exact"),
    "status-mixed-case": (STATUS, ["42", "In Progress"], ["status", "42", "In Progress"], {"project_env": True},
                          [ON_BOARD, EDIT_OK], "exact"),
    "status-unknown-issue": (STATUS, ["999", "todo"], ["status", "999", "todo"], {"project_env": True},
                             [{"argv_prefix": ["api", "graphql"],
                               "stderr": "gh: Could not resolve to an Issue with the number of 999.\n", "exit": 1}],
                             "first_stderr_line"),
    "status-unknown-status-no-config": (STATUS, ["42", "bogus"], ["status", "42", "bogus"], {}, [], "exact"),
    "status-not-on-board": (STATUS, ["42", "todo"], ["status", "42", "todo"], {"project_env": True},
                            [{"argv_prefix": ["api", "graphql"], "stdout": _issue_response(42, "PVT_other")}],
                            "exact"),
    "status-item-edit-fails": (STATUS, ["42", "done"], ["status", "42", "done"], {"project_env": True},
                               [ON_BOARD, {"argv_prefix": ["project", "item-edit"], "stderr": "edit failed\n",
                                           "exit": 1}], "exact"),
    "status-add-with-status": (STATUS, ["add", "42", "blocked"], ["status", "42", "blocked", "--add-to-board"],
                               {"project_env": True}, [ITEM_ADD_OK, EDIT_OK], "exact"),
    "status-add-default": (STATUS, ["add", "42"], ["status", "42", "todo", "--add-to-board"],
                           {"project_env": True}, [ITEM_ADD_OK, EDIT_OK], "exact"),
    "status-add-without-number": (STATUS, ["add"], None, {"project_env": True}, [], "exact"),
    "status-unknown-status": (STATUS, ["42", "bogus"], ["status", "42", "bogus"], {"project_env": True}, [],
                              "exact"),
    "status-missing-config": (STATUS, ["42", "todo"], ["status", "42", "todo"], {}, [], "exact"),
    "status-outside-git": (STATUS, ["42", "todo"], ["status", "42", "todo"], {"git": False}, [], "exact"),
    "status-missing-config-var": (STATUS, ["42", "todo"], ["status", "42", "todo"],
                                  {"project_env": True, "omit_var": "FIELD_ID"}, [], "exact"),
    "status-one-argument": (STATUS, ["42"], None, {"project_env": True}, [], "exact"),
    "status-no-arguments": (STATUS, [], None, {"project_env": True}, [], "exact"),
}


# Intentional output changes (LLD Open question 4). Under `set -euo pipefail` the bash scripts
# exit 1 silently in these scenarios — their error lines are unreachable dead code. The port
# prints the message the scripts meant to print; the golden keeps the bash bytes and adds the
# port's expected output alongside.
INTENTIONAL_CHANGES: dict[str, dict[str, str]] = {
    "create-url-without-number": {
        "port_stdout": "",
        "port_stderr": "Error: could not extract issue number from: https://github.com/owner/repo/issues/new\n",
    },
    "status-not-on-board": {
        "port_stdout": "Error: issue #42 not found on the project board\n",
        "port_stderr": "",
    },
}


def prepare_cwd(base: pathlib.Path, setup: dict) -> pathlib.Path:
    """Build the scenario's working directory (shared with tests/test_tracker_github.py)."""
    cwd = base / "work"
    cwd.mkdir()
    if setup.get("git", True):
        subprocess.run(["git", "init", "-q", str(cwd)], check=True)
    if setup.get("project_env"):
        omit = setup.get("omit_var")
        (cwd / ".github").mkdir()
        (cwd / ".github" / "project.env").write_text(
            "".join(f"{k}={v}\n" for k, v in PROJECT_ENV.items() if k != omit), encoding="utf-8"
        )
    return cwd


def tokenise(text: str, script: pathlib.Path, cwd: pathlib.Path) -> str:
    return text.replace(str(script), "{script}").replace(str(cwd), "{cwd}")


def _fake_gh_env(base: pathlib.Path, rules: list[dict]) -> dict[str, str]:
    bin_dir = base / "bin"
    bin_dir.mkdir()
    wrapper = bin_dir / "gh"
    wrapper.write_text(f'#!/bin/sh\nexec "{sys.executable}" "{HERE / "fake_gh.py"}" "$@"\n', encoding="utf-8")
    wrapper.chmod(0o755)
    (base / "scenario.json").write_text(json.dumps(rules), encoding="utf-8")
    env = {k: v for k, v in os.environ.items() if not k.startswith("JIRA_")}
    env.update(PATH=f"{bin_dir}{os.pathsep}{env.get('PATH', '')}", FAKE_GH_SCENARIO=str(base / "scenario.json"))
    env.pop("FAKE_GH_LOG", None)
    return env


def record(name: str, script_dir: pathlib.Path) -> dict:
    script_name, argv, tracker_argv, setup, rules, compare = SCENARIOS[name]
    with tempfile.TemporaryDirectory() as tmp:
        base = pathlib.Path(tmp)
        cwd = prepare_cwd(base, setup)
        script = script_dir / script_name
        result = subprocess.run(["bash", str(script), *argv], cwd=cwd, env=_fake_gh_env(base, rules),
                                capture_output=True, text=True, timeout=60, stdin=subprocess.DEVNULL)
        return {
            "script": script_name, "argv": argv, "tracker_argv": tracker_argv, "setup": setup, "rules": rules,
            "compare": compare, "stdout": tokenise(result.stdout, script, cwd),
            "stderr": tokenise(result.stderr, script, cwd), "exit": result.returncode,
            **INTENTIONAL_CHANGES.get(name, {}),
        }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rev", default=PRE_PORT_REV)
    args = parser.parse_args()
    GOLDEN_DIR.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        script_dir = pathlib.Path(tmp)
        for name in SCRIPTS:
            content = subprocess.run(["git", "show", f"{args.rev}:plugins/edf/bin/{name}"], cwd=REPO_ROOT,
                                     check=True, capture_output=True).stdout
            (script_dir / name).write_bytes(content)
            (script_dir / name).chmod(0o755)
        for name in SCENARIOS:
            golden = record(name, script_dir)
            (GOLDEN_DIR / f"{name}.json").write_text(json.dumps(golden, indent=2, ensure_ascii=False) + "\n",
                                                     encoding="utf-8")
            print(f"{name}: exit {golden['exit']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
