"""Gate: confirm a session log carries the cost checkpoints its pressure tier requires.

Usage:
  py bin/check-checkpoints.py --issue <ref>
  py bin/check-checkpoints.py --session-log <path>

Reads the session log's `## Cost checkpoints` table and its `Pressure:` line.

Output (one line per finding):
  missing: 4bF,6b      Standard/Heavy log without those rows (exit 1)
  missing: session log no session log found for the issue (exit 1)
  bulk: 5,6,6b         >= 3 consecutive rows written within 60 s of the first — a
                       backfill signature (warning, exit 0); one line per run
  checkpoints: ok      nothing to report (exit 0)

Light-tier logs, and logs with no checkpoint table, need no rows (exit 0).
"""

from __future__ import annotations

import argparse
import importlib.util
import pathlib
import re
import subprocess
import sys
from datetime import datetime

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

import _edf_env
import _feature_id
from _tracker_contract import TrackerError

REQUIRED = ("4bF", "6b")
BULK_MIN_ROWS = 3
BULK_WINDOW_SECONDS = 60

_PRESSURE = re.compile(r"Pressure:\**\s*\**\s*(light|standard|heavy)\b", re.IGNORECASE)
_TABLE_HEADING = "## Cost checkpoints"
_TIMESTAMP_FORMAT = "%Y-%m-%dT%H:%M:%SZ"


# Justification: tested contract surface — the tier decides which rows are required.
def parse_pressure(text: str) -> str | None:
    """Lower-cased tier word from the `Pressure:` line ('light' | 'standard' | 'heavy'), or None."""
    match = _PRESSURE.search(text)
    return match.group(1).lower() if match else None


# Justification: tested contract surface — feeds both the missing and the bulk check.
def parse_rows(text: str) -> list[tuple[str, datetime]] | None:
    """(step, timestamp) per data row of the `## Cost checkpoints` table, in file order.

    None when the log has no such table; rows with an unparseable timestamp are skipped.
    """
    lines = text.splitlines()
    start = next((i for i, ln in enumerate(lines) if ln.strip().startswith(_TABLE_HEADING)), None)
    if start is None:
        return None
    rows = []
    for line in lines[start + 1:]:
        if line.strip().startswith("## "):
            break
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) < 2 or cells[0] == "Step" or not cells[0].strip("-: "):
            continue  # blank line, header or separator
        try:
            rows.append((cells[0], datetime.strptime(cells[1], _TIMESTAMP_FORMAT)))
        except ValueError:
            # A data row that cannot be read would otherwise surface as "missing" with no reason.
            print(f"warning: step {cells[0]} row has an unreadable timestamp '{cells[1]}' — skipped",
                  file=sys.stderr)
    return rows


# Justification: tested contract surface — the tier rule (light never missing) in isolation.
def missing_steps(pressure: str | None, steps: list[str]) -> list[str]:
    """REQUIRED steps absent from `steps` — always [] for 'light'; None counts as standard."""
    if pressure == "light":
        return []
    return [step for step in REQUIRED if step not in steps]


# Justification: tested contract surface — the 60 s window rule in isolation.
def bulk_runs(rows: list[tuple[str, datetime]]) -> list[list[str]]:
    """Runs of >= BULK_MIN_ROWS consecutive rows whose timestamps fall within
    BULK_WINDOW_SECONDS of the run's first row; each run as its list of step labels."""
    runs: list[list[str]] = []
    i = 0
    while i < len(rows):
        first = rows[i][1]
        j = i + 1
        while j < len(rows) and 0 <= (rows[j][1] - first).total_seconds() <= BULK_WINDOW_SECONDS:
            j += 1
        if j - i >= BULK_MIN_ROWS:
            runs.append([step for step, _ in rows[i:j]])
            i = j
        else:
            i += 1
    return runs


# Justification: --issue lookup reuses append-checkpoint's find_session_log so both scripts
# resolve the same log (hyphenated module, loaded by path).
def _find_log(issue: str) -> pathlib.Path | None:
    root = _feature_id.main_checkout_root()
    feature_id = _feature_id.resolve_feature_id(issue, root)
    spec = importlib.util.spec_from_file_location(
        "append_checkpoint", pathlib.Path(__file__).resolve().parent / "append-checkpoint.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    toplevel = subprocess.run(["git", "rev-parse", "--show-toplevel"],
                              capture_output=True, text=True, check=False).stdout.strip()
    return module.find_session_log(pathlib.Path(toplevel or "."), feature_id, _edf_env.docs_dir(root))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--issue", help="Issue ref (number or Jira key)")
    source.add_argument("--session-log", help="Path to the session log .md file")
    args = parser.parse_args(argv)

    if args.session_log:
        log = pathlib.Path(args.session_log)
    else:
        try:
            log = _find_log(args.issue)
        except TrackerError as e:
            print(f"Error: {e}", file=sys.stderr)
            return 1
    if log is None or not log.is_file():
        print("missing: session log")
        return 1

    text = log.read_text(encoding="utf-8")
    rows = parse_rows(text)
    if rows is None:
        print("checkpoints: ok (no checkpoint table)")
        return 0
    missing = missing_steps(parse_pressure(text), [step for step, _ in rows])
    runs = bulk_runs(rows)
    if missing:
        print(f"missing: {','.join(missing)}")
    for run in runs:
        print(f"bulk: {','.join(run)}")
    if not missing and not runs:
        print("checkpoints: ok")
    return 1 if missing else 0


if __name__ == "__main__":
    raise SystemExit(main())
