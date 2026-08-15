"""Evaluator audit for issue #46 (LLD template gates/palette/annotations).

test_lld_template_gates_palette_annotations.py (written by edf:test-author) checks
that each conditional diagram type's section contains a "When required" heading and,
*somewhere in that whole section*, a content-signal keyword. It does the same for
"When optional". Because both checks search the same combined section text, a
template edit that swapped the two clauses' content (content signal moved under
"When optional", generic exclusion prose moved under "When required") would still
satisfy every existing assertion — the keywords are still present in the section,
just under the wrong heading. This is exactly the failure mode the epic exists to
catch: a rule that reads correctly and still says nothing, because nothing checks
which clause a signal actually lives in.

These tests close that gap by scoping the content-signal assertion to the text
between "When required:" and "When optional:" specifically, for each of the four
conditional diagram types.
"""

import re

from tests.test_lld_template_gates_palette_annotations import (
    _section_for_type,
    _template_text,
)

CONTENT_SIGNAL_PATTERNS = {
    "stateDiagram-v2": r"(non-trivial|retry|optimistic|polling)",
    "erDiagram": r"((new )?table|FK relationship|foreign.key)",
    "flowchart": r"((two|2|multiple) or more conditions|branches on (two|2|multiple))",
    "classDiagram": r"((new )?module|module boundary|dependency between)",
}


def _when_required_clause(section):
    """Return only the text between 'When required:' and the next 'When optional:'.

    Mirrors the structure every gate section in template.md actually uses --
    a "When required" paragraph followed by a "When optional" paragraph -- so
    that a content-signal assertion can be pinned to the correct clause instead
    of matching anywhere in the section.
    """
    match = re.search(
        r"when required\**:?\s*(.*?)(?=when optional\**:?|\Z)",
        section,
        re.IGNORECASE | re.DOTALL,
    )
    assert match, "no 'When required' clause found to scope the content signal to"
    return match.group(1)


def test_state_gate_content_signal_lives_in_when_required_clause():
    """#46 gap: the transition-related signal must sit under 'When required', not merely
    somewhere in the stateDiagram-v2 section (which also includes 'When optional')."""
    section = _section_for_type(_template_text(), "stateDiagram-v2")
    required_clause = _when_required_clause(section)
    assert re.search(CONTENT_SIGNAL_PATTERNS["stateDiagram-v2"], required_clause, re.IGNORECASE), (
        "stateDiagram-v2's content signal does not appear under its 'When required' "
        "clause specifically -- a swap with 'When optional' would pass the existing test"
    )


def test_er_gate_content_signal_lives_in_when_required_clause():
    """#46 gap: same scoping check for the erDiagram gate."""
    section = _section_for_type(_template_text(), "erDiagram")
    required_clause = _when_required_clause(section)
    assert re.search(CONTENT_SIGNAL_PATTERNS["erDiagram"], required_clause, re.IGNORECASE), (
        "erDiagram's content signal does not appear under its 'When required' clause "
        "specifically -- a swap with 'When optional' would pass the existing test"
    )


def test_flowchart_gate_content_signal_lives_in_when_required_clause():
    """#46 gap: same scoping check for the flowchart gate."""
    section = _section_for_type(_template_text(), "flowchart")
    required_clause = _when_required_clause(section)
    assert re.search(CONTENT_SIGNAL_PATTERNS["flowchart"], required_clause, re.IGNORECASE), (
        "flowchart's content signal does not appear under its 'When required' clause "
        "specifically -- a swap with 'When optional' would pass the existing test"
    )


def test_classdiagram_gate_content_signal_lives_in_when_required_clause():
    """#46 gap: same scoping check for the classDiagram gate."""
    section = _section_for_type(_template_text(), "classDiagram")
    required_clause = _when_required_clause(section)
    assert re.search(CONTENT_SIGNAL_PATTERNS["classDiagram"], required_clause, re.IGNORECASE), (
        "classDiagram's content signal does not appear under its 'When required' clause "
        "specifically -- a swap with 'When optional' would pass the existing test"
    )
