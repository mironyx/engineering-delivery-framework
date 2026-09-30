"""Tests for bin/check-justification.py and bin/changed-lines.py.

check-justification is the mechanical half of pr-review Agent C's
`[unspecified-function]` rule. In FCS-1389, 1382 and 1373 a missing
`Justification:` comment was a review blocker — found only after the PR existed.
"""

import pathlib
import subprocess
import sys

BIN_DIR = pathlib.Path(__file__).resolve().parent.parent / "plugins" / "edf" / "bin"

BASE_SRC = """export function kept(a: number): number {
  return a;
}
"""


def _git(repo, *args):
    subprocess.run(["git", "-c", "user.email=t@t", "-c", "user.name=t", *args],
                   cwd=repo, check=True, capture_output=True)


def _repo(tmp_path):
    repo = tmp_path / "repo"
    (repo / "src").mkdir(parents=True)
    (repo / "tests").mkdir()
    (repo / "docs").mkdir()
    (repo / "src" / "mod.ts").write_text(BASE_SRC, encoding="utf-8")
    (repo / "docs" / "lld.md").write_text("## Design\n`designedHelper(x)` computes the thing.\n", encoding="utf-8")
    _git(repo, "init", "-q", "-b", "main")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-qm", "base")
    _git(repo, "checkout", "-qb", "feat")
    return repo


def _check(repo, lld="docs/lld.md"):
    return subprocess.run(
        [sys.executable, str(BIN_DIR / "check-justification.py"), "--lld", lld, "--base", "main"],
        capture_output=True, text=True, timeout=30, cwd=repo,
    )


def test_flags_new_unjustified_helper_not_in_lld(tmp_path):
    repo = _repo(tmp_path)
    (repo / "src" / "mod.ts").write_text(BASE_SRC + """
function fitListToBudget(xs: string[]): string[] {
  return xs;
}
""", encoding="utf-8")
    result = _check(repo)
    assert result.returncode == 1
    assert "src/mod.ts:5 fitListToBudget" in result.stdout


def test_passes_helper_named_in_lld(tmp_path):
    repo = _repo(tmp_path)
    (repo / "src" / "mod.ts").write_text(BASE_SRC + "\nconst designedHelper = (x: number) => x + 1;\n",
                                         encoding="utf-8")
    result = _check(repo)
    assert result.returncode == 0, result.stdout


def test_passes_helper_with_justification_in_comment_block(tmp_path):
    repo = _repo(tmp_path)
    (repo / "src" / "mod.ts").write_text(BASE_SRC + """
/**
 * Keeps whole items until the budget runs out.
 * Justification: shared by three sections; keeps truncateArtefacts under the complexity gate.
 */
function fitListToBudget(xs: string[]): string[] {
  return xs;
}
""", encoding="utf-8")
    assert _check(repo).returncode == 0


def test_python_docstring_justification_counts(tmp_path):
    repo = _repo(tmp_path)
    (repo / "src" / "tool.py").write_text(
        'def helper(x):\n    """Do it.\n\n    Justification: reused by two call sites.\n    """\n    return x\n',
        encoding="utf-8")
    assert _check(repo).returncode == 0


def test_existing_function_with_changed_signature_is_not_new(tmp_path):
    repo = _repo(tmp_path)
    (repo / "src" / "mod.ts").write_text(BASE_SRC.replace("kept(a: number)", "kept(a: number, b = 0)"),
                                         encoding="utf-8")
    assert _check(repo).returncode == 0


def test_test_files_are_ignored(tmp_path):
    repo = _repo(tmp_path)
    (repo / "tests" / "mod.test.ts").write_text("function makeFixture() { return 1; }\n", encoding="utf-8")
    assert _check(repo).returncode == 0


def test_no_lld_skips(tmp_path):
    repo = _repo(tmp_path)
    (repo / "src" / "mod.ts").write_text(BASE_SRC + "\nfunction anything() {}\n", encoding="utf-8")
    result = _check(repo, lld="none")
    assert result.returncode == 0
    assert "skipped" in result.stdout


def test_changed_lines_reports_added_ranges(tmp_path):
    repo = _repo(tmp_path)
    (repo / "src" / "mod.ts").write_text(BASE_SRC + "\nfunction a() {}\nfunction b() {}\n", encoding="utf-8")
    (repo / "src" / "new.ts").write_text("x\ny\n", encoding="utf-8")
    result = subprocess.run([sys.executable, str(BIN_DIR / "changed-lines.py"), "--base", "main"],
                            capture_output=True, text=True, timeout=30, cwd=repo)
    assert result.returncode == 0
    assert "src/mod.ts: 4-6" in result.stdout
    assert "src/new.ts: 1-2" in result.stdout
