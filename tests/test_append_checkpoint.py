"""Tests for bin/append-checkpoint.py — cost checkpoint row placement.

The script must insert rows into the ``## Cost checkpoints`` table, not append
to end-of-file: session logs have sections (e.g. ``## Cost retrospective``,
``## Next steps``) after the table, so a naive append lands the row under the
wrong heading.
"""

import pathlib
import subprocess
import sys

BIN_DIR = pathlib.Path(__file__).resolve().parent.parent / "plugins" / "edf" / "bin"


def _run(session_log, *args):
    return subprocess.run(
        [sys.executable, str(BIN_DIR / "append-checkpoint.py"),
         "--session-log", str(session_log), *args],
        capture_output=True,
        text=True,
        timeout=30,
    )


def test_inserts_row_into_cost_checkpoints_table(tmp_path):
    log = tmp_path / "session.md"
    log.write_text(
        "# Session\n"
        "## Cost checkpoints\n"
        "| Step | Timestamp | Cost | Note |\n"
        "|------|-----------|------|------|\n"
        "| 3c | 2026-08-24T09:18:09Z | $0.00 | pressure: heavy |\n"
        "\n"
        "## Cost retrospective\n"
        "No data.\n"
        "\n"
        "## Next steps\n"
        "- Run feature.\n",
        encoding="utf-8",
    )
    result = _run(log, "--step", "5", "--note", "green on attempt 1")
    assert result.returncode == 0, result.stderr

    text = log.read_text(encoding="utf-8")
    assert "| 5 |" in text
    assert "green on attempt 1" in text
    # The new row lands inside the Cost checkpoints table, before the next heading.
    assert text.index("| 5 |") < text.index("## Cost retrospective")
    # Trailing sections are intact.
    assert "No data." in text
    assert "- Run feature." in text


def test_appends_at_end_when_no_heading(tmp_path):
    log = tmp_path / "session.md"
    log.write_text("# Session\nJust prose, no cost table.\n", encoding="utf-8")
    result = _run(log, "--step", "5", "--note", "x")
    assert result.returncode == 0
    assert "Warning" in result.stderr
    assert log.read_text(encoding="utf-8").rstrip().endswith("| x |")
