"""Fake `gh` executable driven by a scenario file.

FAKE_GH_SCENARIO: JSON list of rules {"argv_prefix": [...], "stdout": "", "stderr": "", "exit": 0};
the first rule whose prefix matches argv wins. An optional "argv_contains": [...] further requires
every listed element to appear somewhere in argv (e.g. "number=7" to tell GraphQL lookups apart).
No match → stderr "fake gh: unexpected call <argv>", exit 97. A missing scenario file means no rules.
FAKE_GH_LOG: every call appends {"argv": [...], "stdin": "..."} as one JSON line.
"""

import json
import os
import select
import sys

# A caller that passes input= (or DEVNULL) makes stdin readable at once; an inherited pipe
# that never closes must not hang the test, so stop waiting after this many seconds.
_STDIN_WAIT_SECONDS = 2.0


def _read_stdin() -> str:
    if sys.stdin is None or sys.stdin.isatty():
        return ""
    ready, _, _ = select.select([sys.stdin], [], [], _STDIN_WAIT_SECONDS)
    return sys.stdin.read() if ready else ""


def main(argv: list[str]) -> int:
    log_path = os.environ.get("FAKE_GH_LOG")
    if log_path:
        with open(log_path, "a", encoding="utf-8") as log:
            log.write(json.dumps({"argv": argv, "stdin": _read_stdin()}) + "\n")
    scenario = os.environ.get("FAKE_GH_SCENARIO")
    rules = []
    if scenario and os.path.exists(scenario):
        with open(scenario, encoding="utf-8") as f:
            rules = json.load(f)
    for rule in rules:
        prefix = rule.get("argv_prefix", [])
        contains = rule.get("argv_contains", [])
        if argv[: len(prefix)] == prefix and all(item in argv for item in contains):
            sys.stdout.write(rule.get("stdout", ""))
            sys.stderr.write(rule.get("stderr", ""))
            return int(rule.get("exit", 0))
    sys.stderr.write(f"fake gh: unexpected call {argv}\n")
    return 97


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
