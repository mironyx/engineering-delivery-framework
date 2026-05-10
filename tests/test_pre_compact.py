"""Tests for pre-compact-session-log.py pure functions."""

import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent / "plugins" / "edf" / "bin"))

from importlib import import_module

# The module has side effects (reads stdin on import in main guard), but since
# we're importing it the __name__ != "__main__" guard prevents main() from running.
pcl = import_module("pre-compact-session-log")


class TestRelPath:
    def test_with_project_root(self):
        result = pcl._rel("/home/user/project/src/lib/auth.ts", "/home/user/project")
        assert result == "src/lib/auth.ts"

    def test_without_project_root_finds_marker(self):
        result = pcl._rel("C:\\projects\\myapp\\tests\\unit\\test_auth.ts")
        assert "tests/unit/test_auth.ts" in result

    def test_no_marker_returns_filename(self):
        result = pcl._rel("/tmp/random/file.txt")
        assert result == "file.txt"


class TestTestResult:
    def test_summarizer_pass(self):
        assert pcl._test_result("PASS 5/5 -- 1.2s") == "5 passed"

    def test_summarizer_fail(self):
        # "FAIL 2/5" → total=5, n=2 → "FAIL (3 failed, 2 passed)"
        result = pcl._test_result("FAIL 2/5")
        assert "FAIL" in result
        assert "3 failed" in result
        assert "2 passed" in result

    def test_raw_pytest_pass(self):
        assert pcl._test_result("12 passed") == "12 passed"

    def test_raw_pytest_fail(self):
        result = pcl._test_result("2 failed, 10 passed")
        assert "FAIL" in result and "2 failed" in result

    def test_raw_vitest_pass(self):
        assert pcl._test_result("25 passed") == "25 passed"

    def test_raw_vitest_fail(self):
        result = pcl._test_result("2 failed, 23 passed")
        assert "FAIL" in result and "2 failed" in result

    def test_unknown(self):
        result = pcl._test_result("some random text")
        assert result == "unknown"


class TestTypecheckResult:
    def test_tsc_errors(self):
        result = pcl._typecheck_result("error TS2322: Type 'string' is not assignable to type 'number'. error TS2345: Argument of type 'string' not assignable.")
        assert "2 error(s)" in result

    def test_clean_tsc(self):
        assert pcl._typecheck_result("No errors found.") == "clean"

    def test_mypy_found_errors(self):
        result = pcl._typecheck_result("Found 3 errors")
        assert "3 error(s)" in result

    def test_mypy_clean(self):
        # Found 0 errors → "clean" (special-cased in _typecheck_result)
        assert pcl._typecheck_result("Found 0 errors") == "clean"

    def test_generic_error_match(self):
        result = pcl._typecheck_result("error: some issue\nerror: another issue")
        assert "2 error(s)" in result


class TestGitCommitMsg:
    def test_double_quoted(self):
        result = pcl._git_commit_msg('git commit -m "fix: resolve race condition in auth middleware"')
        assert result == "fix: resolve race condition in auth middleware"

    def test_single_quoted(self):
        result = pcl._git_commit_msg("git commit -m 'feat: add user endpoint'")
        assert result == "feat: add user endpoint"

    def test_truncation(self):
        long_msg = "a" * 120
        assert len(pcl._git_commit_msg(f'git commit -m "{long_msg}"')) == 80

    def test_heredoc(self):
        result = pcl._git_commit_msg("git commit -F -")
        assert result == "(message in heredoc)"


class TestExtractFacts:
    def test_empty_data(self):
        facts = pcl.extract_facts({})
        assert facts["turn_count"] == 0
        assert facts["files"] == {}
        assert facts["git_commits"] == []

    def test_tool_use_tracking(self):
        data = {
            "tool_uses": [
                {"id": "1", "name": "Write", "input": {"file_path": "/proj/src/new.py"}},
                {"id": "2", "name": "Edit", "input": {"file_path": "/proj/src/existing.py"}},
                {"id": "3", "name": "Bash", "input": {"command": "pytest tests/"}},
            ],
            "tool_results": {"3": "12 passed"},
        }
        facts = pcl.extract_facts(data)
        assert "src/new.py" in facts["files"]
        assert facts["files"]["src/new.py"] == "created"
        assert "src/existing.py" in facts["files"]
        assert len(facts["test_runs"]) == 1
        assert facts["test_runs"][0] == "12 passed"

    def test_agent_spawn_tracking(self):
        data = {
            "tool_uses": [
                {"id": "a1", "name": "Agent", "input": {"description": "Run tests"}},
                {"id": "a2", "name": "Agent", "input": {"description": "Code review"}},
            ],
            "tool_results": {},
        }
        facts = pcl.extract_facts(data)
        assert len(facts["agent_spawns"]) == 2
        assert "Run tests" in facts["agent_spawns"]


class TestRenderSection:
    def test_minimal_section(self):
        facts = {}
        section = pcl.render_section(facts, "abc12345-def6-7890-abcd-ef1234567890", "14:30")
        assert "## Compact snapshot" in section
        assert "14:30" in section
        assert "abc12345" in section

    def test_section_with_facts(self):
        facts = {
            "feature_tag": "EDF-55",
            "turn_count": 42,
            "files": {"src/auth.py": "created"},
            "test_runs": ["5 passed"],
            "agent_spawns": ["Run tests"],
        }
        section = pcl.render_section(facts, "abc12345-def6-7890-abcd-ef1234567890", "14:30")
        assert "EDF-55" in section
        assert "src/auth.py" in section
        assert "5 passed" in section


class TestInferProjectRoot:
    def test_finds_common_prefix(self):
        tool_uses = [
            {"name": "Write", "input": {"file_path": "/proj/src/lib/auth.py"}},
            {"name": "Write", "input": {"file_path": "/proj/tests/test_auth.py"}},
        ]
        root = pcl._infer_project_root(tool_uses)
        assert root is not None

    def test_no_markers_returns_none(self):
        tool_uses = [
            {"name": "Write", "input": {"file_path": "/tmp/random.txt"}},
        ]
        root = pcl._infer_project_root(tool_uses)
        assert root is None
