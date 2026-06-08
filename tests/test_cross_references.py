"""Validate cross-references between skills, agents, scripts, and hooks configuration."""

import json
import pathlib
import re

import pytest

PLUGIN_ROOT = pathlib.Path(__file__).resolve().parent.parent / "plugins" / "edf"
SKILLS_DIR = PLUGIN_ROOT / "skills"
AGENTS_DIR = PLUGIN_ROOT / "agents"
BIN_DIR = PLUGIN_ROOT / "bin"
HOOKS_DIR = PLUGIN_ROOT / "hooks"


def _parse_frontmatter(text):
    if not text.startswith("---\n"):
        return {}, text
    end = text.find("\n---\n", 4)
    if end == -1:
        return {}, text
    raw = text[4:end]
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

    return data, text[end + 5:]


def _all_skill_names():
    names = set()
    for d in SKILLS_DIR.iterdir():
        if d.is_dir() and not d.name.startswith(".") and d.name != "shared":
            sf = d / "SKILL.md"
            if sf.exists():
                fm, _ = _parse_frontmatter(sf.read_text(encoding="utf-8"))
                names.add(fm.get("name", d.name))
    return names


def _all_agent_names():
    names = set()
    for f in AGENTS_DIR.glob("*.md"):
        fm, _ = _parse_frontmatter(f.read_text(encoding="utf-8"))
        names.add(fm.get("name", f.stem))
    return names


# ── Skill → Agent references ─────────────────────────────────────────────────


def _agent_refs_in_skill(skill_dir):
    """Extract edf:<agent-name> from Launch Agent and subagent_type contexts only.

    Matches only contexts that are unambiguously agent launches — not skill
    references like edf:diag or edf:test.
    """
    skill_file = SKILLS_DIR / skill_dir / "SKILL.md"
    if not skill_file.exists():
        return []
    text = skill_file.read_text(encoding="utf-8")
    refs = set()
    # Launch Agent: edf:<name>  (in code blocks)
    refs.update(re.findall(r'Launch Agent: edf:([\w-]+)', text))
    # Agent({subagent_type: "edf:<name>", ...})  (in Agent() calls)
    refs.update(re.findall(r'subagent_type: "edf:([\w-]+)"', text))
    return refs


class TestSkillAgentReferences:
    """Skills that invoke Agent tool with edf: prefix should reference real agents."""

    def test_feature_core_refers_real_agents(self):
        """feature-core spawns edf:test-author, edf:feature-evaluator, edf:ci-probe."""
        agent_names = _all_agent_names()
        for ref in _agent_refs_in_skill("feature-core"):
            assert ref in agent_names, f"feature-core references unknown agent edf:{ref}"

    def test_pr_review_refers_real_agents(self):
        agent_names = _all_agent_names()
        for ref in _agent_refs_in_skill("pr-review"):
            assert ref in agent_names, f"pr-review references unknown agent edf:{ref}"

    def test_feature_refers_real_agents(self):
        agent_names = _all_agent_names()
        for ref in _agent_refs_in_skill("feature"):
            assert ref in agent_names, f"feature references unknown agent edf:{ref}"


# ── Skill → Script references ────────────────────────────────────────────────


class TestSkillScriptReferences:
    """Skills that reference specific bin/ scripts should reference real files."""

    def test_skills_referencing_bin_scripts(self):
        """Any skill referencing a bin/ script name should reference one that exists."""
        bin_scripts = {f.name for f in BIN_DIR.iterdir() if f.is_file()}
        for d in SKILLS_DIR.iterdir():
            if not d.is_dir() or d.name.startswith(".") or d.name == "shared":
                continue
            sf = d / "SKILL.md"
            if not sf.exists():
                continue
            text = sf.read_text(encoding="utf-8")
            # Find references like bin/script-name.sh or bin/script-name.py
            for match in re.finditer(r'bin/([\w.-]+)', text):
                script = match.group(1)
                assert script in bin_scripts, (
                    f"{d.name}/SKILL.md references bin/{script} which does not exist"
                )


# ── Hooks configuration ──────────────────────────────────────────────────────


class TestHooksConfig:
    def test_hooks_json_valid(self):
        hooks_json = PLUGIN_ROOT / "hooks" / "hooks.json"
        data = json.loads(hooks_json.read_text())
        assert "hooks" in data
        assert "PostToolUse" in data["hooks"]
        assert "PreCompact" in data["hooks"]

    def test_post_tool_use_hooks_reference_real_scripts(self):
        hooks_json = PLUGIN_ROOT / "hooks" / "hooks.json"
        data = json.loads(hooks_json.read_text())
        matchers = data["hooks"]["PostToolUse"]
        for matcher in matchers:
            for hook in matcher.get("hooks", []):
                cmd = hook.get("command", "")
                # Extract the script path after ${CLAUDE_PLUGIN_ROOT}/hooks/
                m = re.search(r'\$\{CLAUDE_PLUGIN_ROOT\}/hooks/([\w.-]+)', cmd)
                if m:
                    script = m.group(1)
                    assert (HOOKS_DIR / script).exists(), (
                        f"PostToolUse hook references hooks/{script} which does not exist"
                    )

    def test_precompact_hooks_reference_real_scripts(self):
        hooks_json = PLUGIN_ROOT / "hooks" / "hooks.json"
        data = json.loads(hooks_json.read_text())
        for entry in data["hooks"].get("PreCompact", []):
            for hook in entry.get("hooks", []):
                cmd = hook.get("command", "")
                if "bin/" in cmd:
                    m = re.search(r'bin/([\w.-]+)', cmd)
                    if m:
                        script = m.group(1)
                        assert (BIN_DIR / script).exists(), (
                            f"PreCompact hook references bin/{script} which does not exist"
                        )

    def test_timeouts_are_numeric(self):
        hooks_json = PLUGIN_ROOT / "hooks" / "hooks.json"
        data = json.loads(hooks_json.read_text())
        for section in data["hooks"].values():
            for matcher in section:
                for hook in matcher.get("hooks", []):
                    timeout = hook.get("timeout", 0)
                    assert isinstance(timeout, (int, float))
                    assert timeout > 0
