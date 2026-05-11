"""Tests for shell script argument parsing and dry-run paths.

These tests invoke shell scripts directly via bash. They test argument validation
and dry-run modes — not live GitHub operations.
"""

import os
import pathlib
import shutil
import subprocess
import sys
import tempfile

import pytest

BIN_DIR = pathlib.Path(__file__).resolve().parent.parent / "plugins" / "edf" / "bin"
HOOKS_DIR = pathlib.Path(__file__).resolve().parent.parent / "plugins" / "edf" / "hooks"

# Git for Windows provides bash at this path (MSYS2/Cygwin-based).
_BASH_EXE = shutil.which("bash") or "bash"


def _to_msys2_path(p):
    """Convert Windows path to MSYS2/Cygwin format: C:\\foo\\bar → /c/foo/bar"""
    s = str(p).replace("\\", "/")
    if s[1:2] == ":":
        s = "/" + s[0].lower() + s[2:]
    return s


def _bash(script_path, *args, cwd=None):
    """Run a bash script with arguments."""
    result = subprocess.run(
        [_BASH_EXE, _to_msys2_path(script_path), *args],
        capture_output=True,
        text=True,
        timeout=30,
        cwd=cwd,
    )
    return result


def _gh_available():
    """Check if gh CLI is installed and authenticated."""
    try:
        result = subprocess.run(
            ["gh", "auth", "status"], capture_output=True, timeout=10
        )
        return result.returncode == 0
    except Exception:
        return False


gh_required = pytest.mark.skipif(not _gh_available(), reason="gh CLI not authenticated")


# ── gh-create-issue.sh ───────────────────────────────────────────────────────


class TestGhCreateIssue:
    def test_missing_title(self):
        result = _bash(BIN_DIR / "gh-create-issue.sh", "--body", "test body")
        assert result.returncode != 0
        assert "title" in result.stderr.lower()

    def test_missing_body(self):
        result = _bash(BIN_DIR / "gh-create-issue.sh", "--title", "test title")
        assert result.returncode != 0
        assert "body" in result.stderr.lower()

    def test_unknown_option(self):
        result = _bash(BIN_DIR / "gh-create-issue.sh", "--unknown-flag")
        assert result.returncode != 0

    @gh_required
    def test_dry_run_output(self):
        result = _bash(
            BIN_DIR / "gh-create-issue.sh",
            "--title", "Test Issue",
            "--body", "Issue body content",
            "--dry-run",
        )
        assert result.returncode == 0
        assert "dry-run: would create issue" in result.stdout
        assert "Test Issue" in result.stdout
        assert "Issue body content" in result.stdout

    @gh_required
    def test_dry_run_with_labels(self):
        result = _bash(
            BIN_DIR / "gh-create-issue.sh",
            "--title", "Labeled Issue",
            "--body", "Body",
            "--labels", "bug,high-priority",
            "--dry-run",
        )
        assert result.returncode == 0
        assert "bug,high-priority" in result.stdout

    def test_no_args(self):
        result = _bash(BIN_DIR / "gh-create-issue.sh")
        assert result.returncode != 0


# ── create-feature-pr.sh ─────────────────────────────────────────────────────


class TestCreateFeaturePr:
    def test_missing_all_args(self):
        result = _bash(BIN_DIR / "create-feature-pr.sh")
        assert result.returncode != 0

    def test_missing_required_arg(self):
        result = _bash(
            BIN_DIR / "create-feature-pr.sh",
            "--issue", "42",
            "--title", "Test PR",
        )
        assert result.returncode != 0
        assert "Missing required argument" in result.stderr

    def test_unknown_option(self):
        result = _bash(BIN_DIR / "create-feature-pr.sh", "--bogus")
        assert result.returncode != 0

    def test_runs_without_claude_plugin_root_env(self):
        # The script must not depend on $CLAUDE_PLUGIN_ROOT being set in the Bash
        # environment — that variable is only resolved by Claude Code in hooks.json
        # and skill markdown, not exported into tool-invoked commands. We unset it
        # and invoke with a missing-arg path: the script should fail on the missing
        # arg, NOT on "CLAUDE_PLUGIN_ROOT: unbound variable".
        env = {k: v for k, v in os.environ.items() if k != "CLAUDE_PLUGIN_ROOT"}
        result = subprocess.run(
            [_BASH_EXE, _to_msys2_path(BIN_DIR / "create-feature-pr.sh"),
             "--issue", "1", "--title", "x"],
            capture_output=True, text=True, timeout=30, env=env,
        )
        assert "CLAUDE_PLUGIN_ROOT" not in result.stderr
        assert "unbound variable" not in result.stderr
        assert "Missing required argument" in result.stderr


# ── gh-project-status.sh ─────────────────────────────────────────────────────


class TestGhProjectStatus:
    def test_no_args_shows_usage(self):
        result = _bash(BIN_DIR / "gh-project-status.sh")
        assert result.returncode != 0

    def test_missing_config_file_in_repo(self, tmp_path):
        # Script resolves repo root via `git rev-parse --show-toplevel`, not its own
        # location. From inside a git repo with no .github/project.env, it must look
        # at the *repo's* .github/, not the plugin's.
        subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
        result = _bash(BIN_DIR / "gh-project-status.sh", "add", "42", cwd=tmp_path)
        assert result.returncode != 0
        # The error message should reference the repo's .github path
        assert str(tmp_path).replace("\\", "/").lower() in result.stderr.replace("\\", "/").lower() \
            or ".github/project.env" in result.stderr

    def test_outside_git_repo_fails_clearly(self, tmp_path):
        # When invoked from outside any git repo, the script must fail with a clear
        # message rather than silently looking at the plugin's directory.
        result = _bash(BIN_DIR / "gh-project-status.sh", "add", "42", cwd=tmp_path)
        assert result.returncode != 0
        assert "git repository" in result.stderr.lower()


# ── run-python.sh ────────────────────────────────────────────────────────────


class TestRunPython:
    def test_runs_python_command(self):
        result = _bash(HOOKS_DIR / "run-python.sh", "-c", "print(42)")
        assert result.returncode == 0
        assert "42" in result.stdout

    def test_python_version(self):
        result = _bash(HOOKS_DIR / "run-python.sh", "--version")
        assert result.returncode == 0


# ── open-in-editor.sh ────────────────────────────────────────────────────────


class TestOpenInEditor:
    def test_skips_gracefully_without_editor(self):
        # This should exit 0 even when neither windsurf nor code is installed
        result = _bash(HOOKS_DIR / "open-in-editor.sh")
        assert result.returncode == 0
