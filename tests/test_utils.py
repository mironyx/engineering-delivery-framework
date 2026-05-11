"""Tests for utility functions across the bin/ scripts."""

import json
import pathlib
import subprocess
import sys
import tempfile

import pytest

BIN_DIR = pathlib.Path(__file__).resolve().parent.parent / "plugins" / "edf" / "bin"

sys.path.insert(0, str(BIN_DIR))

# Import modules (main guard prevents side effects)
tag_session = __import__("tag-session")
extract_session_id = __import__("extract-session-id")
query_feature_cost = __import__("query-feature-cost")
update_coverage_manifest = __import__("update-coverage-manifest")
check_epic_checkbox = __import__("check-epic-checkbox")
edf_env = __import__("_edf_env")


# ── derive_project_key ───────────────────────────────────────────────────────


class TestDeriveProjectKey:
    def test_windows_path(self):
        key = tag_session.derive_project_key(pathlib.Path("C:\\projects\\my-project"))
        assert key == "c--projects-my-project"

    def test_wsl_path(self):
        key = tag_session.derive_project_key(pathlib.Path("/home/user/projects/my-project"))
        assert key == "-home-user-projects-my-project"

    def test_no_drive_letter(self):
        key = tag_session.derive_project_key(pathlib.Path("/mnt/c/projects/app"))
        assert key == "-mnt-c-projects-app"


# ── derive_feature_prefix ────────────────────────────────────────────────────


class TestDeriveFeaturePrefix:
    def test_from_env(self, monkeypatch):
        monkeypatch.setenv("EDF_FEATURE_PREFIX", "CUSTOM")
        root = pathlib.Path("/tmp/test-project")
        prefix = tag_session.derive_feature_prefix(root)
        assert prefix == "CUSTOM"

    def test_from_dotenv(self, tmp_path, monkeypatch):
        monkeypatch.delenv("EDF_FEATURE_PREFIX", raising=False)
        (tmp_path / ".env").write_text("EDF_FEATURE_PREFIX=FROMFILE\n")
        prefix = tag_session.derive_feature_prefix(tmp_path)
        assert prefix == "FROMFILE"

    def test_derive_from_multi_word_repo(self, monkeypatch):
        monkeypatch.delenv("EDF_FEATURE_PREFIX", raising=False)
        root = pathlib.Path("/tmp/engineering-delivery-framework")
        prefix = tag_session.derive_feature_prefix(root)
        assert prefix == "EDF"

    def test_derive_single_word(self, monkeypatch):
        monkeypatch.delenv("EDF_FEATURE_PREFIX", raising=False)
        root = pathlib.Path("/tmp/myproject")
        prefix = tag_session.derive_feature_prefix(root)
        assert prefix == "MYPROJECT"


# ── _edf_env.read_dotenv ─────────────────────────────────────────────────────
# (moved from tag-session._read_dotenv to shared _edf_env module)


class TestReadDotenv:
    def test_simple_key_value(self, tmp_path):
        env_file = tmp_path / ".env"
        env_file.write_text('KEY=value\nANOTHER=123\n')
        result = edf_env.read_dotenv(tmp_path)
        assert result == {"KEY": "value", "ANOTHER": "123"}

    def test_skips_comments_and_blanks(self, tmp_path):
        env_file = tmp_path / ".env"
        env_file.write_text('# comment\nKEY=value\n\nOTHER=thing\n')
        result = edf_env.read_dotenv(tmp_path)
        assert result == {"KEY": "value", "OTHER": "thing"}

    def test_strips_quotes(self, tmp_path):
        env_file = tmp_path / ".env"
        env_file.write_text('KEY="quoted value"\n')
        result = edf_env.read_dotenv(tmp_path)
        assert result == {"KEY": "quoted value"}

    def test_missing_file(self, tmp_path):
        result = edf_env.read_dotenv(tmp_path)
        assert result == {}


# ── extract-session-id ───────────────────────────────────────────────────────


class TestExtractSessionId:
    def test_from_pr_body(self):
        body = "Some text\n<!-- claude-session-id: abc-def-123 -->\nMore text"
        sid = extract_session_id._extract_from_pr_body(body)
        assert sid == "abc-def-123"

    def test_no_session_in_body(self):
        sid = extract_session_id._extract_from_pr_body("Just some PR description")
        assert sid == ""


# ── query-feature-cost ───────────────────────────────────────────────────────


class TestFormatDuration:
    def test_minutes_only(self):
        assert query_feature_cost.format_duration(120) == "2 min"

    def test_hours_and_minutes(self):
        result = query_feature_cost.format_duration(5400)
        assert "1h" in result and "30min" in result

    def test_zero(self):
        assert query_feature_cost.format_duration(0) == "0 min"


# ── update-coverage-manifest ─────────────────────────────────────────────────


class TestUpdateCoverageManifest:
    def test_extract_epic_slug(self, monkeypatch):
        monkeypatch.setattr("sys.stdin", __import__("io").StringIO("ref: lld-my-slug-v2-some-feature.md"))
        slug = update_coverage_manifest.extract_epic_slug()
        # Regex lld-([a-z0-9-]+)-[a-z0-9-]+\.md greedily captures "my-slug-v2-some"
        assert "my-slug" in slug

    def test_extract_no_match(self, monkeypatch):
        monkeypatch.setattr("sys.stdin", __import__("io").StringIO("No slug here"))
        slug = update_coverage_manifest.extract_epic_slug()
        assert slug == ""


# ── check-epic-checkbox ──────────────────────────────────────────────────────


class TestCheckEpicCheckbox:
    def test_extract_parent_epic(self):
        body = "## Summary\n## Parent epic\n\n#42\n\nSome notes"
        epic = check_epic_checkbox._extract_parent_epic(body)
        assert epic == "42"

    def test_no_epic(self):
        body = "## Summary\nNo parent epic here"
        epic = check_epic_checkbox._extract_parent_epic(body)
        assert epic == ""

    def test_tick_checkbox(self):
        body = "- [ ] #55 Fix login bug\n- [ ] #56 Add tests"
        updated = check_epic_checkbox._tick_checkbox(body, "55")
        assert "- [x] #55 Fix login bug" in updated
        assert "- [ ] #56 Add tests" in updated

    def test_tick_already_ticked(self):
        body = "- [x] #55 Fix login bug"
        updated = check_epic_checkbox._tick_checkbox(body, "55")
        assert updated == body  # No change needed
