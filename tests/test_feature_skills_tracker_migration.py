"""Issue #149: feature, feature-core, feature-end, feature-team call the tracker script."""

import pathlib
import re

import pytest

SKILLS = pathlib.Path(__file__).resolve().parent.parent / "plugins" / "edf" / "skills"
NAMES = ["feature", "feature-core", "feature-end", "feature-team"]
FILES = [SKILLS / n / f for n in NAMES for f in ("SKILL.md", "flowchart.md")]
OLD = re.compile(
    r"gh issue|gh project|gh-project-status|gh-create-issue|check-epic-checkbox|EDF_FEATURE_PREFIX"
)


def _text(name):
    return (SKILLS / name / "SKILL.md").read_text()


@pytest.mark.parametrize("path", FILES, ids=lambda p: f"{p.parent.name}/{p.name}")
def test_no_issue_access_patterns(path):
    assert not OLD.findall(path.read_text())


def test_feature_picks_first_todo_task_and_stops_when_empty():
    text = _text("feature")
    assert "tracker.py list --status todo --label kind:task" in text
    assert text.index("No Todo items") < text.index("git checkout -b feat/")


def test_feature_end_closes_once_after_merge_success():
    text = _text("feature-end")
    assert text.count("tracker.py close") == 1
    assert text.index("tracker.py close") > text.index("gh pr merge")


def test_feature_team_epic_reads_remaining_from_epic_progress():
    assert "epic-progress.py <ref> --remaining" in _text("feature-team")


def test_feature_core_derives_feature_id_via_resolver():
    assert "feature-id.py id" in _text("feature-core")
