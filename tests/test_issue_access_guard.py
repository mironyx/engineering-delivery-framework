"""Issue-access guard (LLD v3 E3.3 §1.4, I13-I15).

Fails, naming ``path:line``, when issue access (``gh issue``, ``gh project``, ``gh api …/issues``
or the removed shim names) appears under the plugin's skills/agents/bin/starters outside the
GitHub backend.
"""

import pathlib
import re

import pytest

REPO = pathlib.Path(__file__).resolve().parent.parent
PLUGIN = REPO / "plugins" / "edf"
ROOTS = ["skills", "agents", "bin", "starters"]
EXCLUDED = {"bin/_tracker_github.py"}
PATTERNS = [
    r"gh\s+issue\b",
    r"gh\s+project\b",
    r"[\"']gh[\"']\s*,\s*[\"'](issue|project)[\"']",
    r"gh\s+api\b[^\n]*/issues\b",
    r"[\"']gh[\"']\s*,\s*[\"']api[\"'][^\]\n]*/issues\b",
    r"gh-create-issue|gh-project-status|check-epic-checkbox",
]
_COMPILED = [re.compile(p) for p in PATTERNS]
SHIMS = ["bin/gh-create-issue.sh", "bin/gh-project-status.sh", "bin/check-epic-checkbox.py"]


def scan(root: pathlib.Path) -> list[str]:
    """Return ``relpath:line`` for each violating line under ``root``'s scanned roots."""
    hits: list[str] = []
    for sub in ROOTS:
        base = root / sub
        if not base.is_dir():
            continue
        for path in sorted(p for p in base.rglob("*") if p.is_file()):
            rel = path.relative_to(root).as_posix()
            if rel in EXCLUDED or "__pycache__" in path.parts:
                continue
            try:
                text = path.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                continue
            for n, line in enumerate(text.splitlines(), 1):
                if any(rx.search(line) for rx in _COMPILED):
                    hits.append(f"{rel}:{n}")
    return hits


def test_no_issue_access_outside_github_backend() -> None:
    assert scan(PLUGIN) == []


def test_exclusion_list_is_only_the_github_backend() -> None:
    assert EXCLUDED == {"bin/_tracker_github.py"}
    assert (PLUGIN / "bin" / "_tracker_github.py").is_file()


def test_shims_are_gone_and_unreferenced() -> None:
    for rel in SHIMS:
        assert not (PLUGIN / rel).exists(), rel
    for doc in (REPO / "README.md", PLUGIN / "bin" / "tracker.py"):
        text = doc.read_text(encoding="utf-8")
        for name in ("gh-create-issue", "gh-project-status", "check-epic-checkbox"):
            assert name not in text, f"{doc.name} mentions {name}"


VIOLATIONS = {
    "skills/a/SKILL.md": "run gh issue view 5\n",
    "bin/argv.py": 'import x\nsubprocess.run(["gh", "issue", "list"])\n',
    "agents/api.md": "gh api repos/{owner}/{repo}/issues/5\n",
    "starters/scripts/api.py": 'run(["gh", "api", "repos/o/r/issues/5"])\n',
    "bin/proj.sh": "gh project item-list\n",
    "skills/b/SKILL.md": "see gh-create-issue.sh\n",
    "skills/c/SKILL.md": "use gh-project-status.sh\n",
    "skills/d/SKILL.md": "and check-epic-checkbox.py\n",
}
CLEAN = {
    "skills/ok/SKILL.md": "gh pr view 5\ngh api repos/o/r/pulls/5\ngh api repos/o/r/actions/runs\n",
    "bin/ok.py": 'run(["gh", "pr", "view"])\n_gh(["issue", "view"])\n',
    "bin/_tracker_github.py": "gh issue view 5\n",
}


@pytest.mark.parametrize("rel,content", sorted(VIOLATIONS.items()))
def test_each_pattern_is_caught_with_file_and_line(tmp_path, rel, content) -> None:
    for r, c in {**CLEAN, rel: content}.items():
        f = tmp_path / r
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(c, encoding="utf-8")
    line = next(i for i, ln in enumerate(content.splitlines(), 1) if any(rx.search(ln) for rx in _COMPILED))
    assert scan(tmp_path) == [f"{rel}:{line}"]
