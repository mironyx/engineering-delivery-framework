"""Validate LLD template link forms, support matrix, and anchor conventions.

Covers issue #45: migrate `edf://` scheme references in
`plugins/edf/skills/lld/template.md` to document-relative paths, state the
`design-root` containment rule, the two-parse-error support matrix, the
sequence `link` directive convention, the `#LLD-` anchor form, and the
`classDiagram` display-label workaround.

Assertions are semantic (token/regex based) rather than exact-sentence
matches, since the normative wording is subject to review edits. See
plugins/edf/docs/design/v1/lld-v1-e1-1-template-vocabulary.md Part B,
"Normative content to add", for the source wording these tests are derived
from.
"""

import json
import pathlib
import re

PLUGIN_ROOT = pathlib.Path(__file__).resolve().parent.parent / "plugins" / "edf"
TEMPLATE_PATH = PLUGIN_ROOT / "skills" / "lld" / "template.md"
REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
PLUGIN_JSON_PATH = PLUGIN_ROOT / ".claude-plugin" / "plugin.json"
MARKETPLACE_JSON_PATH = REPO_ROOT / ".claude-plugin" / "marketplace.json"

KNOWN_DIAGRAM_TYPES = [
    "flowchart",
    "classDiagram",
    "stateDiagram-v2",
    "erDiagram",
    "sequenceDiagram",
]


def _template_text():
    return TEMPLATE_PATH.read_text(encoding="utf-8")


def _support_matrix_block(text):
    """Extract the support-matrix section from the template text.

    Bounded from the "Support matrix" heading/label to the next markdown
    heading line (a line starting with `#`), which is where the section ends.
    """
    match = re.search(
        r"Support matrix\b.*?(?=\n#{1,6}\s|\Z)", text, re.IGNORECASE | re.DOTALL
    )
    assert match, "template.md has no 'Support matrix' section"
    return match.group(0)


def _support_matrix_rows(text):
    """Return only the markdown table rows of the support matrix.

    Prose in the section is deliberately excluded: the surrounding paragraphs
    discuss parse errors (and, elsewhere in the document, explicitly state that
    the `link` directive is NOT one), so counting phrase occurrences across the
    whole section would be measuring the wrong thing. A row is a line starting
    with `|`; the header and delimiter rows are dropped.
    """
    rows = [
        line
        for line in _support_matrix_block(text).splitlines()
        if line.lstrip().startswith("|")
    ]
    return [
        row
        for row in rows
        if not re.fullmatch(r"[|\s:-]+", row) and "Diagram type" not in row
    ]


# A rule is only encoded if the document cannot also be read as stating its
# opposite. `not permitted` contains `permitted`, so a bare substring search
# cannot tell the adopted rule from the superseded ADR-0039 ban it replaces.
NEGATION = r"(?<!not )(?<!never )(?<!isn't )(?<!aren't )"


# ── describe('template.md link forms') ──────────────────────────────────────


def test_contains_no_edf_scheme_occurrence():
    """#45: the retired edf:// scheme must not remain anywhere in template.md."""
    text = _template_text()
    assert "edf://" not in text, "template.md still contains an edf:// occurrence"


def test_states_path_form_as_document_relative_with_dotdot_permitted():
    """#45: path form is stated as document-relative, with `..` permitted."""
    text = _template_text()
    assert re.search(r"document-relative", text, re.IGNORECASE), (
        "template.md does not state the document-relative path form"
    )
    # Direction matters: "`..` segments are not permitted" is the superseded
    # ADR-0039 rule, so the negated form must NOT satisfy this assertion.
    assert re.search(rf"\.\.[^\n]{{0,60}}{NEGATION}permitted", text, re.IGNORECASE), (
        "template.md does not state that `..` segments are permitted"
    )
    assert not re.search(
        r"\.\.[^\n]{0,60}(not permitted|never permitted|no `?\.\.`? segments)",
        text,
        re.IGNORECASE,
    ), "template.md still states the superseded rule banning `..` segments"


def test_bans_leading_slash_in_click_href():
    """#45: a leading slash in a click href path is explicitly disallowed."""
    text = _template_text()
    assert re.search(
        r"leading slash[^\n]{0,60}(not permitted|banned|prohibited|disallowed)",
        text,
        re.IGNORECASE,
    ), "template.md does not ban a leading slash in the path form"


def test_requires_click_href_to_resolve_inside_design_root():
    """#45: a click href must resolve inside design-root and name an existing file."""
    text = _template_text()
    assert re.search(
        r"(resolve|lie|lies)[^\n]{0,40}inside[^\n]{0,20}design-root",
        text,
        re.IGNORECASE,
    ), "template.md does not require the resolved path to lie inside design-root"
    assert re.search(r"name[^\n]{0,20}file[^\n]{0,20}exist", text, re.IGNORECASE), (
        "template.md does not require the resolved path to name a file that exists"
    )


def test_defines_design_root_and_names_single_module_default():
    """#45: design-root is defined; the single-module default is the repo root."""
    text = _template_text()
    assert re.search(r"design-root", text), "template.md never defines design-root"
    assert re.search(
        r"single-module[\s\S]{0,80}(repository root|repo root)",
        text,
        re.IGNORECASE,
    ), "template.md does not name the repository root as the single-module default"


def test_states_lld_anchor_form_including_epic_id():
    """#45: the #LLD- anchor form is LLD-<epic-id>-<section-slug>, epic id included."""
    text = _template_text()
    assert re.search(r"LLD-<epic-id>-<section-slug>", text), (
        "template.md does not state the LLD-<epic-id>-<section-slug> anchor form"
    )
    assert re.search(r"epic id", text, re.IGNORECASE), (
        "template.md does not explain that the anchor form includes the epic id"
    )


def test_states_fragment_with_no_target_is_silent_noop():
    """#45: a #LLD- fragment with no matching target is documented as a silent no-op."""
    text = _template_text()
    assert re.search(rf"{NEGATION}a silent no-op", text, re.IGNORECASE), (
        "template.md does not state that a fragment with no matching target "
        "is a silent no-op"
    )
    # The point of the rule is that nothing surfaces the failure. If the
    # document claims an error is raised, it is stating the opposite rule.
    assert not re.search(
        r"no (matching )?target[^\n]{0,80}(raises|throws|is an error)",
        text,
        re.IGNORECASE,
    ), "template.md claims a targetless fragment errors — it is a silent no-op"


def test_states_classdiagram_display_label_workaround_for_slash_identifiers():
    """#45: identifiers containing `/` need a display-label workaround in classDiagram."""
    text = _template_text()
    assert re.search(r"display label", text, re.IGNORECASE), (
        "template.md does not describe a display-label workaround"
    )
    assert re.search(
        r"identifier[\s\S]{0,60}(/|slash)[\s\S]{0,40}parse error", text, re.IGNORECASE
    ) or re.search(
        r"parse error[\s\S]{0,80}identifier[\s\S]{0,20}(/|slash)", text, re.IGNORECASE
    ), "template.md does not tie a parse error to identifiers containing `/`"


# ── describe('template.md support matrix') ───────────────────────────────────


def test_lists_exactly_two_parse_error_cases():
    """#45: the support matrix marks exactly two diagram/click combinations as parse errors.

    Counts rows in the matrix keyed by a known diagram-type name that also
    carry "parse error" on the same table row/line — not prose occurrences of
    the phrase elsewhere in the document (e.g. the `link`-directive discussion,
    which explicitly is NOT a parse error).
    """
    text = _template_text()
    rows = _support_matrix_rows(text)
    count = 0
    matched_types = []
    for diagram_type in KNOWN_DIAGRAM_TYPES:
        for row in rows:
            if diagram_type in row and re.search(r"parse error", row, re.IGNORECASE):
                count += 1
                matched_types.append(diagram_type)
                break
    assert count == 2, (
        f"expected exactly two parse-error cases in the support matrix, "
        f"found {count}: {matched_types}"
    )


def test_marks_sequence_diagram_click_as_fatal_parse_error():
    """#45: sequenceDiagram + click is marked as a fatal parse error in the matrix."""
    text = _template_text()
    seq_lines = [row for row in _support_matrix_rows(text) if "sequenceDiagram" in row]
    assert seq_lines, "support matrix has no sequenceDiagram row"
    assert any(
        re.search(r"fatal parse error", line, re.IGNORECASE) for line in seq_lines
    ), "support matrix does not mark sequenceDiagram click as a fatal parse error"


def test_marks_state_diagram_self_as_parse_error():
    """#45: stateDiagram-v2 with a `_self` click argument is marked as a parse error."""
    text = _template_text()
    state_lines = [
        row for row in _support_matrix_rows(text) if "stateDiagram-v2" in row
    ]
    assert state_lines, "support matrix has no stateDiagram-v2 row"
    assert any(
        "_self" in line and re.search(r"parse error", line, re.IGNORECASE)
        for line in state_lines
    ), "support matrix does not mark stateDiagram-v2 _self as a parse error"


def test_marks_er_diagram_as_parsing_with_no_anchor():
    """#45: erDiagram click parses but generates no anchor (not a parse error)."""
    text = _template_text()
    er_lines = [row for row in _support_matrix_rows(text) if "erDiagram" in row]
    assert er_lines, "support matrix has no erDiagram row"
    assert any(re.search(r"no anchor", line, re.IGNORECASE) for line in er_lines), (
        "support matrix does not mark erDiagram as parsing with no anchor"
    )
    assert not any(
        re.search(r"parse error", line, re.IGNORECASE) for line in er_lines
    ), "support matrix incorrectly marks erDiagram as a parse error"


def test_documents_sequence_link_directive_as_convention_not_parse_error():
    """#45: the omitted sequence `link` directive is a convention, not a parse error (D2)."""
    text = _template_text()
    # Scope the check to the section that owns the rule, so a stray "link" and
    # a stray "convention" elsewhere in the document cannot satisfy it.
    section = re.search(
        r"#+[^\n]*`?link`? directive.*?(?=\n#{1,6}\s|\Z)",
        text,
        re.IGNORECASE | re.DOTALL,
    )
    assert section, "template.md has no section covering the sequence `link` directive"
    block = section.group(0)

    assert re.search(rf"{NEGATION}a convention", block, re.IGNORECASE), (
        "the link-directive section does not describe the omission as a convention"
    )
    assert re.search(rf"{NEGATION}parses successfully", block, re.IGNORECASE), (
        "the link-directive section does not state that it parses successfully "
        "(measured, mermaid 11.12.2 — decision D2)"
    )
    assert re.search(r"not a parse (error|rule)", block, re.IGNORECASE), (
        "the link-directive section does not explicitly state the omission is "
        "NOT a parse error/rule"
    )
    # D2 is precisely that this is not an error. Guard the inversion.
    assert not re.search(
        r"`?link`?[^\n]{0,60}is a (fatal )?parse error", block, re.IGNORECASE
    ), "template.md calls the link directive a parse error — D2 measured that it parses"


# ── LLD Invariant 6 ───────────────────────────────────────────────────────────


def test_plugin_json_and_marketplace_json_versions_match():
    """LLD Invariant 6: plugin.json version equals the marketplace.json edf entry version."""
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


def test_states_click_must_follow_node_declaration():
    """#45 (ADR-0039 R4): a click before its node declaration is silently dropped.

    Measured on mermaid 11.12.2: the same classDiagram yields 3 anchors with the
    click lines last and 0 with them first, and BOTH orderings parse. A
    parse-only check cannot catch it, so the rule has to be stated.
    """
    text = _template_text()
    assert re.search(
        r"click[^\n]{0,80}(after|last)[\s\S]{0,200}(declar|class)", text, re.IGNORECASE
    ) or re.search(
        r"(declar)[\s\S]{0,200}before[\s\S]{0,80}click", text, re.IGNORECASE
    ), "template.md does not state that a click must follow its node declaration"
    assert re.search(r"silently dropped|no anchor at all", text, re.IGNORECASE), (
        "template.md does not state that an out-of-order click fails silently"
    )


def test_classdiagram_example_emits_clicks_after_declarations():
    """#45 (ADR-0039 R4): the worked example must obey its own ordering rule.

    This is the example every generated LLD is copied from, so an ordering
    mistake here propagates as zero working links in every downstream document.
    """
    text = _template_text()
    block = re.search(r"\nclassDiagram\n.*?\n`", text, re.DOTALL)
    assert block, "template.md has no classDiagram worked example"
    body = block.group(0)

    first_class = re.search(r"^\s*class\s+\w", body, re.MULTILINE)
    first_click = re.search(r"^\s*click\s+\w", body, re.MULTILINE)
    assert first_class and first_click, (
        "the classDiagram example must declare classes and emit click directives"
    )
    assert first_class.start() < first_click.start(), (
        "the classDiagram example emits a click before its class declarations — "
        "mermaid silently drops it and the example generates zero anchors"
    )
