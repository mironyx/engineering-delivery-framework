"""Validate SKILL.md Step 2.5 parse-then-navigability self-critique checks.

Covers issue #53: replace the single trailing "Diagram navigability"
checklist item with distinct parse, navigability, path-form, file-existence,
fragment, palette and annotation checks — parse checks gating the rest — and
reposition them into the security-and-correctness cluster.

Three properties here are behavioural, not cosmetic, and each encodes a
measured fact about mermaid 11.12.2:

* **Ordering.** A diagram that fails to parse renders as nothing, so a
  navigability finding against it names the wrong defect. The parse checks
  must appear textually before the navigability checks (Invariant 8).
* **No `link` parse check (D2).** The sequence-diagram `link` directive
  *parses*. Its omission is a generation convention enforced by Step 2, not a
  parse defect. A parse check for it would report a non-error and train
  authors to distrust the whole parse section (Invariant 10).
* **Path form and file existence stay separate.** A path that escapes
  `design-root` still resolves on the author's own machine, so a combined
  check passes locally and fails for every other reader — the exact failure
  decision D1 corrected (Invariant 11).

Assertions are semantic (token/regex over a bounded section slice) rather
than exact-sentence matches, since the normative wording is subject to review
edits. See plugins/edf/docs/design/v1/lld-v1-e1-3-skill-quality-gates.md
Part A §3.2 (Invariants 8-14, BDD specs) and Part B §3.2 "Placement" /
"Checks to state" for the source wording.
"""

import json
import pathlib
import re

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
PLUGIN_ROOT = REPO_ROOT / "plugins" / "edf"
SKILL_PATH = PLUGIN_ROOT / "skills" / "lld" / "SKILL.md"
FLOWCHART_PATH = PLUGIN_ROOT / "skills" / "lld" / "flowchart.md"
PLUGIN_JSON_PATH = PLUGIN_ROOT / ".claude-plugin" / "plugin.json"
MARKETPLACE_JSON_PATH = REPO_ROOT / ".claude-plugin" / "marketplace.json"


def _skill_text():
    return SKILL_PATH.read_text(encoding="utf-8")


def _step25_block(text):
    """Return the Step 2.5 self-critique checklist, bounded to Step 2.6.

    Bounding matters in both directions: Step 2 legitimately carries the
    generation rules these checks mirror, so an unbounded search would pass
    on Step 2's text even if Step 2.5 were empty.
    """
    match = re.search(
        r"\n### Step 2\.5:.*?(?=\n### Step 2\.6)",
        text,
        re.DOTALL,
    )
    assert match, "SKILL.md has no Step 2.5 section terminated by Step 2.6"
    return match.group(0)


def _checklist_items(block):
    """Top-level checklist items in the Step 2.5 block, in document order.

    Returns a list of (bold_label, full_item_text). Continuation lines and
    nested sub-bullets are folded into their parent item so that a check
    spanning several lines is still one item.
    """
    items = []
    current = None
    for line in block.split("\n"):
        top = re.match(r"^- \*\*(.+?)\*\*", line)
        if top:
            if current:
                items.append(current)
            current = [top.group(1), line]
        elif re.match(r"^- ", line):
            # A top-level bullet without a bold label still ends the previous item.
            if current:
                items.append(current)
            current = ["", line]
        elif current is not None:
            current[1] += "\n" + line
    if current:
        items.append(current)
    return [(label, text) for label, text in items]


def _item_index(items, needle):
    """Index of the first checklist item whose label contains `needle`."""
    for i, (label, _) in enumerate(items):
        if needle.lower() in label.lower():
            return i
    raise AssertionError(
        f"no Step 2.5 checklist item labelled like {needle!r}; "
        f"labels present: {[label for label, _ in items]}"
    )


def _parse_item(items):
    return items[_item_index(items, "parse")][1]


def _navigability_item(items):
    return items[_item_index(items, "navigability")][1]


# ---------------------------------------------------------------------------
# Ordering — parse checks gate everything else (Invariant 8)
# ---------------------------------------------------------------------------


def test_places_parse_checks_before_navigability_checks():
    items = _checklist_items(_step25_block(_skill_text()))
    assert _item_index(items, "parse") < _item_index(items, "navigability")


def test_parse_checks_are_declared_as_gating_the_rest():
    """The ordering must be stated as a rule, not left implicit in layout."""
    item = _parse_item(_checklist_items(_step25_block(_skill_text())))
    assert re.search(r"\bfirst\b", item, re.IGNORECASE), (
        "the parse item must state that it runs first"
    )
    assert re.search(r"\bgate", item, re.IGNORECASE), (
        "the parse item must state that it gates the checks below"
    )


def test_parse_failure_reports_the_offender_and_stops_that_diagram():
    item = _parse_item(_checklist_items(_step25_block(_skill_text())))
    assert re.search(r"report", item, re.IGNORECASE)
    assert re.search(r"\bstop\b|\bskip\b", item, re.IGNORECASE), (
        "a parse failure must stop further assessment of that diagram"
    )


# ---------------------------------------------------------------------------
# The four measured parse cases (Invariant 9)
# ---------------------------------------------------------------------------


def test_checks_for_click_in_a_sequence_diagram():
    item = _parse_item(_checklist_items(_step25_block(_skill_text())))
    assert re.search(r"`?click`?[^\n]*`?sequenceDiagram`?", item), item


def test_checks_for_self_on_a_state_diagram_click():
    item = _parse_item(_checklist_items(_step25_block(_skill_text())))
    assert "_self" in item
    assert "stateDiagram-v2" in item


def test_checks_for_a_slash_in_a_class_diagram_identifier():
    item = _parse_item(_checklist_items(_step25_block(_skill_text())))
    assert re.search(r"`/`[^\n]*`?classDiagram`?|`?classDiagram`?[^\n]*`/`", item), item


def test_checks_for_a_semicolon_in_note_text():
    item = _parse_item(_checklist_items(_step25_block(_skill_text())))
    assert re.search(r"`;`", item), item
    assert re.search(r"`?Note`? text", item), item


def test_does_not_check_the_sequence_link_directive_as_a_parse_error():
    """D2: the `link` directive parses. A parse check for it reports a non-error.

    Scoped to the parse item — Step 2's generation rules legitimately
    instruct against emitting `link`, and that is a convention, not a defect.
    """
    item = _parse_item(_checklist_items(_step25_block(_skill_text())))
    assert not re.search(r"\blink\b\s+directive", item, re.IGNORECASE), (
        "the parse checks must not name the sequence `link` directive — it parses"
    )
    assert not re.search(r"\blink\b[^\n]*parse error", item, re.IGNORECASE), item


def test_no_link_directive_parse_error_claim_anywhere_in_the_skill():
    """LLD Invariant 10, whole-file as written."""
    assert not re.search(r"\blink\b[^\n]*parse error", _skill_text(), re.IGNORECASE)


# ---------------------------------------------------------------------------
# Navigability scope (three link-supporting types)
# ---------------------------------------------------------------------------


def test_scopes_navigability_checks_to_the_three_link_supporting_types():
    item = _navigability_item(_checklist_items(_step25_block(_skill_text())))
    for diagram_type in ("flowchart", "classDiagram", "stateDiagram-v2"):
        assert diagram_type in item, f"{diagram_type} missing from navigability scope"


def test_navigability_scope_excuses_the_two_link_free_types():
    """`sequenceDiagram` and `erDiagram` carry no links by design.

    Without this, the gate reports every sequence participant as a dead
    label — a finding the author cannot act on.
    """
    item = _navigability_item(_checklist_items(_step25_block(_skill_text())))
    assert "sequenceDiagram" in item and "erDiagram" in item, item


# ---------------------------------------------------------------------------
# Path form vs file existence — two checks, deliberately (Invariant 11)
# ---------------------------------------------------------------------------


def test_checks_path_form_and_file_existence_separately():
    items = _checklist_items(_step25_block(_skill_text()))
    form = _item_index(items, "path form")
    exists = _item_index(items, "exist")
    assert form != exists, (
        "path form and file existence must be two distinct checklist items"
    )


def test_path_form_check_uses_design_root_containment_not_a_dotdot_ban():
    """D1: `..` segments are expected — the base is the LLD's own directory."""
    items = _checklist_items(_step25_block(_skill_text()))
    item = items[_item_index(items, "path form")][1]
    assert "design-root" in item, item
    assert not re.search(r"no `?\.\.`? segments", item), (
        "a `..` ban would reject every correct document-relative link"
    )


def test_checks_every_lld_fragment_against_a_part_b_anchor():
    block = _step25_block(_skill_text())
    items = _checklist_items(block)
    item = items[_item_index(items, "fragment")][1]
    assert "#LLD-" in item
    assert re.search(r"<a id>|<a\s+id=", item), item
    assert re.search(r"case-sensitive", item, re.IGNORECASE), item


# ---------------------------------------------------------------------------
# Palette and annotations (Invariant 12)
# ---------------------------------------------------------------------------


def test_checks_the_palette_block_sits_in_a_text_fence():
    items = _checklist_items(_step25_block(_skill_text()))
    item = items[_item_index(items, "palette")][1]
    assert re.search(r"`text`", item), item
    assert re.search(r"`mermaid`", item), (
        "the check must contrast the `text` fence with the bare `mermaid` fence"
    )


def test_palette_check_covers_presence_and_consistent_application():
    items = _checklist_items(_step25_block(_skill_text()))
    item = items[_item_index(items, "palette")][1]
    assert re.search(r"exactly one class|one class each", item, re.IGNORECASE), item
    assert "classDef" in item


def test_palette_check_does_not_claim_class_diagram_styling_renders():
    """Measured on the pinned mermaid: `classDef` + `class X role` applies NO
    styling in a `classDiagram`, though it works in `flowchart` and
    `stateDiagram-v2`. The gate must not raise an unfixable finding.
    """
    items = _checklist_items(_step25_block(_skill_text()))
    item = items[_item_index(items, "palette")][1]
    assert "classDiagram" in item, (
        "the palette check must note the measured classDiagram styling gap "
        "so an unstyled classDiagram is not reported as an authoring defect"
    )


def test_checks_every_trust_boundary_interaction_carries_a_note():
    items = _checklist_items(_step25_block(_skill_text()))
    item = items[_item_index(items, "annotation")][1]
    assert re.search(r"`Note`", item), item
    for boundary in ("authZ", "validation", "error propagation"):
        assert boundary in item, f"{boundary} missing from the annotation check"


# ---------------------------------------------------------------------------
# Report specificity (Invariant 13)
# ---------------------------------------------------------------------------


def test_requires_failure_messages_to_name_the_specific_offender():
    block = _step25_block(_skill_text())
    assert re.search(
        r"name the specific (participant|path|fragment|interaction|diagram)",
        block,
        re.IGNORECASE,
    ), "Step 2.5 must require findings to name the offender"


def test_rejects_vague_findings_explicitly():
    block = _step25_block(_skill_text())
    assert re.search(r"is not a finding", block, re.IGNORECASE), (
        "the vague-finding counter-example must be stated as rejected"
    )


# ---------------------------------------------------------------------------
# Placement (Invariant 14)
# ---------------------------------------------------------------------------


def test_diagram_checks_sit_immediately_after_the_attack_surface_item():
    items = _checklist_items(_step25_block(_skill_text()))
    attack = _item_index(items, "attack surface")
    parse = _item_index(items, "parse")
    assert parse == attack + 1, (
        "the parse checks must directly follow 'Attack surface / STRIDE-lite'; "
        f"got attack={attack} parse={parse}"
    )


def test_diagram_checks_are_followed_by_at_least_two_other_items():
    """A check the author scrolls past is a check that did not run."""
    items = _checklist_items(_step25_block(_skill_text()))
    last_diagram = _item_index(items, "annotation")
    trailing = len(items) - last_diagram - 1
    assert trailing >= 2, (
        f"only {trailing} checklist item(s) follow the diagram checks; "
        "they must not be the trailing items"
    )


def test_error_paths_item_follows_the_diagram_checks():
    items = _checklist_items(_step25_block(_skill_text()))
    assert _item_index(items, "annotation") < _item_index(items, "error paths")


# ---------------------------------------------------------------------------
# The old trailing item is gone, not duplicated
# ---------------------------------------------------------------------------


def test_old_trailing_navigability_item_and_its_todo_marker_are_removed():
    """Leaving both old and new means authors follow whichever they reach first."""
    text = _skill_text()
    assert "TODO(#53)" not in text
    assert "link <actor>" not in text, (
        "the old item's sequenceDiagram `link` prose must be deleted"
    )


def test_no_edf_scheme_reference_remains_in_the_skill():
    """LLD Invariant 1, whole-file — the fifth occurrence lived in Step 2.5."""
    assert "edf://" not in _skill_text()


def test_navigability_appears_exactly_once_as_a_checklist_label():
    items = _checklist_items(_step25_block(_skill_text()))
    labelled = [label for label, _ in items if "navigability" in label.lower()]
    assert len(labelled) == 1, f"expected one navigability item, got {labelled}"


# ---------------------------------------------------------------------------
# Companion artefacts
# ---------------------------------------------------------------------------


def test_flowchart_documents_the_parse_gate_branch():
    """Skill steps and `flowchart.md` must not drift (CLAUDE.md convention)."""
    text = FLOWCHART_PATH.read_text(encoding="utf-8")
    assert re.search(r"diagrams parse", text, re.IGNORECASE), (
        "flowchart.md must show the parse gate introduced in Step 2.5"
    )


def test_plugin_and_marketplace_versions_match():
    """LLD Invariant 7."""
    plugin = json.loads(PLUGIN_JSON_PATH.read_text(encoding="utf-8"))["version"]
    marketplace = json.loads(MARKETPLACE_JSON_PATH.read_text(encoding="utf-8"))
    entry = next(p for p in marketplace["plugins"] if p["name"] == "edf")
    assert plugin == entry["version"], (
        f"plugin.json {plugin} != marketplace.json {entry['version']}"
    )
