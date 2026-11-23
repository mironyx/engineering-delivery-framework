"""Skill-prose contract checks for issue #169 — earlier design-stage checks, cheaper review.

Each check is moved earlier in the pipeline (architect, requirements, lld, lld-sync,
feature-core) or made cheaper (pr-review). Assertions are keyword/ordering checks over a
bounded section slice, not exact sentences, so review edits to wording do not break them.
Bounding matters: several skills already mention the same keywords elsewhere (e.g. the
architect Review Mode table cites "doc URL"), so an unbounded search would pass vacuously.
"""

import json
import pathlib
import re

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
PLUGIN_ROOT = REPO_ROOT / "plugins" / "edf"
SKILLS = PLUGIN_ROOT / "skills"
_I = re.IGNORECASE


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


def _windows(text: str, anchor: str, radius: int = 900):
    """Text windows of +/- radius chars around each match of `anchor`."""
    return [text[max(0, m.start() - radius): m.end() + radius] for m in re.finditer(anchor, text, _I)]


def _some_window_has(text: str, anchor: str, *patterns: str, radius: int = 900) -> bool:
    return any(all(re.search(p, w, _I) for p in patterns) for w in _windows(text, anchor, radius))


# --------------------------------------------------------------------------- /architect


def _architect_pre_gate() -> str:
    """Process Step 2 up to its 'Wait for user confirmation' gate (wherever that gate sits)."""
    text = _read("architect")
    start = re.search(r"\n### Step 2:", text)
    assert start, "architect has no Step 2"
    gate = re.search(r"wait for user confirmation", text[start.start():], _I)
    assert gate, "architect Step 2 has no 'Wait for user confirmation' gate"
    return text[start.start(): start.start() + gate.start()]


def test_169_architect_sizes_tasks_against_200_lines_before_overview_gate():
    pre_gate = _architect_pre_gate()
    assert re.search(r"\b200\b", pre_gate), "200-line sizing must happen before the overview gate"


def test_169_architect_lists_files_each_task_edits_before_overview_gate():
    pre_gate = _architect_pre_gate()
    assert re.search(
        r"\bfiles?\b[^.\n]{0,60}\b(edits?|touch(es)?|modif\w*|writes?)\b"
        r"|\b(edits?|touch(es)?|modif\w*)\b[^.\n]{0,40}\bfiles?\b",
        pre_gate,
        _I,
    ), "each task's file list must be produced before the overview gate"


def test_169_architect_shared_types_interfaces_allowlists_force_separate_waves():
    pre_gate = _architect_pre_gate()
    for word in (r"allowlist", r"interfaces?", r"types?"):
        assert _some_window_has(pre_gate, r"allowlist", word, r"wave"), (
            f"the shared-file wave rule must cover {word}"
        )


def test_169_architect_vendor_schema_cites_url_or_marks_unverified():
    process = _read("architect").split("\n## Process", 1)
    assert len(process) == 2, "architect has no ## Process section"
    assert _some_window_has(
        process[1],
        r"(vendor|third-party|external)[^\n]{0,80}(payload|schema)"
        r"|(payload|schema)[^\n]{0,80}(vendor|third-party|external)",
        r"\bURL\b|\bcite",
        r"unverified",
    ), "architect Process must check vendor payload shapes against a cited doc URL or mark them Unverified"


# --------------------------------------------------------------------------- /requirements


def _requirements_pre_gate1() -> str:
    text = _read("requirements")
    return _between(text, r"\n## Process", r"\n### Gate 1")


def test_169_requirements_integration_check_sits_before_gate_1():
    assert re.search(r"integration", _requirements_pre_gate1(), _I), (
        "an integration-story check must appear before Gate 1"
    )


def test_169_requirements_integration_check_reads_platform_docs_and_current_code():
    assert _some_window_has(
        _requirements_pre_gate1(),
        r"integration",
        r"\b(docs|documentation)\b",
        r"current code|existing code|codebase|source (code|files?)",
        r"constraints?",
    ), "integration check must read platform docs and current code and record constraints"


def test_169_requirements_integration_check_requires_cited_source():
    assert _some_window_has(
        _requirements_pre_gate1(), r"integration", r"\bURL\b|\bcite", r"unverified"
    ), "platform findings must cite a source URL or be marked Unverified"


# --------------------------------------------------------------------------- /lld and /lld-sync

_DELIVERY = r"redeliver|retr(y|ies)|ordering"


def test_169_lld_self_critique_checks_delivery_assumptions_as_blocker():
    block = _between(_read("lld"), r"\n### Step 2\.5:", r"\n### Step 2\.6")
    assert _some_window_has(block, r"kb/anti-patterns\.md", _DELIVERY, r"blocker", radius=600), (
        "lld Step 2.5 must check delivery assumptions against kb/anti-patterns.md as a blocker"
    )


def test_169_lld_sync_step2_checks_delivery_assumptions_as_correction():
    block = _between(_read("lld-sync"), r"\n### Step 2:", r"\n### Step 3:")
    assert _some_window_has(block, r"kb/anti-patterns\.md", _DELIVERY, r"correction", radius=600), (
        "lld-sync Step 2 must check delivery assumptions against kb/anti-patterns.md as a Correction"
    )


# --------------------------------------------------------------------------- feature-core


def test_169_feature_core_reuse_search_precedes_both_implementation_tracks():
    text = _read("feature-core")
    region = _between(text, r"\n## Steps — Shared preamble", r"\n### Step 4L")
    assert text.index("### Step 4L") < text.index("### Step 4bF"), "Step 4L must precede Step 4bF"
    assert _some_window_has(
        region,
        r"kb/anti-patterns\.md",
        r"\b(grep|search)",
        r"\bcomponents?\b",
        r"style|css",
        r"reus",
    ), "a pre-implementation reuse search (components, style classes, anti-patterns) must precede Step 4"


# --------------------------------------------------------------------------- /pr-review


def test_169_pr_review_threshold_is_300_with_no_150_left():
    for name in ("SKILL.md", "flowchart.md"):
        text = _read("pr-review", name)
        assert not re.search(r"\b150\b", text), f"pr-review/{name} still mentions the 150 threshold"
        assert re.search(r"(<|≥|>=)\s*300\b", text), f"pr-review/{name} must state the 300 threshold"


def test_169_pr_review_passes_kb_sections_filtered_by_changed_paths_with_full_fallback():
    step1 = _between(_read("pr-review"), r"\n### Step 1:", r"\n### Step 2:")
    assert _some_window_has(
        step1,
        r"\bsections?\b",
        r"kb/",
        r"changed[- ](files?|paths?)|numstat",
        r"fall ?back|no (section )?match",
        r"\bfull\b|whole|entire",
    ), "pr-review must filter kb sections by changed paths, falling back to full files"


# --------------------------------------------------------------------------- flowcharts and version


def test_169_flowcharts_reflect_new_steps():
    expectations = {
        "architect": r"allowlist|shared types?|interfaces?",
        "requirements": r"integration",
        "lld": r"anti-patterns|delivery assumption|redeliver",
        "lld-sync": r"delivery assumption|redeliver|retr(y|ies)",
        "feature-core": r"reuse search|reuse|style class",
    }
    missing = [s for s, p in expectations.items() if not re.search(p, _read(s, "flowchart.md"), _I)]
    assert not missing, f"flowcharts not updated for: {missing}"


def test_169_architect_flowchart_sizes_before_overview_gate():
    text = _read("architect", "flowchart.md")
    gate = re.search(r"Wait for user confirmation", text)
    assert gate
    assert re.search(r"200", text[: gate.start()])
    assert re.search(r"files", text[: gate.start()], _I)


def test_169_plugin_and_marketplace_versions_match():
    plugin = json.loads((PLUGIN_ROOT / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8"))
    market = json.loads((REPO_ROOT / ".claude-plugin" / "marketplace.json").read_text(encoding="utf-8"))
    entry = next(p for p in market["plugins"] if p["name"] == "edf")
    assert plugin["version"] == entry["version"]
