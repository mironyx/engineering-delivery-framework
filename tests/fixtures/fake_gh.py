"""Fake `gh` executable driven by a scenario file.

FAKE_GH_SCENARIO: JSON list of rules {"argv_prefix": [...], "stdout": "", "stderr": "", "exit": 0};
the first rule whose prefix matches argv wins. No match → stderr
"fake gh: unexpected call <argv>", exit 97. A missing scenario file means no rules.
FAKE_GH_LOG: every call appends {"argv": [...], "stdin": "..."} as one JSON line.
"""

import json
import os
import sys


def _read_stdin() -> str:
    if sys.stdin is None or sys.stdin.isatty():
        return ""
    return sys.stdin.read()


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
        if argv[: len(prefix)] == prefix:
            sys.stdout.write(rule.get("stdout", ""))
            sys.stderr.write(rule.get("stderr", ""))
            return int(rule.get("exit", 0))
    sys.stderr.write(f"fake gh: unexpected call {argv}\n")
    return 97


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
