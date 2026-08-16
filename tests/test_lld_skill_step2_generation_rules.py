"""Validate SKILL.md Step 2 diagram generation rules.

Covers issue #52: rewrite `plugins/edf/skills/lld/SKILL.md` Step 2's diagram
generation rules so the template's conventions (E1.1) are applied
mechanically — no `edf://` references, no sequenceDiagram `link` emission
instruction, a concrete content signal per conditional diagram type, the
palette applied by reference rather than restated, the full link-emission
support matrix (including the D1 document-relative path form with
`design-root` containment, `..` permitted), the classDiagram display-label
workaround, the D4 mechanism-and-rejection annotation format, a worked
example per concern, and the co-versioning rule.

Assertions are semantic (token/regex based on a bounded section slice) rather
than exact-sentence matches, since the normative wording is subject to review
edits and the implementation has not been written yet. See
plugins/edf/docs/design/v1/lld-v1-e1-3-skill-quality-gates.md Part A §3.1 and
Part B §3.1 "Rules to state" / "Worked examples — required shape", for the
source wording these tests are derived from.

Scoping: assertions are bounded to the Step 2 "Diagram generation rules"
block of SKILL.md via `_step2_block()`, not the whole file. This bounding was
originally required because Step 2.5 still carried an `edf://` reference and
sequenceDiagram `link` prose that were out of scope here; #53 has since
removed both, and whole-file coverage of those two invariants now lives in
`test_lld_skill_step25_self_critique.py`. The bounding is kept regardless: it
is what proves a Step 2 assertion passes on Step 2's own text rather than on
Step 2.5's mirror of it. The one exception is the palette-hex invariant (LLD
Invariant 4), which is file-wide but only requires that any hex hit sits
inside a fenced code block.
"""

import json
import pathlib
import re

PLUGIN_ROOT = pathlib.Path(__file__).resolve().parent.parent / "plugins" / "edf"
SKILL_PATH = PLUGIN_ROOT / "skills" / "lld" / "SKILL.md"
REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
PLUGIN_JSON_PATH = PLUGIN_ROOT / ".claude-plugin" / "plugin.json"
MARKETPLACE_JSON_PATH = REPO_ROOT / ".claude-plugin" / "marketplace.json"

PALETTE_HEXES = {
    "error": "#f7d6d6",
    "auth": "#f7eed6",
    "external": "#d6e8f7",
    "new": "#d4f0d4",
}

CONDITIONAL_DIAGRAM_TYPES = [
    "stateDiagram-v2",
    "erDiagram",
    "flowchart",
    "classDiagram",
]


def _skill_text():
    return SKILL_PATH.read_text(encoding="utf-8")


def _step2_block(text):
    """Return the Step 2 "Diagram generation rules" block, bounded from its
    marker through the start of "### Step 2.5".

    Step 2.5 still carries a legacy `edf://` reference and `link`-directive
    prose (out of scope, task #53) — these tests must not see them.
    """
    match = re.search(
        r"\*\*Diagram generation rules\*\*.*?(?=\n### Step 2\.5)",
        text,
        re.DOTALL,
    )
    assert match, "SKILL.md has no 'Diagram generation rules' block before Step 2.5"
    return match.group(0)


# ── describe('SKILL.md Step 2 generation rules') ────────────────────────────


def test_contains_no_edf_scheme_reference():
    """#52: no edf:// reference remains in the Step 2 generation-rules block."""
    block = _step2_block(_skill_text())
    assert "edf://" not in block, (
        "Step 2 generation-rules block still contains an edf:// occurrence"
    )


def test_instructs_no_link_directive_in_a_sequence_diagram():
    """#52: no instruction to emit a `link` directive in a sequenceDiagram (D2)."""
    block = _step2_block(_skill_text())
    assert not re.search(
        r"sequenceDiagram[^\n]{0,80}`?link`?\s+<?actor", block, re.IGNORECASE
    ), "Step 2 still instructs emitting a `link` directive on a sequenceDiagram actor"
    assert not re.search(
        r"`?link`?\s+<actor>[^\n]{0,40}@[^\n]{0,40}<url>", block
    ), "Step 2 still shows the sequenceDiagram `link <actor>: ... @ <url>` form"


def test_states_content_signal_per_conditional_diagram_type():
    """#52: each conditional diagram type is gated by a concrete content signal.

    The signal must appear *near* the diagram type it gates. Searching the whole
    block would let unrelated prose satisfy the assertion — "gate table" and
    "canonical palette table" both contain "table", so a bare `table` pattern
    passes even with the erDiagram signal deleted entirely.
    """
    block = _step2_block(_skill_text())
    signal_patterns = {
        "stateDiagram-v2": r"non-trivial|retry|optimistic|polling",
        "erDiagram": r"entity-graph|FK relationship|foreign.key|adds a table|new table",
        "flowchart": r"(two|2|multi|multiple)[- ]condition|or more conditions|branch",
        "classDiagram": r"module boundary|module-boundary|adds a module|new module|"
        r"dependency between",
    }
    window = 200
    for diagram_type in CONDITIONAL_DIAGRAM_TYPES:
        occurrences = list(re.finditer(re.escape(diagram_type), block))
        assert occurrences, f"Step 2 block does not mention {diagram_type!r}"
        pattern = signal_patterns[diagram_type]
        near = any(
            re.search(
                pattern,
                block[max(0, m.start() - window) : m.end() + window],
                re.IGNORECASE,
            )
            for m in occurrences
        )
        assert near, (
            f"Step 2 block does not name a concrete content signal near any "
            f"mention of {diagram_type!r}"
        )


def test_references_template_for_palette_values_rather_than_restating_hexes():
    """#52: palette values come from the template's canonical table, never restated as hexes."""
    block = _step2_block(_skill_text())
    assert re.search(r"template", block, re.IGNORECASE), (
        "Step 2 block does not reference the template for palette values"
    )
    assert re.search(r"canonical", block, re.IGNORECASE), (
        "Step 2 block does not mark the template's palette table as canonical"
    )
    for role, hexval in PALETTE_HEXES.items():
        assert hexval not in block, (
            f"Step 2 block restates palette hex {hexval} for role {role!r} "
            "instead of referencing the template"
        )


def test_palette_hex_appears_only_inside_a_fenced_code_block():
    """LLD Invariant 4: any palette hex hit in SKILL.md sits inside a fenced code block.

    File-wide (not bounded to Step 2), per LLD Invariant 4 — a syntax
    demonstration snippet may legitimately show a hex value.
    """
    text = _skill_text()
    fence_matches = list(re.finditer(r"```.*?```", text, re.DOTALL))

    def _inside_fence(pos):
        return any(m.start() <= pos < m.end() for m in fence_matches)

    for role, hexval in PALETTE_HEXES.items():
        for hit in re.finditer(re.escape(hexval), text):
            assert _inside_fence(hit.start()), (
                f"palette hex {hexval} for role {role!r} appears outside a "
                "fenced code block"
            )


def test_states_exactly_one_palette_class_per_participant():
    """#52: exactly one palette class applies per participant."""
    block = _step2_block(_skill_text())
    assert re.search(r"exactly one class", block, re.IGNORECASE), (
        "Step 2 block does not state that exactly one class applies per participant"
    )


def test_states_no_emit_rule_for_sequence_and_er_diagrams():
    """#52: the link-emission rule states no-emit for BOTH sequenceDiagram and erDiagram."""
    block = _step2_block(_skill_text())
    assert re.search(
        r"sequenceDiagram[^\n]{0,120}(emit nothing|no link|omit link)", block, re.IGNORECASE
    ) or re.search(
        r"(emit nothing|no link|omit link)[^\n]{0,80}sequenceDiagram", block, re.IGNORECASE
    ), "Step 2 block does not state the no-emit rule for sequenceDiagram"
    assert re.search(
        r"erDiagram[^\n]{0,120}(emit nothing|no link|omit link)", block, re.IGNORECASE
    ) or re.search(
        r"(emit nothing|no link|omit link)[^\n]{0,80}erDiagram", block, re.IGNORECASE
    ), "Step 2 block does not state the no-emit rule for erDiagram"


def test_states_state_diagram_no_self_rule():
    """#52 (D3): the stateDiagram-v2 rule omits `_self` on its click directive."""
    block = _step2_block(_skill_text())
    assert re.search(
        r"stateDiagram-v2[^\n]{0,120}(no _self|without _self)", block
    ) or re.search(
        r"(no _self|without _self)[^\n]{0,80}stateDiagram-v2", block
    ), "Step 2 block does not state that stateDiagram-v2 clicks omit `_self`"


def test_states_document_relative_path_form_with_design_root_containment():
    """#52 (LLD Invariant 6): document-relative path form, `..` permitted, design-root containment.

    A rule banning `..` would reject every correct link (D1) — the block must
    state `..` is permitted, not banned.
    """
    block = _step2_block(_skill_text())
    assert re.search(r"document-relative", block, re.IGNORECASE), (
        "Step 2 block does not state the document-relative path form"
    )
    assert re.search(r"design-root", block), (
        "Step 2 block does not state design-root containment"
    )
    assert re.search(r"\.\.[^\n]{0,40}permitted", block, re.IGNORECASE), (
        "Step 2 block does not state that `..` is permitted"
    )
    assert not re.search(
        r"no \.\. segments|\.\.[^\n]{0,60}(not permitted|banned|disallowed)",
        block,
        re.IGNORECASE,
    ), "Step 2 block still bans `..` segments — this rejects every correct link (D1)"


def test_states_classdiagram_display_label_workaround_for_slash_identifiers():
    """#52: identifiers containing `/` use the classDiagram display-label workaround."""
    block = _step2_block(_skill_text())
    assert re.search(r"display label", block, re.IGNORECASE), (
        "Step 2 block does not describe the display-label workaround"
    )
    # A bare `/` search is tautological — any path or "and/or" in a ~100-line
    # markdown block satisfies it. Require the slash on the same line as the
    # identifier rule it constrains.
    assert re.search(r"identifier[^\n]{0,60}`?/`?", block, re.IGNORECASE), (
        "Step 2 block does not tie the workaround to identifiers containing `/`"
    )


def test_states_mechanism_and_rejection_annotation_format_without_semicolon():
    """#52 (D4): annotation format is mechanism — rejection, comma separated, no semicolon."""
    block = _step2_block(_skill_text())
    assert re.search(r"mechanism", block, re.IGNORECASE) and re.search(
        r"rejection", block, re.IGNORECASE
    ), "Step 2 block does not state the mechanism-and-rejection annotation format"
    assert re.search(r"comma separated", block, re.IGNORECASE), (
        "Step 2 block does not state the annotation fields are comma separated"
    )
    assert re.search(
        r";[^\n]{0,60}parse error", block, re.IGNORECASE
    ) or re.search(
        r"semicolon[^\n]{0,60}(parse error|never use)", block, re.IGNORECASE
    ), "Step 2 block does not state the D4 no-semicolon constraint"


def test_provides_a_worked_example_for_each_of_the_four_concerns():
    """#52: a worked example is present for type selection, palette, link emission, annotation.

    This guards the PR's central acceptance criterion, so it asserts on the
    labelled worked-example markers themselves. Checking only that the four
    concern words and the word "example" appear somewhere would pass with a
    single example alongside four rule headings.
    """
    block = _step2_block(_skill_text())
    labelled = {
        m.group(1).strip().lower()
        for m in re.finditer(r"\*Worked example\s*[—-]\s*([^.*]+)", block)
    }
    for concern in ("type selection", "palette", "link emission", "annotation"):
        assert concern in labelled, (
            f"Step 2 block has no labelled worked example for the {concern!r} "
            f"concern (found: {sorted(labelled)})"
        )


def test_states_covering_rule_every_template_feature_has_a_generation_rule():
    """#52 (LLD Invariant 3, Design Principle 6): co-versioning rule — every template
    feature has a corresponding generation rule."""
    block = _step2_block(_skill_text())
    assert re.search(
        r"every template feature[^\n]{0,80}(corresponding )?generation rule", block, re.IGNORECASE
    ), "Step 2 block does not state the co-versioning rule"


def test_states_click_must_follow_node_declaration():
    """#52 (D5): a `click` must be emitted AFTER the node/participant declaration it targets.

    Measured on mermaid 11.12.2 (E1.1): a click before its node declaration is
    silently dropped, and both orderings parse — so the rule must be stated
    explicitly, not just modelled correctly by example.
    """
    block = _step2_block(_skill_text())
    assert re.search(
        r"click[^\n]{0,80}(after|last)[\s\S]{0,200}(declar|node|participant)",
        block,
        re.IGNORECASE,
    ) or re.search(
        r"(declar)[\s\S]{0,200}before[\s\S]{0,80}click", block, re.IGNORECASE
    ), "Step 2 block does not state that a click must follow its node declaration"


def test_states_classdef_needs_a_local_scope_per_fence():
    """#52 (D6): each mermaid fence needs its own local `classDef` — not global across fences.

    classDef definitions do not carry over between separate mermaid fenced
    blocks; a diagram that references a class without its own local classDef
    silently loses the styling.
    """
    block = _step2_block(_skill_text())
    assert re.search(r"classDef", block), "Step 2 block does not mention classDef"
    assert re.search(
        r"classDef[^\n]{0,120}(each|every|per)[^\n]{0,40}(diagram|fence|block)",
        block,
        re.IGNORECASE,
    ) or re.search(
        r"(each|every|per)[^\n]{0,40}(diagram|fence|block)[^\n]{0,120}classDef",
        block,
        re.IGNORECASE,
    ), "Step 2 block does not state that classDef must be defined locally per fence"
    assert re.search(
        r"not global|fence-local|per-fence|does not carry|never carries|"
        r"not shared across|do(es)? not carry over",
        block,
        re.IGNORECASE,
    ), (
        "Step 2 block does not state that classDef is not global/shared across "
        "fences"
    )


# ── LLD Invariant 7 ───────────────────────────────────────────────────────────


def test_plugin_json_and_marketplace_json_versions_match():
    """LLD Invariant 7: plugin.json version equals the marketplace.json edf entry version."""
    plugin_data = json.loads(PLUGIN_JSON_PATH.read_text(encoding="utf-8"))
    marketplace_data = json.loads(MARKETPLACE_JSON_PATH.read_text(encoding="utf-8"))

    plugin_version = plugin_data["version"]
    edf_entries = [p for p in marketplace_data["plugins"] if p.get("name") == "edf"]
    assert edf_entries, "marketplace.json has no 'edf' plugin entry"
    marketplace_version = edf_entries[0]["version"]

    assert plugin_version == marketplace_version, (
        f"plugin.json version ({plugin_version}) does not match "
        f"marketplace.json edf entry version ({marketplace_version})"
    )
