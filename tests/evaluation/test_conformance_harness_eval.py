"""Evaluator audit for issue #47 (renderer conformance fixture, harness, report).

`check-diagrams.mjs`'s `checkAnchorsRendered` makes exactly one render pass per block
and derives *two* independent assertions from it (see its docstring in
`tests/conformance/check-diagrams.mjs`):

    ok = anchors === clicks && styledRoles.length === roles.length
         \\_________________/    \\_____________________________/
              D5 half                       D6 half

`test_conformance_harness.py` (written by edf:test-author) exercises the D5 half
directly (`test_click_before_node_declaration_is_reported_as_a_failure_not_a_pass`)
but has no test that exercises the D6 half: a block whose `class X role` statement
names a palette role the block never declares via `classDef`. Per D6 (LLD
`lld-v1-e1-1-template-vocabulary.md`), this parses and renders cleanly and applies
*no* styling at all — the same "reads fine, parses fine, produces nothing" failure
class D5 exists to catch, just on the other half of the same boolean expression. A
regression that always evaluated the `styledRoles` clause as `true` (e.g. an
accidentally-inverted `.filter` predicate) would not be caught by any existing test,
because every block in the committed fixture and template.md already declares the
`classDef` it uses (D6 was fixed forward, not left to regress silently).

This closes that gap directly against the harness's public CLI/JSON contract, the
same way the sibling D5 test does.
"""

import pytest

from tests.test_conformance_harness import (
    _first_file_entry,
    _run_harness_json,
    _write_fixture,
    skip_if_no_node_toolchain,
)


@skip_if_no_node_toolchain
def test_class_referencing_undeclared_classdef_role_is_reported_as_a_failure(tmp_path):
    """#47/D6 gap: a `class X role` with no matching `classDef` in the same block
    renders with zero styling for that role and must fail the run — mirrors the D5
    click-before-declaration test that already exists, but for the styledRoles half
    of `checkAnchorsRendered`'s combined assertion."""
    design_root = tmp_path
    doc = _write_fixture(
        design_root,
        "doc.md",
        "```mermaid\n"
        "flowchart TD\n"
        '    A["Node"]\n'
        "    class A new\n"  # references role "new" -- no classDef "new" in this block
        "```\n",
    )
    result, data = _run_harness_json(doc, design_root=design_root)
    entry = _first_file_entry(data)
    rendered = entry["rendered"]
    assert rendered, f"no RenderResult reported for the flowchart block: {entry!r}"
    block = rendered[0]
    assert block["roles"] == ["new"], f"expected role 'new' to be referenced, got {block!r}"
    assert block["styledRoles"] == [], (
        "a role referenced without a matching classDef in the same block was reported "
        f"as styled: {block!r}"
    )
    assert block["ok"] is False, (
        f"a block whose referenced role has no classDef in the same block was not "
        f"reported as failing: {block!r}"
    )
    assert result.returncode != 0, (
        "harness exited 0 on a D6 violation (class role with no matching classDef "
        "in the same block)"
    )


@skip_if_no_node_toolchain
@pytest.mark.parametrize("role", ["error", "auth", "external", "new"])
def test_undeclared_classdef_is_caught_for_every_palette_role(tmp_path, role):
    """#47/D6, regression: the D6 check must fail for EVERY palette role, not just the
    three whose names do not collide with mermaid's own stylesheet.

    The original `styledRoles` probe tested the SVG for a loose `\\.<role>\\b`. Mermaid
    emits built-in `.error-icon{…}` and `.error-text{…}` rules into *every* stylesheet,
    which that pattern matches — so `error`, alone among the four roles, was reported as
    styled even when the block declared no `classDef` for it, and could never fail the
    check written to catch exactly that. The probe now looks for the `.<role>>*` rule an
    applied `classDef` actually emits.

    Parametrised over all four roles deliberately: a probe that is right for three roles
    and silently exempt for the fourth is the failure this suite exists to prevent.
    """
    doc = _write_fixture(
        tmp_path,
        f"undeclared-{role}.md",
        "```mermaid\n"
        "flowchart TD\n"
        '    A["Node"] --> B["Other"]\n'
        f"    class A {role}\n"  # no classDef for `role` in this block
        "```\n",
    )
    result, data = _run_harness_json(doc, design_root=tmp_path)
    block = _first_file_entry(data)["rendered"][0]
    assert block["roles"] == [role]
    assert block["styledRoles"] == [], (
        f"role {role!r} was reported as styled despite no classDef in the block — "
        f"the mermaid built-in stylesheet collision is back: {block!r}"
    )
    assert block["ok"] is False
    assert result.returncode != 0


@skip_if_no_node_toolchain
@pytest.mark.parametrize("role", ["error", "auth", "external", "new"])
def test_declared_classdef_passes_for_every_palette_role(tmp_path, role):
    """#47/D6, positive control: the same block WITH its `classDef` must pass.

    Without this, a probe that simply never matched anything would satisfy the negative
    test above while failing every legitimate diagram.
    """
    doc = _write_fixture(
        tmp_path,
        f"declared-{role}.md",
        "```mermaid\n"
        "flowchart TD\n"
        '    A["Node"] --> B["Other"]\n'
        f"    classDef {role} fill:#d4f0d4,stroke:#2d7d2d,color:#1a3a1a\n"
        f"    class A {role}\n"
        "```\n",
    )
    result, data = _run_harness_json(doc, design_root=tmp_path)
    block = _first_file_entry(data)["rendered"][0]
    assert block["styledRoles"] == [role], (
        f"role {role!r} declared via classDef in the same block was not detected as "
        f"styled: {block!r}"
    )
    assert block["ok"] is True
    assert result.returncode == 0


@skip_if_no_node_toolchain
def test_unterminated_mermaid_fence_is_reported(tmp_path):
    """#47: a mermaid fence left open at EOF must fail the run rather than vanish.

    An earlier implementation dropped the block silently, so a truncated diagram passed
    every check with no diagnostic — the same silent no-op the harness exists to catch.
    """
    doc = _write_fixture(
        tmp_path,
        "unterminated.md",
        "```mermaid\nflowchart TD\n    A[\"a\"] --> B[\"b\"]\n",
    )
    result, data = _run_harness_json(doc, design_root=tmp_path)
    entry = _first_file_entry(data)
    assert entry["unterminatedBlocks"], (
        f"an unterminated mermaid fence was not reported: {entry!r}"
    )
    assert result.returncode != 0
