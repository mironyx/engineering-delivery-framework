"""Tests for _edf_env shared helpers (.env reading, env precedence, prom_dir)."""

import pathlib
import sys

import pytest

sys.path.insert(
    0,
    str(pathlib.Path(__file__).resolve().parent.parent / "plugins" / "edf" / "bin"),
)

import _edf_env


@pytest.fixture
def repo(tmp_path):
    """A throwaway repo root for .env tests."""
    return tmp_path


class TestReadDotenv:
    def test_missing_file_returns_empty(self, repo):
        assert _edf_env.read_dotenv(repo) == {}

    def test_simple_pairs(self, repo):
        (repo / ".env").write_text("FOO=bar\nBAZ=qux\n", encoding="utf-8")
        assert _edf_env.read_dotenv(repo) == {"FOO": "bar", "BAZ": "qux"}

    def test_skips_comments_and_blanks(self, repo):
        (repo / ".env").write_text(
            "# a comment\n\nFOO=bar\n   # indented comment\nBAZ=qux\n",
            encoding="utf-8",
        )
        assert _edf_env.read_dotenv(repo) == {"FOO": "bar", "BAZ": "qux"}

    def test_strips_quotes(self, repo):
        (repo / ".env").write_text('FOO="quoted"\nBAR=\'single\'\n', encoding="utf-8")
        assert _edf_env.read_dotenv(repo) == {"FOO": "quoted", "BAR": "single"}

    def test_lines_without_equals_ignored(self, repo):
        (repo / ".env").write_text("not_a_pair\nFOO=bar\n", encoding="utf-8")
        assert _edf_env.read_dotenv(repo) == {"FOO": "bar"}


class TestResolve:
    def test_env_takes_precedence(self, repo, monkeypatch):
        (repo / ".env").write_text("FOO=from_dotenv\n", encoding="utf-8")
        monkeypatch.setenv("FOO", "from_env")
        assert _edf_env.resolve("FOO", repo) == "from_env"

    def test_falls_back_to_dotenv(self, repo, monkeypatch):
        (repo / ".env").write_text("FOO=from_dotenv\n", encoding="utf-8")
        monkeypatch.delenv("FOO", raising=False)
        assert _edf_env.resolve("FOO", repo) == "from_dotenv"

    def test_missing_returns_none(self, repo, monkeypatch):
        monkeypatch.delenv("FOO", raising=False)
        assert _edf_env.resolve("FOO", repo) is None

    def test_empty_env_falls_through_to_dotenv(self, repo, monkeypatch):
        (repo / ".env").write_text("FOO=from_dotenv\n", encoding="utf-8")
        monkeypatch.setenv("FOO", "")
        assert _edf_env.resolve("FOO", repo) == "from_dotenv"


class TestPromDir:
    def test_default_under_repo(self, repo, monkeypatch):
        monkeypatch.delenv("EDF_FEATURE_PROM_DIR", raising=False)
        assert _edf_env.prom_dir(repo) == repo / "monitoring" / "textfile_collector"

    def test_env_override(self, repo, monkeypatch, tmp_path):
        override = tmp_path / "custom"
        monkeypatch.setenv("EDF_FEATURE_PROM_DIR", str(override))
        assert _edf_env.prom_dir(repo) == override

    def test_dotenv_override(self, repo, monkeypatch, tmp_path):
        override = tmp_path / "from_dotenv"
        (repo / ".env").write_text(
            f"EDF_FEATURE_PROM_DIR={override}\n", encoding="utf-8"
        )
        monkeypatch.delenv("EDF_FEATURE_PROM_DIR", raising=False)
        assert _edf_env.prom_dir(repo) == override
