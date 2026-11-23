"""#168 — bin/check-checkpoints.py: the cost-checkpoint gate run before PR creation and at feature-end.

Contract (issue #168 §2):
- Standard/Heavy logs (and logs with no `Pressure:` line) must carry rows 4bF and 6b;
  absent ones are printed as `missing: 4bF,6b` and the exit code is 1.
- Light logs never report missing rows; a log with no `## Cost checkpoints` table exits 0.
- No session log at all -> `missing: session log`, exit 1.
- >= 3 consecutive rows within 60 s of the run's first row -> `bulk: <steps>` (one line per run,
  warning only: exit 0 unless rows are also missing).
- `checkpoints: ok` only when there is nothing else to report.
"""

from __future__ import annotations

import importlib.util
import pathlib
import subprocess
import sys
from datetime import datetime, timedelta, timezone

import pytest

BIN_DIR = pathlib.Path(__file__).resolve().parent.parent / "plugins" / "edf" / "bin"
SCRIPT = BIN_DIR / "check-checkpoints.py"
sys.path.insert(0, str(BIN_DIR))


def _load_module():
    spec = importlib.util.spec_from_file_location("check_checkpoints", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


cc = _load_module()

HEADER = (
    "| Step | Timestamp | Cost (cumulative) | Tokens (cumulative) | Note |\n"
    "|------|-----------|--------------------|----------------------|------|\n"
)


def _row(step: str, ts: str) -> str:
    return f"| {step} | {ts} | $1.00 | 10 in / 20 out | note for {step} |\n"


def _log(pressure: str | None, rows: list[tuple[str, str]] | None, tail: bool = True) -> str:
    """A session log shaped like the real ones: Pressure bullet, table, sections after it."""
    text = "# Session log — EDF-168\n\n"
    if pressure is not None:
        text += f"- **Pressure:** {pressure} — ~150 src lines across 4 source files\n"
    text += "\n"
    if rows is not None:
        text += "## Cost checkpoints\n" + HEADER + "".join(_row(s, t) for s, t in rows)
    if tail:
        text += "\n## Concerns & Deferred Items\n- none\n"
    return text


# Rows minutes apart: no bulk signature.
SPREAD_ALL = [
    ("3c", "2026-11-23T07:00:00Z"),
    ("4bF", "2026-11-23T07:10:00Z"),
    ("5", "2026-11-23T07:20:00Z"),
    ("6", "2026-11-23T07:30:00Z"),
    ("6b", "2026-11-23T07:40:00Z"),
    ("8", "2026-11-23T07:50:00Z"),
]
SPREAD_NO_REQUIRED = [r for r in SPREAD_ALL if r[0] not in ("4bF", "6b")]


def _run(log_path: pathlib.Path, cwd: pathlib.Path | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT), "--session-log", str(log_path)],
        capture_output=True, text=True, timeout=30, cwd=cwd, check=False,
    )


def _write(tmp_path: pathlib.Path, text: str) -> pathlib.Path:
    path = tmp_path / "2026-11-23-session-1-x-EDF-168.md"
    path.write_text(text, encoding="utf-8")
    return path


def _lines(result: subprocess.CompletedProcess[str]) -> list[str]:
    return [ln.strip() for ln in result.stdout.splitlines() if ln.strip()]


# ── pure helpers ─────────────────────────────────────────────────────────────


class TestParsePressure:
    @pytest.mark.parametrize("tier", ["light", "standard", "heavy"])
    def test_bullet_form_from_real_session_logs(self, tier):
        assert cc.parse_pressure(_log(tier, [])) == tier

    def test_tier_word_is_lower_cased(self):
        assert cc.parse_pressure("Pressure: Heavy\n") == "heavy"

    def test_absent_pressure_line_is_none(self):
        assert cc.parse_pressure(_log(None, [])) is None


class TestParseRows:
    def test_rows_in_file_order_with_parsed_timestamps(self):
        rows = cc.parse_rows(_log("standard", SPREAD_ALL))
        assert [s for s, _ in rows] == [s for s, _ in SPREAD_ALL]
        assert rows[0][1].replace(tzinfo=None) == datetime(2026, 11, 23, 7, 0, 0)

    def test_header_separator_and_following_sections_are_not_rows(self):
        rows = cc.parse_rows(_log("standard", [("3c", "2026-11-23T07:00:00Z")]))
        assert [s for s, _ in rows] == ["3c"]

    def test_no_table_is_none(self):
        assert cc.parse_rows(_log("standard", None)) is None

    def test_empty_table_is_empty_list(self):
        assert cc.parse_rows(_log("standard", [])) == []

    def test_unparseable_timestamp_row_is_skipped(self):
        rows = cc.parse_rows(_log("standard", [("3c", "2026-11-23T07:00:00Z"), ("4bF", "pending"),
                                                ("5", "2026-11-23T07:20:00Z")]))
        assert [s for s, _ in rows] == ["3c", "5"]


class TestMissingSteps:
    @pytest.mark.parametrize("tier", ["standard", "heavy", None])
    def test_required_steps_absent_are_reported_in_order(self, tier):
        assert cc.missing_steps(tier, ["3c", "5", "8"]) == ["4bF", "6b"]

    def test_only_the_absent_one_is_reported(self):
        assert cc.missing_steps("standard", ["3c", "4bF", "5"]) == ["6b"]

    def test_nothing_missing_when_both_present(self):
        assert cc.missing_steps("heavy", ["4bF", "6b"]) == []

    def test_light_never_misses(self):
        assert cc.missing_steps("light", []) == []


def _ts(sec: int) -> datetime:
    return datetime(2026, 11, 23, 7, 0, 0, tzinfo=timezone.utc) + timedelta(seconds=sec)


class TestBulkRuns:
    def test_three_rows_inside_the_window_are_one_run(self):
        rows = [("5", _ts(0)), ("6", _ts(10)), ("6b", _ts(30))]
        assert cc.bulk_runs(rows) == [["5", "6", "6b"]]

    def test_two_rows_are_not_a_run(self):
        assert cc.bulk_runs([("5", _ts(0)), ("6", _ts(10))]) == []

    def test_window_is_anchored_to_the_runs_first_row(self):
        # Each gap is 40 s, but the third row is 80 s after the first.
        rows = [("5", _ts(0)), ("6", _ts(40)), ("6b", _ts(80))]
        assert cc.bulk_runs(rows) == []

    def test_spread_rows_have_no_run(self):
        rows = [("3c", _ts(0)), ("4bF", _ts(600)), ("5", _ts(1200)), ("6", _ts(1800))]
        assert cc.bulk_runs(rows) == []

    def test_two_separate_runs(self):
        rows = [("3c", _ts(0)), ("4bF", _ts(5)), ("5", _ts(10)),
                ("6", _ts(1000)), ("6b", _ts(1010)), ("8", _ts(1020))]
        assert cc.bulk_runs(rows) == [["3c", "4bF", "5"], ["6", "6b", "8"]]

    def test_empty(self):
        assert cc.bulk_runs([]) == []


# ── CLI ──────────────────────────────────────────────────────────────────────


class TestMissingCli:
    @pytest.mark.parametrize("tier", ["standard", "heavy"])
    def test_standard_and_heavy_without_4bF_and_6b_exit_1(self, tmp_path, tier):
        result = _run(_write(tmp_path, _log(tier, SPREAD_NO_REQUIRED)))
        assert result.returncode == 1
        assert "missing: 4bF,6b" in _lines(result)
        assert "checkpoints: ok" not in _lines(result)

    def test_only_6b_missing(self, tmp_path):
        rows = [r for r in SPREAD_ALL if r[0] != "6b"]
        result = _run(_write(tmp_path, _log("standard", rows)))
        assert result.returncode == 1
        assert "missing: 6b" in _lines(result)

    def test_absent_pressure_line_counts_as_standard(self, tmp_path):
        result = _run(_write(tmp_path, _log(None, SPREAD_NO_REQUIRED)))
        assert result.returncode == 1
        assert "missing: 4bF,6b" in _lines(result)

    def test_light_is_never_missing(self, tmp_path):
        result = _run(_write(tmp_path, _log("light", [("3c", "2026-11-23T07:00:00Z")])))
        assert result.returncode == 0
        assert not any(ln.startswith("missing:") for ln in _lines(result))

    def test_no_checkpoint_table_exits_0(self, tmp_path):
        result = _run(_write(tmp_path, _log("standard", None)))
        assert result.returncode == 0
        assert not any(ln.startswith("missing:") for ln in _lines(result))

    def test_complete_log_prints_ok_only(self, tmp_path):
        result = _run(_write(tmp_path, _log("heavy", SPREAD_ALL)))
        assert result.returncode == 0, result.stderr
        assert _lines(result) == ["checkpoints: ok"]

    def test_nonexistent_session_log_path(self, tmp_path):
        result = _run(tmp_path / "nope.md")
        assert result.returncode == 1
        assert "missing: session log" in _lines(result)


class TestBulkCli:
    def test_bulk_is_a_warning_with_exit_0(self, tmp_path):
        rows = [("3c", "2026-11-23T07:00:00Z"), ("4bF", "2026-11-23T07:10:00Z"),
                ("5", "2026-11-23T07:20:00Z"), ("6", "2026-11-23T07:20:10Z"),
                ("6b", "2026-11-23T07:20:30Z"), ("8", "2026-11-23T07:20:50Z")]
        result = _run(_write(tmp_path, _log("standard", rows)))
        assert result.returncode == 0, result.stderr
        lines = _lines(result)
        assert "bulk: 5,6,6b,8" in lines
        assert "checkpoints: ok" not in lines

    def test_one_line_per_run(self, tmp_path):
        rows = [("3c", "2026-11-23T07:00:00Z"), ("4bF", "2026-11-23T07:00:05Z"),
                ("5", "2026-11-23T07:00:10Z"), ("6", "2026-11-23T08:00:00Z"),
                ("6b", "2026-11-23T08:00:10Z"), ("8", "2026-11-23T08:00:20Z")]
        result = _run(_write(tmp_path, _log("standard", rows)))
        bulk = [ln for ln in _lines(result) if ln.startswith("bulk:")]
        assert bulk == ["bulk: 3c,4bF,5", "bulk: 6,6b,8"]

    def test_bulk_and_missing_co_occur_and_exit_1(self, tmp_path):
        rows = [("3c", "2026-11-23T07:00:00Z"), ("5", "2026-11-23T07:00:10Z"),
                ("6", "2026-11-23T07:00:20Z")]
        result = _run(_write(tmp_path, _log("standard", rows)))
        assert result.returncode == 1
        lines = _lines(result)
        assert "missing: 4bF,6b" in lines
        assert "bulk: 3c,5,6" in lines
        assert "checkpoints: ok" not in lines


class TestIssueLookup:
    """--issue finds the log like append-checkpoint.py: <docs-dir>/sessions/**/*-<FEATURE_ID>.md."""

    def _repo(self, tmp_path):
        repo = tmp_path / "proj"
        (repo / "docs" / "sessions" / "2026-11").mkdir(parents=True)
        subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
        (repo / ".env").write_text("EDF_FEATURE_PREFIX=MP\n", encoding="utf-8")
        return repo

    def _run_issue(self, repo, ref):
        return subprocess.run([sys.executable, str(SCRIPT), "--issue", ref],
                              capture_output=True, text=True, timeout=30, cwd=repo, check=False)

    def test_issue_resolves_to_its_session_log(self, tmp_path, monkeypatch):
        monkeypatch.delenv("EDF_DOCS_DIR", raising=False)
        monkeypatch.delenv("EDF_FEATURE_PREFIX", raising=False)
        repo = self._repo(tmp_path)
        sessions = repo / "docs" / "sessions" / "2026-11"
        (sessions / "2026-11-23-session-1-foo-MP-42.md").write_text(
            _log("standard", SPREAD_NO_REQUIRED), encoding="utf-8")
        # A different issue whose ID shares a prefix must not be picked.
        (sessions / "2026-11-23-session-1-bar-MP-421.md").write_text(
            _log("standard", SPREAD_ALL), encoding="utf-8")
        result = self._run_issue(repo, "42")
        assert result.returncode == 1, result.stderr
        assert "missing: 4bF,6b" in _lines(result)

    def test_no_session_log_for_issue(self, tmp_path, monkeypatch):
        monkeypatch.delenv("EDF_DOCS_DIR", raising=False)
        monkeypatch.delenv("EDF_FEATURE_PREFIX", raising=False)
        repo = self._repo(tmp_path)
        result = self._run_issue(repo, "7")
        assert result.returncode == 1
        assert "missing: session log" in _lines(result)


def test_main_accepts_argv(tmp_path, capsys):
    path = _write(tmp_path, _log("standard", SPREAD_ALL))
    assert cc.main(["--session-log", str(path)]) == 0
    assert capsys.readouterr().out.strip() == "checkpoints: ok"
