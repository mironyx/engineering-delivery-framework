"""Tests for parser scripts: parse-pytest-output, parse-vitest-output, parse-project-item-id."""

import pathlib
import subprocess
import sys

import pytest

BIN_DIR = pathlib.Path(__file__).resolve().parent.parent / "plugins" / "edf" / "bin"
FIXTURES = pathlib.Path(__file__).resolve().parent / "fixtures"


def _run_parser(script_name, fixture_name):
    fixture = FIXTURES / fixture_name
    result = subprocess.run(
        [sys.executable, str(BIN_DIR / script_name)],
        input=fixture.read_bytes(),
        capture_output=True,
        timeout=15,
    )
    return result


# ── parse-pytest-output ──────────────────────────────────────────────────────


class TestParsePytestOutput:
    def test_passed_output(self):
        result = _run_parser("parse-pytest-output.py", "pytest_passed.txt")
        assert result.returncode == 0
        assert b"PASS 12/12" in result.stdout
        assert b"2.34s" in result.stdout

    def test_failed_output(self):
        result = _run_parser("parse-pytest-output.py", "pytest_failed.txt")
        assert b"FAIL 2/12" in result.stdout
        assert b"test_token_refresh" in result.stdout
        assert b"test_create_user" in result.stdout

    def test_error_output(self):
        result = _run_parser("parse-pytest-output.py", "pytest_error.txt")
        # Parser reports fail count from summary line. ERROR entries aren't FAILED
        # lines, so individual test names won't be extracted.
        assert b"FAIL 2/3" in result.stdout

    def test_no_summary_crash(self):
        # No summary line + failure signals -> must NOT be reported as a pass.
        result = _run_parser("parse-pytest-output.py", "pytest_no_summary.txt")
        assert result.returncode == 2
        assert b"INCONCLUSIVE" in result.stdout
        assert b"crashed" in result.stdout

    def test_empty_input_inconclusive(self):
        # Empty input -> ambiguous, never a blind PASS 0/0.
        result = _run_parser("parse-pytest-output.py", "pytest_empty.txt")
        assert result.returncode == 2
        assert b"INCONCLUSIVE" in result.stdout

    def test_ansi_stripping(self):
        ansi_input = b"\x1b[32mPASSED\x1b[0m tests/test_auth.py::test_login\n\x1b[31mFAILED\x1b[0m tests/test_bug.py::test_bug - AssertionError\n========================= 1 passed, 1 failed in 0.50s ========================="
        result = subprocess.run(
            [sys.executable, str(BIN_DIR / "parse-pytest-output.py")],
            input=ansi_input,
            capture_output=True,
            timeout=15,
        )
        assert b"FAIL 1/2" in result.stdout


# ── parse-vitest-output ──────────────────────────────────────────────────────


class TestParseVitestOutput:
    def test_passed_output(self):
        result = _run_parser("parse-vitest-output.py", "vitest_passed.txt")
        assert result.returncode == 0
        assert b"PASS 25/25" in result.stdout
        assert b"3.45s" in result.stdout

    def test_failed_output(self):
        result = _run_parser("parse-vitest-output.py", "vitest_failed.txt")
        assert b"FAIL 2/25" in result.stdout
        assert b"should create user" in result.stdout
        assert b"should delete user" in result.stdout

    def test_empty_output(self):
        result = _run_parser("parse-vitest-output.py", "vitest_empty.txt")
        assert result.returncode == 0

    def test_no_summary_inconclusive(self):
        # No "Tests" summary line and no crash signal -> ambiguous, not a blind PASS.
        result = _run_parser("parse-vitest-output.py", "vitest_crash.txt")
        assert result.returncode == 2
        assert b"INCONCLUSIVE" in result.stdout


# ── parse-project-item-id ────────────────────────────────────────────────────


class TestParseProjectItemId:
    def _run(self, fixture_name, project_id):
        fixture = FIXTURES / fixture_name
        result = subprocess.run(
            [sys.executable, str(BIN_DIR / "parse-project-item-id.py"), project_id],
            input=fixture.read_bytes(),
            capture_output=True,
            timeout=15,
        )
        return result

    def test_find_matching_project(self):
        result = self._run("project_items.json", "PVT_myproject")
        assert result.returncode == 0
        assert b"PVTI_target" in result.stdout

    def test_no_match(self):
        result = self._run("project_items_no_match.json", "PVT_myproject")
        assert result.returncode == 1
        assert result.stdout.strip() == b""

    def test_missing_argument(self):
        result = subprocess.run(
            [sys.executable, str(BIN_DIR / "parse-project-item-id.py")],
            capture_output=True,
            timeout=15,
        )
        assert result.returncode == 1
