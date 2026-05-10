"""Validate all agent .md files have correct YAML frontmatter with required fields."""

import pathlib
import re

import pytest

PLUGIN_ROOT = pathlib.Path(__file__).resolve().parent.parent / "plugins" / "edf"
AGENTS_DIR = PLUGIN_ROOT / "agents"

# Valid tool names for agent definitions
VALID_AGENT_TOOLS = {"Read", "Write", "Edit", "MultiEdit", "Bash", "Glob", "Grep",
                     "Agent", "Skill", "TodoWrite", "NotebookRead", "NotebookEdit",
                     "WebFetch", "WebSearch", "TaskOutput", "TaskStop",
                     "AskUserQuestion", "ExitPlanMode", "EnterPlanMode",
                     "CronCreate", "CronDelete", "CronList",
                     "LSP", "Monitor", "BashOutput", "KillShell",
                     "mcp__plugin_playwright_playwright__*"}

VALID_MODELS = {"haiku", "sonnet", "opus"}

REQUIRED_AGENT_FIELDS = ["name", "description", "tools", "model"]


def _parse_frontmatter(text):
    """Parse YAML frontmatter from markdown. Returns (dict, body) or (None, text)."""
    if not text.startswith("---\n"):
        return None, text
    end = text.find("\n---\n", 4)
    if end == -1:
        return None, text
    raw = text[4:end]
    body = text[end + 5:]
    data = {}
    current_key = None
    current_value_lines = []
    in_folded = False

    for line in raw.splitlines():
        if in_folded:
            if line and (line[0] == ' ' or line[0] == '\t'):
                current_value_lines.append(line.strip())
                continue
            else:
                data[current_key] = ' '.join(current_value_lines).strip()
                current_key = None
                current_value_lines = []
                in_folded = False

        if ':' in line:
            idx = line.index(':')
            key = line[:idx].strip()
            value = line[idx + 1:].strip()
            if value == '>':
                current_key = key
                current_value_lines = []
                in_folded = True
            else:
                data[key] = value

    if in_folded and current_key:
        data[current_key] = ' '.join(current_value_lines).strip()

    return data, body


def _find_all_agent_files():
    agents = []
    for f in sorted(AGENTS_DIR.glob("*.md")):
        agents.append(f)
    return agents


ALL_AGENTS = _find_all_agent_files()


@pytest.mark.parametrize("agent_path", ALL_AGENTS, ids=lambda p: p.stem)
class TestAgentSchema:
    def test_has_frontmatter(self, agent_path):
        text = agent_path.read_text(encoding="utf-8")
        assert text.startswith("---\n"), f"Missing YAML frontmatter in {agent_path.stem}"

    def test_valid_frontmatter(self, agent_path):
        text = agent_path.read_text(encoding="utf-8")
        frontmatter, _ = _parse_frontmatter(text)
        assert frontmatter is not None, f"Could not parse frontmatter in {agent_path.stem}"
        assert len(frontmatter) > 0, f"Empty frontmatter in {agent_path.stem}"

    def test_has_required_fields(self, agent_path):
        text = agent_path.read_text(encoding="utf-8")
        frontmatter, _ = _parse_frontmatter(text)
        for field in REQUIRED_AGENT_FIELDS:
            assert field in frontmatter, f"Missing '{field}' in {agent_path.stem}"

    def test_name_matches_filename(self, agent_path):
        text = agent_path.read_text(encoding="utf-8")
        frontmatter, _ = _parse_frontmatter(text)
        if frontmatter and "name" in frontmatter:
            assert frontmatter["name"] == agent_path.stem, (
                f"name '{frontmatter['name']}' does not match filename '{agent_path.stem}'"
            )

    def test_valid_model(self, agent_path):
        text = agent_path.read_text(encoding="utf-8")
        frontmatter, _ = _parse_frontmatter(text)
        if frontmatter and "model" in frontmatter:
            assert frontmatter["model"] in VALID_MODELS, (
                f"Invalid model '{frontmatter['model']}' in {agent_path.stem}"
            )

    def test_tools_not_empty(self, agent_path):
        text = agent_path.read_text(encoding="utf-8")
        frontmatter, _ = _parse_frontmatter(text)
        if frontmatter and "tools" in frontmatter:
            tools = [t.strip() for t in frontmatter["tools"].split(",")]
            assert len(tools) > 0, f"tools is empty in {agent_path.stem}"

    def test_has_content_after_frontmatter(self, agent_path):
        text = agent_path.read_text(encoding="utf-8")
        _, body = _parse_frontmatter(text)
        assert body.strip(), f"No content after frontmatter in {agent_path.stem}"
