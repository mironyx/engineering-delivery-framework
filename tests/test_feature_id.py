"""Tests for bin/_feature_id.py and bin/feature-id.py — issue #143.

Covers LLD v3 E3.3 §1.1: resolve_feature_id, issue_reference_lines, the CLI,
consumer failure on invalid backend config, and the PR body on both backends.
"""

from __future__ import annotations

import os
import pathlib
import re
import subprocess
import sys

import pytest

BIN_DIR = pathlib.Path(__file__).resolve().parent.parent / "plugins" / "edf" / "bin"
sys.path.insert(0, str(BIN_DIR))

import _feature_id  # noqa: E402
import _tracker_jira  # noqa: E402
import tracker  # noqa: E402
from _tracker_contract import TrackerError  # noqa: E402

pytestmark = pytest.mark.skipif(sys.platform == "win32", reason="POSIX shell required")

JIRA = {"JIRA_HOST": "https://example.atlassian.net", "JIRA_EMAIL": "d@example.com",
        "JIRA_API_TOKEN": "tok", "JIRA_SPACE": "SCRUM"}


@pytest.fixture
def clean_env(monkeypatch):
    for var in ("EDF_FEATURE_PREFIX", *JIRA, "JIRA_SPACE"):
        monkeypatch.delenv(var, raising=False)


@pytest.fixture
def jira_env(clean_env, monkeypatch):
    for k, v in JIRA.items():
        monkeypatch.setenv(k, v)


def _repo(tmp_path, name="my-repo"):
    repo = tmp_path / name
    repo.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
    return repo


def _env(**extra):
    env = {k: v for k, v in os.environ.items() if k not in ("EDF_FEATURE_PREFIX", *JIRA)}
    env.update(extra)
    return env


def _run(cmd, cwd, env):
    return subprocess.run(cmd, cwd=cwd, env=env, capture_output=True, text=True, timeout=30)


# ── derive_feature_prefix (moved from test_utils.py) ─────────────────────────


class TestDeriveFeaturePrefix:
    def test_from_env(self, monkeypatch):
        monkeypatch.setenv("EDF_FEATURE_PREFIX", "CUSTOM")
        assert _feature_id.derive_feature_prefix(pathlib.Path("/tmp/test-project")) == "CUSTOM"

    def test_from_dotenv(self, tmp_path, monkeypatch):
        monkeypatch.delenv("EDF_FEATURE_PREFIX", raising=False)
        (tmp_path / ".env").write_text("EDF_FEATURE_PREFIX=FROMFILE\n")
        assert _feature_id.derive_feature_prefix(tmp_path) == "FROMFILE"

    def test_derive_from_multi_word_repo(self, monkeypatch):
        monkeypatch.delenv("EDF_FEATURE_PREFIX", raising=False)
        assert _feature_id.derive_feature_prefix(pathlib.Path("/tmp/engineering-delivery-framework")) == "EDF"

    def test_derive_single_word(self, monkeypatch):
        monkeypatch.delenv("EDF_FEATURE_PREFIX", raising=False)
        assert _feature_id.derive_feature_prefix(pathlib.Path("/tmp/myproject")) == "MYPROJECT"


# ── resolve_feature_id ───────────────────────────────────────────────────────


class TestResolveFeatureId:
    def test_jira_returns_key_and_ignores_prefix(self, jira_env, monkeypatch, tmp_path):
        monkeypatch.setenv("EDF_FEATURE_PREFIX", "IGNORED")
        assert _feature_id.resolve_feature_id("SCRUM-42", tmp_path) == "SCRUM-42"

    def test_jira_uppercases_key(self, jira_env, tmp_path):
        assert _feature_id.resolve_feature_id("scrum-42", tmp_path) == "SCRUM-42"

    @pytest.mark.parametrize("ref", ["scrum-42", "SCRUM-42", "Scrum-7"])
    def test_jira_accepts_what_the_backend_accepts(self, ref, jira_env, tmp_path):
        assert _feature_id.resolve_feature_id(ref, tmp_path) == _tracker_jira._parse_ref(ref, "SCRUM")

    @pytest.mark.parametrize("ref", ["87", "#87", "SCRUM", "SCRUM-", "42-SCRUM", "SCRUM-4x", ""])
    def test_jira_rejects_malformed_ref(self, ref, jira_env, tmp_path):
        with pytest.raises(TrackerError, match="invalid issue reference"):
            _feature_id.resolve_feature_id(ref, tmp_path)

    @pytest.mark.parametrize("ref", ["#87", "87"])
    def test_github_prefix_dash_number(self, ref, clean_env, tmp_path):
        (tmp_path / ".env").write_text("EDF_FEATURE_PREFIX=EDF\n")
        assert _feature_id.resolve_feature_id(ref, tmp_path) == "EDF-87"

    def test_github_rejects_jira_key(self, clean_env, tmp_path):
        with pytest.raises(TrackerError):
            _feature_id.resolve_feature_id("SCRUM-42", tmp_path)

    def test_invalid_backend_config_raises(self, clean_env, monkeypatch, tmp_path):
        monkeypatch.setenv("JIRA_HOST", "https://example.atlassian.net")
        with pytest.raises(TrackerError, match="JIRA_EMAIL is missing"):
            _feature_id.resolve_feature_id("SCRUM-1", tmp_path)

    def test_resolver_never_reads_jira_vars(self):
        assert "JIRA_" not in (BIN_DIR / "_feature_id.py").read_text()


class TestIssueReferenceLines:
    def test_jira_one_line_per_ref(self, jira_env, tmp_path):
        assert _feature_id.issue_reference_lines(["SCRUM-42", "scrum-43"], tmp_path) == "Jira: SCRUM-42\nJira: SCRUM-43"

    def test_github_closes_per_ref(self, clean_env, tmp_path):
        assert _feature_id.issue_reference_lines(["87", "#88"], tmp_path) == "Closes #87\nCloses #88"


def test_active_backend_matches_tracker_cli(jira_env, tmp_path):
    assert tracker.active_backend(tmp_path) == "jira"


def test_active_backend_github_by_default(clean_env, tmp_path):
    assert tracker.active_backend(tmp_path) == "github"


def test_no_prefix_env_read_in_bin_outside_resolver():
    offenders = [p.name for p in BIN_DIR.iterdir()
                 if p.is_file() and p.name != "_feature_id.py" and "EDF_FEATURE_PREFIX" in p.read_text(errors="ignore")]
    assert offenders == []


# ── CLI ──────────────────────────────────────────────────────────────────────


class TestCli:
    def test_id_on_jira(self, tmp_path):
        repo = _repo(tmp_path)
        r = _run([sys.executable, str(BIN_DIR / "feature-id.py"), "id", "SCRUM-42"], repo,
                 _env(**JIRA, EDF_FEATURE_PREFIX="IGNORED"))
        assert (r.returncode, r.stdout.strip()) == (0, "SCRUM-42")

    def test_reference_lines_on_github(self, tmp_path):
        repo = _repo(tmp_path)
        r = _run([sys.executable, str(BIN_DIR / "feature-id.py"), "reference-lines", "7", "8"], repo, _env())
        assert (r.returncode, r.stdout) == (0, "Closes #7\nCloses #8\n")

    def test_malformed_ref_one_error_line(self, tmp_path):
        repo = _repo(tmp_path)
        r = _run([sys.executable, str(BIN_DIR / "feature-id.py"), "id", "nope"], repo, _env())
        assert r.returncode == 1 and r.stdout == ""
        assert re.fullmatch(r"Error: [^\n]+\n", r.stderr)


# ── consumers ────────────────────────────────────────────────────────────────

BAD_CONFIG = {"JIRA_HOST": "https://example.atlassian.net"}  # companions missing


class TestConsumerFailure:
    def test_tag_session_exits_1_with_one_error_line(self, tmp_path):
        repo = _repo(tmp_path)
        r = _run([sys.executable, str(BIN_DIR / "tag-session.py"), "SCRUM-1"], repo, _env(**BAD_CONFIG))
        assert r.returncode == 1
        assert re.fullmatch(r"Error: [^\n]+\n", r.stderr)

    def test_append_checkpoint_exits_1_with_one_error_line(self, tmp_path):
        repo = _repo(tmp_path)
        r = _run([sys.executable, str(BIN_DIR / "append-checkpoint.py"), "--issue", "SCRUM-1",
                  "--step", "5", "--note", "x"], repo, _env(**BAD_CONFIG))
        assert r.returncode == 1
        assert re.fullmatch(r"Error: [^\n]+\n", r.stderr)

    def test_create_feature_pr_aborts_before_creating_a_pr(self, tmp_path):
        repo = _repo(tmp_path)
        fake_bin = tmp_path / "bin"
        fake_bin.mkdir()
        marker = tmp_path / "gh-called"
        gh = fake_bin / "gh"
        gh.write_text(f"#!/bin/sh\necho called >> {marker}\n")
        gh.chmod(0o755)
        env = _env(**BAD_CONFIG, PATH=f"{fake_bin}:{os.environ['PATH']}")
        r = _run(["bash", str(BIN_DIR / "create-feature-pr.sh"), "--issue", "SCRUM-1", "--title", "t",
                  "--summary", "s", "--tests-added", "1", "--tests-total", "2"], repo, env)
        assert r.returncode == 1
        assert "Error:" in r.stderr
        assert not marker.exists()


class TestTagSession:
    def _session(self, tmp_path):
        repo = _repo(tmp_path)
        key = str(repo.resolve()).lower().replace("/", "-")
        claude_dir = tmp_path / "home" / ".claude" / "projects" / key
        claude_dir.mkdir(parents=True)
        sid = "11111111-1111-1111-1111-111111111111"
        (claude_dir / f"{sid}.jsonl").write_text("", encoding="utf-8")
        return repo, claude_dir / f"{sid}.jsonl", {"HOME": str(tmp_path / "home"), "CLAUDE_CODE_SESSION_ID": sid}

    def test_jira_tag_uses_key_ignoring_prefix(self, tmp_path):
        repo, jsonl, extra = self._session(tmp_path)
        r = _run([sys.executable, str(BIN_DIR / "tag-session.py"), "SCRUM-42"], repo,
                 _env(**JIRA, **extra, EDF_FEATURE_PREFIX="IGNORED", EDF_FEATURE_PROM_DIR=str(tmp_path / "prom")))
        assert r.returncode == 0, r.stderr
        assert '"customTitle": "SCRUM-42"' in jsonl.read_text()
        assert 'feature_id="SCRUM-42"' in (tmp_path / "prom" / "session_feature.prom").read_text()

    def test_github_tag_uses_prefix_and_number(self, tmp_path):
        repo, jsonl, extra = self._session(tmp_path)
        r = _run([sys.executable, str(BIN_DIR / "tag-session.py"), "87"], repo,
                 _env(**extra, EDF_FEATURE_PREFIX="EDF", EDF_FEATURE_PROM_DIR=str(tmp_path / "prom")))
        assert r.returncode == 0, r.stderr
        assert '"customTitle": "EDF-87"' in jsonl.read_text()


class TestAppendCheckpoint:
    def test_jira_issue_finds_log_by_key(self, tmp_path):
        repo = _repo(tmp_path)
        logs = repo / "docs" / "sessions" / "2026-11"
        logs.mkdir(parents=True)
        log = logs / "2026-11-17-session-1-x-SCRUM-42.md"
        log.write_text("# S\n## Cost checkpoints\n| Step | Timestamp | Cost | Note |\n|---|---|---|---|\n",
                       encoding="utf-8")
        r = _run([sys.executable, str(BIN_DIR / "append-checkpoint.py"), "--issue", "SCRUM-42",
                  "--step", "5", "--note", "ok"], repo,
                 _env(**JIRA, PROM_PORT="1", EDF_FEATURE_PROM_DIR=str(tmp_path / "prom")))
        assert r.returncode == 0, r.stderr
        assert "| 5 |" in log.read_text()


# ── create-feature-pr.sh dry-run bodies ──────────────────────────────────────


def _dry_run(repo, env, *issues):
    args = [a for i in issues for a in ("--issue", i)]
    return _run(["bash", str(BIN_DIR / "create-feature-pr.sh"), *args, "--title", "t", "--summary", "- y",
                 "--tests-added", "1", "--tests-total", "2", "--dry-run"], repo, env)


class TestPrBody:
    def test_jira_body_has_jira_line_and_no_closes(self, tmp_path):
        r = _dry_run(_repo(tmp_path), _env(**JIRA), "SCRUM-42")
        assert r.returncode == 0, r.stderr
        assert "## Issue\nJira: SCRUM-42\n" in r.stdout
        assert "Closes #" not in r.stdout

    def test_github_body_has_closes(self, tmp_path):
        r = _dry_run(_repo(tmp_path), _env(EDF_FEATURE_PREFIX="T"), "5", "6")
        assert r.returncode == 0, r.stderr
        assert "## Issue\nCloses #5\nCloses #6\n" in r.stdout

    def test_pr_prefix_matches_tag_session_derivation(self, tmp_path):
        # Directory name differs from any gh repo name: the PR script must use the
        # main-checkout directory derivation, as tag-session does.
        repo = _repo(tmp_path, "alpha-beta-gamma")
        expected = _run([sys.executable, str(BIN_DIR / "feature-id.py"), "id", "9"], repo, _env()).stdout.strip()
        assert expected == "ABG-9"
