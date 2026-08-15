"""Tests for the renderer conformance harness, fixture and report (issue #47).

Drives `tests/conformance/check-diagrams.mjs` (a Node ESM CLI, still stubbed —
every exported function `throw`s `not implemented`) through its public CLI
contract:

    node tests/conformance/check-diagrams.mjs [--design-root <dir>] [--json] <file.md> [...]
    exit 0 = all checks passed; exit 1 = at least one check failed; exit 2 = usage error.

With `--json` the harness prints one JSON object to stdout:
    { "ok": bool, "files": [ { "path": str, "blocks": [...], "paths": [...],
      "anchors": [...], "rendered": [...], "sanitizer": [...] } ] }

See `plugins/edf/docs/design/v1/lld-v1-e1-1-template-vocabulary.md` §1.3 and
§B.1.3 ("Renderer conformance evidence") for the contract these tests are
derived from, and decisions D1-D6 for the specific failure modes (nested `..`
paths, the sanitizer gates, click-before-declaration silently dropping an
anchor).

The harness tests (`TestConformanceHarness`) require `node` and the installed
`tests/conformance/node_modules` and are skipped when either is absent. The
report and fixture content tests are pure markdown assertions against
committed artefacts and always run.
"""

import json
import pathlib
import re
import shutil
import subprocess

import pytest

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
CONFORMANCE_DIR = REPO_ROOT / "tests" / "conformance"
HARNESS_PATH = CONFORMANCE_DIR / "check-diagrams.mjs"
NODE_MODULES_DIR = CONFORMANCE_DIR / "node_modules"
FIXTURE_PATH = REPO_ROOT / "plugins" / "edf" / "docs" / "design" / "v1" / "conformance-fixture.md"
REPORT_PATH = REPO_ROOT / "plugins" / "edf" / "docs" / "design" / "v1" / "renderer-conformance-report.md"

NODE_BIN = shutil.which("node")

HARNESS_TIMEOUT = 120  # mermaid.render is slow; generous per test-author brief

KNOWN_DIAGRAM_TYPES = [
    "flowchart",
    "classDiagram",
    "stateDiagram-v2",
    "erDiagram",
    "sequenceDiagram",
]

skip_if_no_node_toolchain = pytest.mark.skipif(
    NODE_BIN is None or not NODE_MODULES_DIR.is_dir(),
    reason="node or tests/conformance/node_modules is unavailable on this machine",
)


# ── helpers ──────────────────────────────────────────────────────────────────


def _run_harness(*files, design_root=None, json_output=True, timeout=HARNESS_TIMEOUT):
    """Invoke the harness CLI against `files` and return the CompletedProcess.

    `HARNESS_PATH` is passed as an absolute path so Node resolves the ESM
    imports (and therefore `node_modules`) relative to the script's own
    directory regardless of the caller's cwd.
    """
    cmd = [NODE_BIN, str(HARNESS_PATH)]
    if design_root is not None:
        cmd += ["--design-root", str(design_root)]
    if json_output:
        cmd.append("--json")
    cmd += [str(f) for f in files]
    return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)


def _run_harness_json(*files, design_root=None, timeout=HARNESS_TIMEOUT):
    """Invoke the harness with --json and return (CompletedProcess, parsed dict)."""
    result = _run_harness(*files, design_root=design_root, json_output=True, timeout=timeout)
    assert result.stdout.strip(), (
        f"harness produced no stdout for --json invocation; stderr={result.stderr!r}"
    )
    data = json.loads(result.stdout)
    return result, data


def _first_file_entry(data):
    assert data.get("files"), f"--json output has no 'files' entries: {data!r}"
    return data["files"][0]


def _write_fixture(tmp_path, name, content):
    doc = tmp_path / name
    doc.write_text(content, encoding="utf-8")
    return doc


def _report_text():
    assert REPORT_PATH.exists(), (
        f"{REPORT_PATH} does not exist yet — it is a T3 deliverable "
        "(issue #47) that this test drives"
    )
    return REPORT_PATH.read_text(encoding="utf-8")


def _fixture_text():
    assert FIXTURE_PATH.exists(), f"{FIXTURE_PATH} does not exist"
    return FIXTURE_PATH.read_text(encoding="utf-8")


def _extract_mermaid_block(text, diagram_type):
    """Return the body of the first ```mermaid fence whose first statement is
    `diagram_type`, or None if no such block exists."""
    pattern = re.compile(
        r"```mermaid\s*\n\s*" + re.escape(diagram_type) + r"\b.*?\n```",
        re.DOTALL,
    )
    match = pattern.search(text)
    return match.group(0) if match else None


# ── describe('conformance harness') — issue #47 ─────────────────────────────


@skip_if_no_node_toolchain
class TestConformanceHarness:
    def test_parses_every_fenced_mermaid_block_in_the_fixture(self):
        """#47: the harness exits 0 when run against the real, well-formed fixture."""
        result = _run_harness(FIXTURE_PATH, design_root=REPO_ROOT, json_output=False)
        assert result.returncode == 0, (
            f"harness did not exit 0 on the conformance fixture; "
            f"stdout={result.stdout!r} stderr={result.stderr!r}"
        )

    def test_exits_non_zero_when_a_fixture_diagram_fails_to_parse(self, tmp_path):
        """#47: a diagram that fails to parse (D4: `;` inside a sequenceDiagram Note) fails the run."""
        broken = _write_fixture(
            tmp_path,
            "broken.md",
            "```mermaid\n"
            "sequenceDiagram\n"
            "    participant A\n"
            "    Note over A: mechanism; rejection\n"
            "```\n",
        )
        result = _run_harness(broken, design_root=tmp_path, json_output=False)
        assert result.returncode != 0, (
            "harness exited 0 on a diagram with a `;` inside a Note, which D4 "
            "measured as a Mermaid parse error"
        )

    def test_reports_a_click_href_that_resolves_outside_design_root(self, tmp_path):
        """#47/D1: a click href escaping design-root is reported, not silently accepted."""
        design_root = tmp_path / "root"
        nested_doc_dir = design_root / "a" / "b"
        nested_doc_dir.mkdir(parents=True)
        doc = _write_fixture(
            nested_doc_dir,
            "doc.md",
            "```mermaid\n"
            "flowchart TD\n"
            '    A["Node"]\n'
            '    click A href "../../../outside.md" _self\n'
            "```\n",
        )
        result, data = _run_harness_json(doc, design_root=design_root)
        entry = _first_file_entry(data)
        matches = [p for p in entry["paths"] if p["href"] == "../../../outside.md"]
        assert matches, f"no PathResult reported for the escaping href: {entry['paths']!r}"
        assert matches[0]["inside"] is False, "escaping href was reported as inside design-root"
        assert matches[0]["ok"] is False
        assert result.returncode != 0

    def test_reports_a_click_href_pointing_at_a_non_existent_file(self, tmp_path):
        """#47: a click href resolving inside design-root but naming no file is reported."""
        design_root = tmp_path
        doc = _write_fixture(
            design_root,
            "doc.md",
            "```mermaid\n"
            "flowchart TD\n"
            '    A["Node"]\n'
            '    click A href "does-not-exist.md" _self\n'
            "```\n",
        )
        result, data = _run_harness_json(doc, design_root=design_root)
        entry = _first_file_entry(data)
        matches = [p for p in entry["paths"] if p["href"] == "does-not-exist.md"]
        assert matches, f"no PathResult reported for the dangling href: {entry['paths']!r}"
        assert matches[0]["exists"] is False
        assert matches[0]["ok"] is False
        assert result.returncode != 0

    def test_confirms_dotdot_paths_and_lld_fragments_survive_the_sanitizer(self, tmp_path):
        """#47/D3: `..` paths and `#LLD-` fragments are not stripped by the sanitizer gates."""
        design_root = tmp_path
        doc = _write_fixture(
            design_root,
            "doc.md",
            "```mermaid\n"
            "flowchart TD\n"
            '    A["Node"]\n'
            '    B["Other"]\n'
            '    click A href "../../skills/lld/template.md" _self\n'
            '    click B href "#LLD-v1-e1-1-fixture" _self\n'
            "```\n",
        )
        _, data = _run_harness_json(doc, design_root=design_root)
        entry = _first_file_entry(data)
        sanitizer = entry["sanitizer"]

        dotdot_entries = [s for s in sanitizer if ".." in s["url"]]
        fragment_entries = [s for s in sanitizer if s["url"].startswith("#LLD-")]
        assert dotdot_entries, f"no sanitizer entry recorded for the `..` href: {sanitizer!r}"
        assert fragment_entries, f"no sanitizer entry recorded for the #LLD- fragment: {sanitizer!r}"
        assert all(s["survives"] for s in dotdot_entries), (
            f"a `..` path did not survive the sanitizer: {dotdot_entries!r}"
        )
        assert all(s["survives"] for s in fragment_entries), (
            f"a #LLD- fragment did not survive the sanitizer: {fragment_entries!r}"
        )

    def test_confirms_edf_scheme_is_stripped_by_the_sanitizer(self, tmp_path):
        """#47/D3: the retired edf:// scheme is stripped by the sanitizer gates."""
        design_root = tmp_path
        doc = _write_fixture(
            design_root,
            "doc.md",
            "```mermaid\n"
            "flowchart TD\n"
            '    A["Node"]\n'
            '    click A href "edf://src/lib/example/service.ts" _self\n'
            "```\n",
        )
        _, data = _run_harness_json(doc, design_root=design_root)
        entry = _first_file_entry(data)
        sanitizer = entry["sanitizer"]
        matches = [s for s in sanitizer if s["url"] == "edf://src/lib/example/service.ts"]
        assert matches, f"no sanitizer entry recorded for the edf:// href: {sanitizer!r}"
        assert all(not s["survives"] for s in matches), (
            f"edf:// was not stripped by the sanitizer: {matches!r}"
        )

    def test_strips_inline_code_and_non_mermaid_fences_before_extracting_hrefs(self, tmp_path):
        """#47 AC: documentation *about* edf:// quoted in a table cell or a non-mermaid
        fence must not be reported as a finding — a prototype without this stripping
        step produced a false positive on its own migration notes."""
        design_root = tmp_path
        doc = _write_fixture(
            design_root,
            "doc.md",
            "# Migration notes\n\n"
            "Old form (inline code): "
            '`click Service href "edf://inline-marker-should-not-be-found" "source"`\n\n'
            "```text\n"
            'click Service href "edf://fenced-marker-should-not-be-found" "source"\n'
            "```\n\n"
            "```mermaid\n"
            "flowchart TD\n"
            '    A["Node"]\n'
            '    click A href "does-not-exist.md" _self\n'
            "```\n",
        )
        _, data = _run_harness_json(doc, design_root=design_root)
        serialized = json.dumps(data)
        assert "inline-marker-should-not-be-found" not in serialized, (
            "an inline-code-span edf:// occurrence was reported as a finding"
        )
        assert "fenced-marker-should-not-be-found" not in serialized, (
            "a non-mermaid fenced-block edf:// occurrence was reported as a finding"
        )

    def test_click_before_node_declaration_is_reported_as_a_failure_not_a_pass(self, tmp_path):
        """#47/D5: a click emitted before its node declaration renders zero anchors and
        must fail the run — parse success alone is not evidence of navigability."""
        design_root = tmp_path
        doc = _write_fixture(
            design_root,
            "doc.md",
            "```mermaid\n"
            "classDiagram\n"
            '    click A href "#LLD-v1-e1-1-a" _self\n'
            '    click B href "#LLD-v1-e1-1-b" _self\n'
            "    class A\n"
            "    class B\n"
            "```\n",
        )
        result, data = _run_harness_json(doc, design_root=design_root)
        entry = _first_file_entry(data)
        rendered = entry["rendered"]
        assert rendered, f"no RenderResult reported for the classDiagram block: {entry!r}"
        block = rendered[0]
        assert block["clicks"] == 2, f"expected 2 click directives counted, got {block!r}"
        assert block["anchors"] < block["clicks"], (
            "rendered anchor count was not lower than click count for a click "
            f"emitted before its node declaration: {block!r}"
        )
        assert block["ok"] is False, (
            f"a block with fewer rendered anchors than clicks was not reported as failing: {block!r}"
        )
        assert result.returncode != 0


# ── describe('conformance report') — issue #47 ──────────────────────────────


class TestConformanceReport:
    def test_records_a_row_per_diagram_type_per_renderer(self):
        """#47: the report records a row for every diagram type, for both renderers."""
        text = _report_text()
        for diagram_type in KNOWN_DIAGRAM_TYPES:
            assert re.search(rf"\b{re.escape(diagram_type)}\b", text), (
                f"renderer-conformance-report.md has no row for {diagram_type}"
            )
        for renderer in ["GitHub", "VSCode"]:
            assert re.search(re.escape(renderer), text, re.IGNORECASE), (
                f"renderer-conformance-report.md never mentions renderer {renderer!r}"
            )

    def test_records_the_erdiagram_and_sequencediagram_negative_cases(self):
        """#47: the report records the two negative cases (no click emitted, nothing broke)."""
        text = _report_text()
        assert re.search(
            r"erDiagram[\s\S]{0,300}(no click|negative|no anchor)", text, re.IGNORECASE
        ), "report does not record the erDiagram negative case"
        assert re.search(
            r"sequenceDiagram[\s\S]{0,300}(no click|negative|not (used|emitted))",
            text,
            re.IGNORECASE,
        ), "report does not record the sequenceDiagram negative case"

    def test_records_pinned_mermaid_and_vscode_versions(self):
        """#47: the report records the pinned mermaid and VS Code versions (Invariant 14)."""
        text = _report_text()
        assert re.search(r"mermaid[^\n]{0,60}11\.12\.2", text, re.IGNORECASE), (
            "report does not pin mermaid 11.12.2 next to the name 'mermaid'"
        )
        assert re.search(r"(vs\s?code)[^\n]{0,60}1\.121", text, re.IGNORECASE), (
            "report does not pin VS Code 1.121 next to the name 'VS Code'"
        )

    def test_records_a_reverification_trigger_naming_both_versions(self):
        """#47: the report states a re-verification trigger naming both pinned versions
        (Invariant 15) — a change to either pinned version invalidates the report."""
        text = _report_text()
        trigger_match = re.search(r"[^\n]*re-?verif[a-z]*[^\n]*", text, re.IGNORECASE)
        assert trigger_match, "report has no re-verification trigger sentence"
        window_start = max(0, trigger_match.start() - 300)
        window_end = min(len(text), trigger_match.end() + 300)
        window = text[window_start:window_end]
        assert "11.12.2" in window, (
            "the re-verification trigger does not name the pinned mermaid version"
        )
        assert re.search(r"1\.121", window), (
            "the re-verification trigger does not name the pinned VS Code version"
        )

    def test_records_the_vscode_native_open_finding_as_yes_or_no(self):
        """#47: the VSCode native-open finding is recorded as `yes` or `no` — never
        absent, never 'unknown' (Invariant 16)."""
        text = _report_text()
        finding_match = re.search(r"[^\n]*native[- ]open[^\n]*", text, re.IGNORECASE)
        assert finding_match, "report has no VSCode native-open finding row"
        row = finding_match.group(0)
        assert not re.search(r"unknown", row, re.IGNORECASE), (
            f"native-open finding row states 'unknown' rather than yes/no: {row!r}"
        )
        value_match = re.search(r"\b(yes|no)\b", row, re.IGNORECASE)
        assert value_match, f"native-open finding row has no yes/no value: {row!r}"
        assert value_match.group(1).lower() in {"yes", "no"}

    def test_records_the_nested_depth_relative_link_result(self):
        """#47/D1: the report records the nested-path (>= 3 `..` segments) result —
        the row that would have caught the ADR-0039 defect (Invariant 18)."""
        text = _report_text()
        assert re.search(r"(\.\./){3,}", text) or re.search(
            r"nested[- ](depth|path)", text, re.IGNORECASE
        ), "report does not record a nested-depth (>= 3 `..`) relative link result"

    def test_records_palette_distinguishability_for_all_four_colours_in_each_renderer(self):
        """#47 AC: the report records the palette-distinguishability observation for
        all four colours (error/auth/external/new), for each renderer."""
        text = _report_text()
        for role in ["error", "auth", "external", "new"]:
            assert re.search(rf"\b{role}\b", text, re.IGNORECASE), (
                f"report never mentions palette role {role!r}"
            )
        assert re.search(r"distinguish", text, re.IGNORECASE), (
            "report has no palette-distinguishability observation"
        )
        for renderer in ["GitHub", "VSCode"]:
            assert re.search(re.escape(renderer), text, re.IGNORECASE), (
                f"report's distinguishability observation is missing renderer {renderer!r}"
            )


# ── describe('conformance fixture') — issue #47 ─────────────────────────────


class TestConformanceFixture:
    def test_contains_one_diagram_of_each_of_the_five_types(self):
        """#47 AC: the fixture contains one diagram per type."""
        text = _fixture_text()
        for diagram_type in KNOWN_DIAGRAM_TYPES:
            assert _extract_mermaid_block(text, diagram_type) is not None, (
                f"conformance-fixture.md has no {diagram_type} diagram"
            )

    def test_contains_both_link_forms(self):
        """#47 AC: the fixture contains both link forms — a document-relative path
        and a #LLD- fragment."""
        text = _fixture_text()
        assert re.search(r'href\s+"\.\./', text), (
            "conformance-fixture.md has no document-relative (`..`) click href"
        )
        assert re.search(r'href\s+"#LLD-', text), (
            "conformance-fixture.md has no #LLD- fragment click href"
        )

    def test_contains_erdiagram_and_sequencediagram_negative_cases(self):
        """#47 AC: an erDiagram with no click, and a sequenceDiagram with no click."""
        text = _fixture_text()
        er_block = _extract_mermaid_block(text, "erDiagram")
        seq_block = _extract_mermaid_block(text, "sequenceDiagram")
        assert er_block is not None, "conformance-fixture.md has no erDiagram block"
        assert seq_block is not None, "conformance-fixture.md has no sequenceDiagram block"
        # Match the `click` directive keyword itself, not an identifier that merely
        # contains the substring "click" (e.g. this fixture's `click_directive` entity).
        click_directive = re.compile(r"^\s*click\s+\w", re.MULTILINE)
        assert not click_directive.search(er_block), (
            "the erDiagram negative case carries a click directive"
        )
        assert not click_directive.search(seq_block), (
            "the sequenceDiagram negative case carries a click directive"
        )

    def test_contains_a_link_with_at_least_three_dotdot_segments(self):
        """#47 AC/D1: the fixture contains a nested-depth relative link (>= 3 `..`
        segments) — the case that would have caught the ADR-0039 defect."""
        text = _fixture_text()
        assert re.search(r'href\s+"(\.\./){3,}', text), (
            "conformance-fixture.md has no click href with >= 3 `..` segments"
        )
