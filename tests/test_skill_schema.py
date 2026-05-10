"""Validate all SKILL.md files have correct YAML frontmatter with required fields."""

import pathlib
import re

import pytest

PLUGIN_ROOT = pathlib.Path(__file__).resolve().parent.parent / "plugins" / "edf"
SKILLS_DIR = PLUGIN_ROOT / "skills"


def _parse_frontmatter(text):
    """Parse YAML frontmatter from markdown. Returns (dict, body) or (None, text)."""
    if not text.startswith("---\n"):
        return None, text
    end = text.find("\n---\n", 4)
    if end == -1:
        return None, text
    raw = text[4:end]
    body = text[end + 5:]
    # Minimal YAML parser for simple key: value and key: > (folded block scalar)
    data = {}
    current_key = None
    current_value_lines = []
    in_folded = False

    for line in raw.splitlines():
        if in_folded:
            # In a folded block scalar: accumulate lines until non-indented
            if line and (line[0] == ' ' or line[0] == '\t'):
                current_value_lines.append(line.strip())
                continue
            else:
                data[current_key] = ' '.join(current_value_lines).strip()
                current_key = None
                current_value_lines = []
                in_folded = False

        if ':' in line:
            # Could be "key: value" or "key: >" (folded scalar start)
            idx = line.index(':')
            key = line[:idx].strip()
            value = line[idx + 1:].strip()
            if value == '>':
                current_key = key
                current_value_lines = []
                in_folded = True
            else:
                data[key] = value
        elif current_key:
            current_value_lines.append(line.strip())

    if in_folded and current_key:
        data[current_key] = ' '.join(current_value_lines).strip()

    return data, body


def _find_all_skill_files():
    skills = []
    for d in SKILLS_DIR.iterdir():
        if d.is_dir() and not d.name.startswith("."):
            skill_file = d / "SKILL.md"
            if skill_file.exists():
                skills.append(skill_file)
    return sorted(skills)


ALL_SKILLS = _find_all_skill_files()

REQUIRED_SKILL_FIELDS = ["name", "description", "allowed-tools"]


@pytest.mark.parametrize("skill_path", ALL_SKILLS, ids=lambda p: p.parent.name)
class TestSkillSchema:
    def test_has_frontmatter(self, skill_path):
        text = skill_path.read_text(encoding="utf-8")
        assert text.startswith("---\n"), f"Missing YAML frontmatter in {skill_path.parent.name}"

    def test_valid_frontmatter(self, skill_path):
        text = skill_path.read_text(encoding="utf-8")
        frontmatter, _ = _parse_frontmatter(text)
        assert frontmatter is not None, f"Could not parse frontmatter in {skill_path.parent.name}"
        assert len(frontmatter) > 0, f"Empty frontmatter in {skill_path.parent.name}"

    def test_has_required_fields(self, skill_path):
        text = skill_path.read_text(encoding="utf-8")
        frontmatter, _ = _parse_frontmatter(text)
        for field in REQUIRED_SKILL_FIELDS:
            assert field in frontmatter, f"Missing '{field}' in {skill_path.parent.name}/SKILL.md"

    def test_name_matches_directory(self, skill_path):
        text = skill_path.read_text(encoding="utf-8")
        frontmatter, _ = _parse_frontmatter(text)
        if frontmatter and "name" in frontmatter:
            assert frontmatter["name"] == skill_path.parent.name, (
                f"name '{frontmatter['name']}' does not match directory '{skill_path.parent.name}'"
            )

    def test_has_content_after_frontmatter(self, skill_path):
        text = skill_path.read_text(encoding="utf-8")
        _, body = _parse_frontmatter(text)
        assert body.strip(), f"No content after frontmatter in {skill_path.parent.name}"


def test_all_skill_directories_have_skill_md():
    for d in sorted(SKILLS_DIR.iterdir()):
        if d.is_dir() and not d.name.startswith(".") and d.name != "shared":
            assert (d / "SKILL.md").exists(), f"Missing SKILL.md in {d.name}/"
