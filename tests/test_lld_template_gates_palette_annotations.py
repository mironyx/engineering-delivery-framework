"""Validate LLD template diagram-type gates, palette, and enforcement annotations.

Covers issue #46: harden the four conditional diagram-type gates ("When required" /
"When optional") to concrete content signals, apply the `classDef` palette to the
worked examples with the tie-break rule and `text`-fence placement, and add
enforcement `Note` annotations covering all four boundary types with the adjacency
rule and the no-semicolon rule (D4).

Issue #46 explicitly does NOT touch #45's frozen surface: link forms, the support
matrix, the path constraint, and the `#LLD-` anchor format are covered by
test_lld_template_link_forms.py and are out of scope here. #46 *consumes* that
surface only when adding `click` directives to the state-diagram and flowchart
worked examples.

Assertions are semantic (token/regex based) rather than exact-sentence matches,
since the normative wording is subject to review edits. See
plugins/edf/docs/design/v1/lld-v1-e1-1-template-vocabulary.md §1.2 ("Part A") and
"§1.2 — Implementation" ("Part B"), anchor LLD-v1-e1-1-gates-palette-annotations,
for the source wording these tests are derived from.
"""

import pathlib
import re

PLUGIN_ROOT = pathlib.Path(__file__).resolve().parent.parent / "plugins" / "edf"
TEMPLATE_PATH = PLUGIN_ROOT / "skills" / "lld" / "template.md"

# The four conditional diagram types gated by a content signal. sequenceDiagram is
# the unconditional primary and carries no gate — it is not part of this list.
CONDITIONAL_DIAGRAM_TYPES = [
    "stateDiagram-v2",
    "erDiagram",
    "flowchart",
    "classDiagram",
]

PALETTE_ROLES = {
    "error": "#f7d6d6",
    "auth": "#f7eed6",
    "external": "#d6e8f7",
    "new": "#d4f0d4",
}


def _template_text():
    return TEMPLATE_PATH.read_text(encoding="utf-8")


# A rule is only encoded if the document cannot also be read as stating its
# opposite. See test_lld_template_link_forms.py for the rationale behind this
# guard; the same construction is reused here.
NEGATION = r"(?<!not )(?<!never )(?<!isn't )(?<!aren't )"


# The literal, own-line diagram-type keyword that opens each worked example's
# fenced block, in the form the file actually uses (`flowchart TD`, not just
# `flowchart`). Mirrors test_lld_template_link_forms.py's `\nclassDiagram\n`
# anchor, which finds the worked example regardless of whether it sits behind
# an escaped or a bare fence marker.
TYPE_LINE = {
    "stateDiagram-v2": "stateDiagram-v2",
    "erDiagram": "erDiagram",
    "flowchart": "flowchart TD",
    "classDiagram": "classDiagram",
}


def _worked_example_block(text, diagram_type):
    """Return the worked-example block for a diagram type, keyword through backticks.

    template.md nests some worked examples inside its own outer instructional
    fence using an escaped (two-backtick-and-space) prefix, and lets others sit
    behind a bare fence that legitimately closes the outer fence early per
    CommonMark rules. Anchoring on the diagram-type keyword as its own line and
    capturing through the next run of backticks — regardless of which fence
    style surrounds it — sidesteps that structural quirk, matching the approach
    test_lld_template_link_forms.py already uses for the classDiagram example.
    """
    keyword = TYPE_LINE[diagram_type]
    match = re.search(rf"\n{re.escape(keyword)}\n.*?\n`+", text, re.DOTALL)
    assert match, f"template.md has no {diagram_type!r} worked example"
    return match.group(0)


def _section_for_type(text, diagram_type):
    """Return the prose immediately following a diagram type's worked example.

    This is where "When required"/"When optional" gate text lives in
    template.md's current structure — directly after the worked example's
    closing fence, up to the next markdown heading.
    """
    example = _worked_example_block(text, diagram_type)
    start = text.index(example) + len(example)
    rest = text[start:]
    trailing = re.search(r".*?(?=\n#{2,6}\s|\Z)", rest, re.DOTALL)
    return trailing.group(0) if trailing else ""


def _note_lines(text):
    """Extract every `Note ...` line across the whole file by line-regex.

    template.md's mermaid examples live inside an outer markdown fence, and at
    least one worked example is shown escaped (an extra two-backtick-and-space
    prefix) rather than inside a live ```mermaid fence. Extracting `Note` lines
    by regex over the raw file text, rather than by parsing fence boundaries,
    catches both forms uniformly.
    """
    return re.findall(r"^[^\n]*\bNote\s+(?:over|right of|left of)\b[^\n]*$", text, re.MULTILINE)


_FENCE_OPEN = re.compile(r"^(?:``\ )?```(\w*)\s*$")
_DIAGRAM_KEYWORD = re.compile(
    r"^(flowchart|classDiagram|erDiagram|stateDiagram-v2|sequenceDiagram|graph)\b"
)


def _classdef_block_fence_lang(text):
    """Find the language tag of the fence immediately preceding a standalone
    `classDef` palette block.

    "Standalone" means a block that defines `classDef` rules without a leading
    diagram-type keyword between it and its opening fence — the syntax
    demonstration, not a live diagram that happens to use `classDef`
    internally. Deliberately walks raw lines rather than pairing fence markers
    with a regex: template.md's worked examples sit at multiple nesting depths
    inside the document's own outer instructional fence (some escaped with a
    leading `` ` ` `` prefix, some left bare so they legitimately close the
    outer fence early per CommonMark), so a naive open/close pairing regex
    misaligns partway through the file. Scanning line-by-line and walking
    backward from each `classDef` line to its nearest fence-open marker avoids
    that misalignment entirely.
    """
    lines = text.splitlines()
    for i, line in enumerate(lines):
        if not re.match(r"^\s*classDef\b", line):
            continue
        for j in range(i - 1, -1, -1):
            match = _FENCE_OPEN.match(lines[j])
            if match:
                between = [ln.strip() for ln in lines[j + 1 : i]]
                if not any(_DIAGRAM_KEYWORD.match(ln) for ln in between):
                    return match.group(1)
                break
    return None


# ── describe('template.md diagram gates') ────────────────────────────────────


def test_states_content_signal_for_state_gate():
    """#46: stateDiagram-v2 gate names a concrete, checkable content signal."""
    text = _template_text()
    section = _section_for_type(text, "stateDiagram-v2")
    assert re.search(r"when required", section, re.IGNORECASE), (
        "no 'When required' gate found for stateDiagram-v2"
    )
    assert re.search(
        r"(non-trivial|retry|optimistic|polling)", section, re.IGNORECASE
    ), "stateDiagram-v2 gate does not name a concrete transition-related content signal"


def test_states_content_signal_for_er_gate():
    """#46: erDiagram gate names a concrete, checkable content signal."""
    text = _template_text()
    section = _section_for_type(text, "erDiagram")
    assert re.search(r"when required", section, re.IGNORECASE), (
        "no 'When required' gate found for erDiagram"
    )
    assert re.search(
        r"(new )?table|FK relationship|foreign.key", section, re.IGNORECASE
    ), "erDiagram gate does not name a concrete table/FK content signal"


def test_states_content_signal_for_flowchart_gate():
    """#46: flowchart gate names a concrete, checkable content signal."""
    text = _template_text()
    section = _section_for_type(text, "flowchart")
    assert re.search(r"when required", section, re.IGNORECASE), (
        "no 'When required' gate found for flowchart"
    )
    assert re.search(
        r"(two|2|multiple) or more conditions|branches on (two|2|multiple)",
        section,
        re.IGNORECASE,
    ), "flowchart gate does not name a concrete branch-count content signal"


def test_states_content_signal_for_classdiagram_gate():
    """#46: classDiagram gate names a concrete, checkable content signal."""
    text = _template_text()
    section = _section_for_type(text, "classDiagram")
    assert re.search(r"when required", section, re.IGNORECASE), (
        "no 'When required' gate found for classDiagram"
    )
    assert re.search(
        r"(new )?module|module boundary|dependency between", section, re.IGNORECASE
    ), "classDiagram gate does not name a concrete module/boundary content signal"


def test_states_when_optional_negative_case_for_each_type():
    """#46: each of the four conditional types states a 'When optional' negative case."""
    text = _template_text()
    for diagram_type in CONDITIONAL_DIAGRAM_TYPES:
        section = _section_for_type(text, diagram_type)
        assert re.search(r"when optional", section, re.IGNORECASE), (
            f"{diagram_type} has no 'When optional' negative case"
        )
        # The negative case must say something, not just echo the heading.
        optional_block = re.search(
            r"when optional\**:?\s*(.*)", section, re.IGNORECASE
        )
        assert optional_block and len(optional_block.group(1).strip()) > 10, (
            f"{diagram_type}'s 'When optional' case has no substantive content"
        )


def test_states_no_signal_produces_sequence_diagram_alone():
    """#46: a feature with none of the four gate signals gets the sequence diagram alone."""
    text = _template_text()
    assert re.search(
        r"sequence diagram (alone|only)", text, re.IGNORECASE
    ) or re.search(
        r"none of the (four|conditional)[^\n]{0,60}sequence diagram", text, re.IGNORECASE
    ), "template.md does not state that a feature with no gate signal gets the sequence diagram alone"


# ── describe('template.md palette') ──────────────────────────────────────────


def test_marks_palette_table_canonical():
    """#46: the palette table is marked as the canonical source of truth."""
    text = _template_text()
    assert re.search(r"canonical", text, re.IGNORECASE), (
        "template.md never marks the palette table as canonical"
    )
    # All four hex values must appear once each, tying "canonical" to the table
    # rather than to some unrelated sentence.
    for role, hexval in PALETTE_ROLES.items():
        assert text.count(hexval) >= 1, (
            f"palette hex value {hexval} for role {role!r} is missing from template.md"
        )


def test_places_standalone_classdef_block_in_text_fence():
    """#46: the standalone classDef syntax-demonstration block sits in a `text` fence.

    A standalone classDef block (no diagram-type keyword) is not a valid Mermaid
    diagram and fails to render inside a bare ```mermaid fence — it must be shown
    in a ```text fence instead, with the reason stated.
    """
    text = _template_text()
    lang = _classdef_block_fence_lang(text)
    assert lang is not None, "template.md has no standalone classDef demonstration block"
    assert lang == "text", (
        f"the standalone classDef block sits in a {lang!r} fence, not a `text` fence"
    )
    assert re.search(
        r"classDef[^\n]{0,80}(not a valid diagram|invalid Mermaid)", text, re.IGNORECASE
    ), "template.md does not state the reason a standalone classDef block needs a text fence"


def test_states_tie_break_rule_assigning_exactly_one_class():
    """#46: the tie-break rule — new/external outrank error/auth, exactly one class applies."""
    text = _template_text()
    assert re.search(r"exactly one class", text, re.IGNORECASE), (
        "template.md does not state that exactly one class applies to a participant"
    )
    assert re.search(
        r"new[^\n]{0,40}(and|/)[^\n]{0,10}external[^\n]{0,40}outrank", text, re.IGNORECASE
    ) or re.search(
        r"outrank[^\n]{0,80}(new|external)", text, re.IGNORECASE
    ), "template.md does not state that new/external outrank error/auth"


def test_applies_palette_classes_in_state_and_flowchart_examples():
    """#46: the state-diagram and flowchart worked examples carry palette classes."""
    text = _template_text()
    state_block = _worked_example_block(text, "stateDiagram-v2")
    flowchart_block = _worked_example_block(text, "flowchart")
    assert state_block, "template.md has no stateDiagram-v2 worked example"
    assert flowchart_block, "template.md has no flowchart worked example"

    known_roles = "|".join(PALETTE_ROLES.keys())
    assert re.search(rf"\bclass\b[^\n]*\b({known_roles})\b", state_block), (
        "the stateDiagram-v2 worked example applies no palette class"
    )
    assert re.search(rf"\bclass\b[^\n]*\b({known_roles})\b", flowchart_block), (
        "the flowchart worked example applies no palette class"
    )


def test_state_and_flowchart_examples_carry_at_least_one_click():
    """#46: the state-diagram and flowchart worked examples each carry a `click`.

    This is where #46 *consumes* #45's frozen support matrix: stateDiagram-v2
    clicks must omit `_self` and flowchart clicks must use the document-relative
    path form — those specific rules are #45's and are tested elsewhere; this
    test only checks that #46 actually added the directives to these examples.
    """
    text = _template_text()
    state_block = _worked_example_block(text, "stateDiagram-v2")
    flowchart_block = _worked_example_block(text, "flowchart")
    assert state_block, "template.md has no stateDiagram-v2 worked example"
    assert flowchart_block, "template.md has no flowchart worked example"

    assert re.search(r"^\s*click\s+\w", state_block, re.MULTILINE), (
        "the stateDiagram-v2 worked example carries no click directive"
    )
    assert re.search(r"^\s*click\s+\w", flowchart_block, re.MULTILINE), (
        "the flowchart worked example carries no click directive"
    )


def test_state_diagram_example_click_omits_self():
    """#45+#46 boundary: the stateDiagram-v2 example's click must omit `_self` (D3 caveat).

    #45's rule (stateDiagram-v2 + `_self` is a parse error) is frozen and tested
    in test_lld_template_link_forms.py; this test only checks #46's worked
    example obeys it, since #46 is the task that adds the click to this example.
    """
    text = _template_text()
    state_block = _worked_example_block(text, "stateDiagram-v2")
    assert state_block, "template.md has no stateDiagram-v2 worked example"
    click_lines = [
        line for line in state_block.splitlines() if re.match(r"\s*click\s+\w", line)
    ]
    assert click_lines, "the stateDiagram-v2 worked example carries no click directive"
    assert not any("_self" in line for line in click_lines), (
        "the stateDiagram-v2 worked example's click carries `_self`, "
        "which is a parse error per the support matrix (D3)"
    )


def test_flowchart_example_emits_clicks_after_declarations():
    """#45+#46 boundary: the flowchart example's clicks come after node declarations (D5).

    test_lld_template_link_forms.py already covers the classDiagram example for
    this ordering rule; #46 adds this same obligation to the flowchart example.
    """
    text = _template_text()
    flowchart_block = _worked_example_block(text, "flowchart")
    assert flowchart_block, "template.md has no flowchart worked example"

    first_node_decl = re.search(
        r"^\s*[A-Za-z_]\w*[\[\{]", flowchart_block, re.MULTILINE
    )
    first_click = re.search(r"^\s*click\s+\w", flowchart_block, re.MULTILINE)
    assert first_node_decl and first_click, (
        "the flowchart example must declare nodes and emit at least one click directive"
    )
    assert first_node_decl.start() < first_click.start(), (
        "the flowchart example emits a click before its node declarations — "
        "mermaid silently drops it and the example generates zero anchors"
    )


def test_state_diagram_example_emits_click_after_declaration():
    """#46: the stateDiagram-v2 example's click follows the state it names.

    stateDiagram-v2 creates states lazily, so ordering is not a parse hazard the
    way it is for classDiagram/flowchart — but the worked example should still
    model the emit-after-declaration convention consistently.
    """
    text = _template_text()
    state_block = _worked_example_block(text, "stateDiagram-v2")
    assert state_block, "template.md has no stateDiagram-v2 worked example"
    first_transition = re.search(r"-->", state_block)
    first_click = re.search(r"^\s*click\s+\w", state_block, re.MULTILINE)
    assert first_transition and first_click, (
        "the stateDiagram-v2 example must declare a transition and emit a click"
    )
    assert first_transition.start() < first_click.start(), (
        "the stateDiagram-v2 example emits its click before any state is declared"
    )


# ── describe('template.md enforcement annotations') ─────────────────────────


def test_demonstrates_authz_note_with_mechanism_and_rejection():
    """#46: an authZ Note states its mechanism and rejection behaviour."""
    notes = _note_lines(_template_text())
    authz_notes = [n for n in notes if re.search(r"auth", n, re.IGNORECASE)]
    assert authz_notes, "no Note annotation mentions AuthZ"
    assert any(
        re.search(r"(—|-)[^\n]*\b(401|invalid|reject)", n, re.IGNORECASE)
        or re.search(r"\btoken\b", n, re.IGNORECASE)
        for n in authz_notes
    ), "no AuthZ Note states a mechanism together with a rejection outcome"


def test_demonstrates_validation_note_with_rule_and_rejection():
    """#46: a validation Note states its rule and rejection behaviour."""
    notes = _note_lines(_template_text())
    validation_notes = [n for n in notes if re.search(r"valid", n, re.IGNORECASE)]
    assert validation_notes, "no Note annotation mentions validation"
    assert any(
        re.search(r"\b400\b", n) or re.search(r"field error", n, re.IGNORECASE)
        for n in validation_notes
    ), "no validation Note states a rejection behaviour (e.g. 400, field errors)"


def test_demonstrates_external_call_note_with_safeguard():
    """#46: an external-call Note states its safeguard (SSRF/allowlist/timeout)."""
    notes = _note_lines(_template_text())
    external_notes = [
        n
        for n in notes
        if re.search(r"ssrf|external|allowlist", n, re.IGNORECASE)
    ]
    assert external_notes, "no Note annotation covers an external-call boundary"
    assert any(
        re.search(r"allowlist|timeout|retry", n, re.IGNORECASE) for n in external_notes
    ), "no external-call Note states a concrete safeguard"


def test_demonstrates_error_propagation_note_with_code_and_recovery():
    """#46: an error-propagation Note states its code and recovery behaviour."""
    notes = _note_lines(_template_text())
    error_notes = [
        n for n in notes if re.search(r"error propagation|AppError", n, re.IGNORECASE)
    ]
    assert error_notes, "no Note annotation covers error propagation"
    assert any(
        re.search(r"\b500\b", n) or re.search(r"correlation", n, re.IGNORECASE)
        for n in error_notes
    ), "no error-propagation Note states a code/recovery behaviour"


def test_states_adjacency_rule():
    """#46: the adjacency rule — annotations sit beside the interaction, never in a legend."""
    text = _template_text()
    assert re.search(r"adjacen", text, re.IGNORECASE), (
        "template.md does not name the adjacency rule"
    )
    assert re.search(rf"{NEGATION}in a legend", text, re.IGNORECASE), (
        "template.md does not state that annotations belong beside the interaction, "
        "not in a legend block"
    )


def test_states_semicolon_in_note_text_is_a_parse_error():
    """#46 (D4): the rule that a `;` in Note text is a Mermaid parse error, with its reason."""
    text = _template_text()
    assert re.search(
        r";[^\n]{0,80}parse error", text, re.IGNORECASE
    ) or re.search(
        r"parse error[^\n]{0,80};", text, re.IGNORECASE
    ), "template.md does not state that a semicolon in Note text is a parse error"
    assert re.search(
        r"(terminate|statement separator|ends?)[^\n]{0,60}note", text, re.IGNORECASE
    ) or re.search(
        r"note[^\n]{0,60}(terminate|statement separator|ends? early)", text, re.IGNORECASE
    ), "template.md does not state the reason (a semicolon terminates the note early)"


def test_uses_no_semicolon_in_any_note_example():
    """#46 (D4): no `Note` line anywhere in template.md's worked examples contains a `;`.

    Extracted by line-regex over the whole file (not fence parsing), since some
    worked examples are shown with an escaped fence prefix rather than inside a
    live ```mermaid fence.
    """
    notes = _note_lines(_template_text())
    assert notes, "template.md has no Note annotations to check"
    offending = [n for n in notes if ";" in n]
    assert not offending, (
        f"found `;` inside Note text — a Mermaid parse error (D4): {offending}"
    )
