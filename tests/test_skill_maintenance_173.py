"""Issue #173 — skill maintenance: Step 9 checkpoint, lld-sync check, diag sonar params,
HLD reference, dead agent, template fence.

Item 1 is a script contract (bin/check-checkpoints.py gains `--stage pr|end`; the agreed
design keeps REQUIRED at 4bF,6b for the PR gate and adds 9 only for feature-end's audit).
Items 2-6 are skill-prose contracts: keyword/ordering checks over bounded section slices,
not exact sentences, so wording edits during review do not break them.
"""

from __future__ import annotations

import importlib.util
import json
import pathlib
import re
import subprocess
import sys

import pytest

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
PLUGIN_ROOT = REPO_ROOT / "plugins" / "edf"
SKILLS = PLUGIN_ROOT / "skills"
AGENTS = PLUGIN_ROOT / "agents"
BIN_DIR = PLUGIN_ROOT / "bin"
SCRIPT = BIN_DIR / "check-checkpoints.py"
_I = re.IGNORECASE

sys.path.insert(0, str(BIN_DIR))


def _load_cc():
    spec = importlib.util.spec_from_file_location("check_checkpoints_173", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


cc = _load_cc()


def _read(skill: str, name: str = "SKILL.md") -> str:
    return (SKILLS / skill / name).read_text(encoding="utf-8")


def _between(text: str, start: str, end: str) -> str:
    """Slice from the `start` regex to the next `end` regex after it."""
    m = re.search(start, text)
    assert m, f"no section matching {start!r}"
    rest = text[m.start():]
    e = re.search(end, rest[1:])
    assert e, f"section {start!r} has no terminator {end!r}"
    return rest[: e.start() + 1]


# =========================================================================== Item 1
# Step 9 checkpoint: script `--stage end` requires row 9; feature-core records it
# before triage; feature-end's audit passes `--stage end`.

HEADER = (
    "| Step | Timestamp | Cost (cumulative) | Tokens (cumulative) | Note |\n"
    "|------|-----------|--------------------|----------------------|------|\n"
)


def _log(pressure: str | None, steps: list[str]) -> str:
    text = "# Session log — EDF-173\n\n"
    if pressure is not None:
        text += f"- **Pressure:** {pressure} — ~40 src lines\n"
    text += "\n## Cost checkpoints\n" + HEADER
    # Ten minutes apart: no bulk signature.
    for i, step in enumerate(steps):
        text += f"| {step} | 2026-11-23T{7 + i // 6:02d}:{(i % 6) * 10:02d}:00Z | $1.00 | 1 in / 2 out | n |\n"
    text += "\n## Concerns & Deferred Items\n- none\n"
    return text


def _run(log_path: pathlib.Path, *extra: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT), "--session-log", str(log_path), *extra],
        capture_output=True, text=True, timeout=30, check=False,
    )


def _write(tmp_path: pathlib.Path, text: str) -> pathlib.Path:
    path = tmp_path / "2026-11-23-session-1-x-EDF-173.md"
    path.write_text(text, encoding="utf-8")
    return path


class TestMissingStepsStage173:
    @pytest.mark.parametrize("tier", ["standard", "heavy", None])
    def test_173_end_stage_reports_4bF_6b_9_in_order(self, tier):
        assert cc.missing_steps(tier, ["3c", "5"], stage="end") == ["4bF", "6b", "9"]

    @pytest.mark.parametrize("tier", ["standard", "heavy"])
    def test_173_end_stage_reports_only_9_when_pr_rows_present(self, tier):
        assert cc.missing_steps(tier, ["4bF", "6b", "8"], stage="end") == ["9"]

    def test_173_end_stage_nothing_missing_when_9_present(self):
        assert cc.missing_steps("standard", ["4bF", "6b", "8", "9"], stage="end") == []

    def test_173_pr_stage_does_not_require_9(self):
        assert cc.missing_steps("standard", ["4bF", "6b"], stage="pr") == []
        assert cc.missing_steps("heavy", ["4bF", "6b"]) == []  # default stage is pr

    @pytest.mark.parametrize("stage", ["pr", "end"])
    def test_173_light_never_missing_at_any_stage(self, stage):
        assert cc.missing_steps("light", [], stage=stage) == []

    def test_173_required_tuple_is_unchanged_for_the_pr_gate(self):
        # Agreed deviation: 9 is NOT added to the global REQUIRED.
        assert tuple(cc.REQUIRED) == ("4bF", "6b")


class TestCliStage173:
    def test_173_cli_stage_end_missing_9_exits_1(self, tmp_path):
        log = _write(tmp_path, _log("standard", ["3c", "4bF", "5", "6", "6b", "8"]))
        result = _run(log, "--stage", "end")
        assert result.returncode == 1, result.stderr
        assert "missing: 9" in result.stdout
        assert "checkpoints: ok" not in result.stdout

    def test_173_cli_stage_end_all_missing_listed_in_order(self, tmp_path):
        log = _write(tmp_path, _log("heavy", ["3c", "5"]))
        result = _run(log, "--stage", "end")
        assert result.returncode == 1, result.stderr
        assert "missing: 4bF,6b,9" in result.stdout

    def test_173_cli_stage_end_complete_log_ok(self, tmp_path):
        log = _write(tmp_path, _log("standard", ["3c", "4bF", "5", "6", "6b", "8", "9"]))
        result = _run(log, "--stage", "end")
        assert result.returncode == 0, result.stderr
        assert result.stdout.strip() == "checkpoints: ok"

    def test_173_cli_default_stage_does_not_require_9(self, tmp_path):
        log = _write(tmp_path, _log("standard", ["3c", "4bF", "5", "6", "6b", "8"]))
        for extra in ((), ("--stage", "pr")):
            result = _run(log, *extra)
            assert result.returncode == 0, (extra, result.stdout, result.stderr)
            assert result.stdout.strip() == "checkpoints: ok"

    def test_173_cli_stage_end_light_is_ok(self, tmp_path):
        log = _write(tmp_path, _log("light", ["3c"]))
        result = _run(log, "--stage", "end")
        assert result.returncode == 0, result.stderr


def _feature_core_step9() -> str:
    return _between(_read("feature-core"), r"\n### Step 9:", r"\n### Step 10")


def test_173_feature_core_step9_checkpoint_runs_after_review_before_triage():
    step9 = _feature_core_step9()
    review = re.search(r"edf:pr-review", step9)
    checkpoint = re.search(r"append-checkpoint\.py[\s\\]*--step\s+\"?9\"?", step9)
    triage = re.search(r"Triage each finding", step9, _I)
    assert review and checkpoint and triage, "Step 9 must have pr-review, a step-9 checkpoint and triage"
    assert review.start() < checkpoint.start() < triage.start(), (
        "the step-9 checkpoint must be appended right after edf:pr-review returns, before triage"
    )


def test_173_feature_core_step9_has_exactly_one_step9_checkpoint():
    step9 = _feature_core_step9()
    calls = re.findall(r"append-checkpoint\.py[\s\\]*--step\s+\"?9\"?(?!\w)", step9)
    assert len(calls) == 1, f"expected one step-9 checkpoint call, found {len(calls)}"
    assert not re.search(r"Once review is resolved[^\n]*append a cost checkpoint", step9, _I), (
        "the old conditional 'once review is resolved' checkpoint must be gone"
    )


def test_173_feature_core_step8_gate_stays_pr_stage():
    step8 = _between(_read("feature-core"), r"\n### Step 8:", r"\n### Step 8b|\n### Step 9")
    calls = re.findall(r"check-checkpoints\.py[^\n]*", step8)
    assert calls, "feature-core Step 8 must still run check-checkpoints.py"
    for call in calls:
        assert "--stage end" not in call, "the pre-PR gate must not require row 9"


def test_173_feature_end_checkpoint_audit_passes_stage_end():
    text = _read("feature-end")
    calls = re.findall(r"check-checkpoints\.py[^\n]*", text)
    assert calls, "feature-end must run check-checkpoints.py"
    assert all(re.search(r"--stage\s+end\b", c) for c in calls), (
        "feature-end's checkpoint audit must pass --stage end"
    )


def test_173_feature_core_flowchart_checkpoint_before_triage():
    chart = _read("feature-core", "flowchart.md")
    cp = re.search(r"S9_CP\[[^\]]*step 9", chart, _I)
    triage = re.search(r"S9_T\[", chart)
    assert cp and triage, "flowchart must define S9_CP (step 9 checkpoint) and S9_T (triage)"
    assert re.search(r"S9\s*-->[^\n]*S9_CP", chart), "flowchart: S9 must lead straight to S9_CP"
    assert re.search(r"S9_CP\s*-->[^\n]*S9_T\b", chart), "flowchart: S9_CP must lead to triage"


# =========================================================================== Item 2
# feature-team Step 7 checks every task's session log for `## LLD Sync report`.


def _feature_team_step7() -> str:
    return _between(_read("feature-team"), r"\n### Step 7:", r"\n### Step 8")


def test_173_feature_team_step7_checks_lld_sync_report_heading():
    step7 = _feature_team_step7()
    assert "## LLD Sync report" in step7, "Step 7 must look for the `## LLD Sync report` heading"
    assert re.search(r"session log", step7, _I), "the check reads each task's session log"


def test_173_feature_team_step7_runs_lld_sync_for_tasks_lacking_it():
    step7 = _feature_team_step7()
    assert re.search(r"edf:lld-sync", step7), "Step 7 must run edf:lld-sync for tasks lacking the report"
    assert re.search(r"\b(lack|missing|without|no `?## LLD Sync|don'?t|do not)\b", step7, _I), (
        "Step 7 must name the tasks whose log lacks the report"
    )


def test_173_feature_team_step7_lld_sync_check_before_epic_close():
    step7 = _feature_team_step7()
    check = re.search(r"edf:lld-sync", step7)
    close = re.search(r"tracker\.py close", step7)
    assert check and close, "Step 7 must have the lld-sync check and the epic close"
    assert check.start() < close.start(), (
        "the lld-sync check must run before the epic is reported done/closed"
    )


def test_173_feature_team_flowchart_mentions_lld_sync_check():
    chart = _read("feature-team", "flowchart.md")
    s7_area = _between(chart, r"S7\[", r"S8\[")
    assert re.search(r"LLD Sync|lld-sync", s7_area, _I), "feature-team flowchart S7 must show the lld-sync check"


# =========================================================================== Item 3
# /diag sonar uses the real analyze_code_snippet schema and skips on unmounted paths.


def _diag_sonar() -> str:
    return _between(_read("diag"), r"\n3\. \*\*SonarQube MCP analysis", r"\n4\. \*\*Diagnostics-exporter")


def test_173_diag_has_no_fileContent_parameter():
    assert "fileContent" not in _read("diag"), "fileContent is not in the analyze_code_snippet schema"


def test_173_diag_snippet_uses_filePath_language_scope():
    sonar = _diag_sonar()
    m = re.search(r"analyze_code_snippet`", sonar)
    assert m, "sonar section must describe analyze_code_snippet"
    bullet = sonar[m.start(): m.start() + 900]
    bullet = re.split(r"\n\s*- `mcp__sonarqube__run_advanced", bullet)[0]
    for param in ("filePath", "language", "scope"):
        assert f"`{param}`" in bullet, f"analyze_code_snippet must be described with `{param}`"
    assert re.search(r"(project|repo)[- ]?(root[- ])?relative|relative to the (project|repo)", bullet, _I), (
        "filePath must be described as project-relative"
    )


def test_173_diag_could_not_read_file_is_skipped_with_mount_reason():
    sonar = _diag_sonar()
    m = re.search(r"Could not read file", sonar)
    assert m, "sonar section must handle the `Could not read file` error"
    window = sonar[max(0, m.start() - 600): m.end() + 600]
    assert re.search(r"SonarQube: skipped", window), "Could not read file must emit the SonarQube: skipped line"
    assert re.search(r"mount", window, _I), "the skip reason must name the server's mounted workspace"
    assert re.search(r"(don'?t|do not|never|no)\s+retry", window, _I), "must not retry after Could not read file"


def test_173_diag_drops_any_folder_worktree_claim():
    sonar = _diag_sonar()
    assert not re.search(r"any folder", sonar, _I), "remove the 'works from any folder' claim"
    assert not re.search(r"works?[^.\n]{0,40}worktrees?", sonar, _I), "remove the 'works ... worktrees' claim"
    assert not re.search(r"never needs to see the file ?system", sonar, _I)


def test_173_diag_flowchart_shows_unmounted_skip():
    chart = _read("diag", "flowchart.md")
    assert re.search(r"Could not read|mount", chart, _I), (
        "diag flowchart must show the skip on an unmounted path"
    )


# =========================================================================== Item 4
# HLD reference is conditional on the version's HLD existing; no fallback to older HLDs.


def _conditional_hld_near(text: str, heading: str, radius: int = 700) -> bool:
    for m in re.finditer(re.escape(heading), text):
        window = text[max(0, m.start() - radius): m.end() + radius]
        has_condition = re.search(r"(only (when|if)|if)[^.\n]{0,80}v<N>-design\.md[^.\n]{0,40}exists"
                                  r"|exists[^.\n]{0,80}(only|omit|leave out|drop)", window, _I) or (
            re.search(r"\bexists?\b", window, _I) and re.search(r"\b(omit|leave out|drop|only)\b", window, _I))
        no_fallback = re.search(
            r"(never|do not|don'?t)[^.\n]{0,60}(fall ?back|older|earlier|previous)[^.\n]{0,60}(version|HLD)",
            window, _I)
        if has_condition and no_fallback:
            return True
    return False


def test_173_architect_task_template_hld_reference_is_conditional():
    text = _read("architect")
    task_tpl = _between(text, r"##### Task body template", r"##### Epic body template")
    assert _conditional_hld_near(task_tpl, "## HLD reference"), (
        "architect task template: include HLD reference only when docs/design/v<N>/v<N>-design.md "
        "exists, never fall back to an older version's HLD"
    )


def test_173_architect_epic_template_hld_reference_is_conditional():
    text = _read("architect")
    epic_tpl = _between(text, r"##### Epic body template", r"\n#### ")
    assert _conditional_hld_near(epic_tpl, "### HLD reference"), (
        "architect epic template: include HLD reference only when the version's HLD exists, "
        "never fall back to an older version's HLD"
    )


def test_173_lld_task_template_hld_reference_is_conditional():
    text = _read("lld")
    assert _conditional_hld_near(text, "**HLD reference:**"), (
        "lld task template: include **HLD reference:** only when the version's HLD exists, "
        "never fall back to an older version's HLD"
    )


# =========================================================================== Item 5
# diagnostics-checker agent deleted, every reference gone, README count is 13.


def test_173_diagnostics_checker_agent_deleted():
    assert not (AGENTS / "diagnostics-checker.md").exists()


def _reference_files():
    for path in PLUGIN_ROOT.rglob("*"):
        if not path.is_file():
            continue
        rel = path.relative_to(PLUGIN_ROOT).as_posix()
        if rel.startswith(("docs/sessions/", "docs/reports/")):
            continue
        yield path
    yield REPO_ROOT / "README.md"
    yield REPO_ROOT / "CLAUDE.md"
    yield REPO_ROOT / "tests" / "test_agent_schema.py"


def test_173_no_diagnostics_checker_references_remain():
    hits = []
    for path in _reference_files():
        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        if "diagnostics-checker" in text:
            hits.append(str(path.relative_to(REPO_ROOT)))
    assert not hits, f"diagnostics-checker still referenced in: {hits}"


def test_173_readme_agent_count_is_13():
    readme = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
    m = re.search(r"\*\*(\d+) agents\*\*", readme)
    assert m, "README must state the agent count"
    assert m.group(1) == "13"
    actual = len(list(AGENTS.glob("*.md")))
    assert actual == 13, f"agents dir has {actual} agent files"


# =========================================================================== Item 6
# lld/template.md: one outer ```markdown open, one outer close, no bare fences inside.

_TEMPLATE = SKILLS / "lld" / "template.md"


def _template_lines() -> list[str]:
    return _TEMPLATE.read_text(encoding="utf-8").splitlines()


def _outer_open_index(lines: list[str]) -> int:
    idx = next((i for i, ln in enumerate(lines) if ln.strip() == "```markdown"), None)
    assert idx is not None, "template.md must open an outer ```markdown fence"
    return idx


def test_173_state_diagram_fence_is_escaped_like_siblings():
    lines = _template_lines()
    start = next(i for i, ln in enumerate(lines) if ln.strip() == "#### State diagram")
    end = next(i for i in range(start + 1, len(lines)) if lines[i].startswith("**When required:**"))
    section = lines[start:end]
    # Sibling mermaid examples (e.g. the sequence diagram) use "`` ```mermaid" / "`` ```".
    assert any(ln.strip() == "`` ```mermaid" for ln in section), (
        "state-diagram example must open with the escaped '`` ```mermaid' form used by siblings"
    )
    assert any(ln.strip() == "`` ```" for ln in section), "state-diagram example must close with '`` ```'"
    assert not any(ln.startswith("```") for ln in section), "no bare ``` fence in the state-diagram example"


def test_173_template_has_single_outer_fence():
    lines = _template_lines()
    open_idx = _outer_open_index(lines)
    bare = [i for i in range(open_idx + 1, len(lines)) if lines[i].lstrip().startswith("```")]
    assert len(bare) == 1, (
        "the outer ```markdown fence must be closed exactly once; bare fences found at lines "
        f"{[i + 1 for i in bare]}"
    )
    close_idx = bare[0]
    assert lines[close_idx].strip() == "```", "the outer close must be a bare ``` line"
    assert all(not ln.strip() for ln in lines[close_idx + 1:]), (
        "the outer close must sit at the end of the template section"
    )


def test_173_only_one_markdown_open_fence():
    lines = _template_lines()
    opens = [i for i, ln in enumerate(lines) if ln.lstrip().startswith("```markdown")]
    assert len(opens) == 1, f"expected one outer ```markdown open, found at {[i + 1 for i in opens]}"


# =========================================================================== Version bump


def test_173_plugin_version_bumped_and_in_sync():
    plugin = json.loads((PLUGIN_ROOT / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8"))
    market = json.loads((REPO_ROOT / ".claude-plugin" / "marketplace.json").read_text(encoding="utf-8"))
    entry = next(p for p in market["plugins"] if p.get("name") == plugin["name"])
    assert entry["version"] == plugin["version"], "plugin.json and marketplace.json versions must match"
    assert tuple(int(x) for x in plugin["version"].split(".")) > (0, 10, 96), (
        "#173 must bump the patch version past 0.10.96"
    )
