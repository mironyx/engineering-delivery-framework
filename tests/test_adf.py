"""Tests for the Markdown to ADF converter, `md_to_adf` side (issue #128).

Covers LLD v3 E3.2 §1.1 `describe("md_to_adf")` and invariants A2 (allow-lists), A3 (purity),
A4 (no input raises) and the md_to_adf half of A5 (code block text and language survive).
Issue #129 appends the `adf_to_md` and round-trip classes (A1, A5, A6) at the end of the file.

The module is pure, so every test calls the public function directly; there is no HTTP or SDK
boundary to mock. `tests/conftest.py` puts plugins/edf/bin on sys.path.
"""

from __future__ import annotations

import ast
import pathlib
import re

import pytest

import _adf
from _adf import ALLOWED_MARKS, ALLOWED_NODES, adf_to_md, md_to_adf

ADF_SOURCE = pathlib.Path(_adf.__file__)
MARK_ORDER = ["link", "strong", "em", "code"]


# --------------------------------------------------------------------------- helpers


def walk(node):
    """Yield every node in the tree, depth first, including the root."""
    yield node
    for child in node.get("content", []) or []:
        yield from walk(child)


def find(node, type_):
    return [n for n in walk(node) if n["type"] == type_]


def text_of(node) -> str:
    """Concatenate text under a node; hardBreak counts as a newline."""
    out = []
    for n in walk(node):
        if n["type"] == "text":
            out.append(n["text"])
        elif n["type"] == "hardBreak":
            out.append("\n")
    return "".join(out)


def marks_of(text_node) -> list[str]:
    return [m["type"] for m in text_node.get("marks", []) or []]


def body(markdown: str) -> list[dict]:
    return md_to_adf(markdown)["content"]


def marked(markdown: str) -> list[tuple[str, list[str]]]:
    """(text, mark types) for every text node of the document."""
    return [(n["text"], marks_of(n)) for n in find(md_to_adf(markdown), "text")]


# Every Supported construct plus the "everything else" cases.
CORPUS = {
    "heading": "# Title\n\n## Sub\n\n###### Six",
    "paragraph": "Just a paragraph.",
    "inline": "**b** and *i* and _i_ and `c` and [t](http://x.io/a)",
    "bullets": "- a\n- b\n  - nested\n- c",
    "ordered": "1. one\n2. two\n   1. inner",
    "tasks": "- [ ] open\n- [x] done",
    "fence": "```python\nprint('x')\n```",
    "table": "| a | b |\n|---|---|\n| 1 | 2 |",
    "soft": "line one\nline two",
    "hard": "line one\\\nline two",
    "html": "<div>raw <b>html</b></div>",
    "quote": "> quoted\n> text",
    "image": "![alt](http://x.io/i.png)",
    "rule": "---",
    "mixed": "# H\n\ntext **b**\n\n- x\n- y\n\n```\ncode\n```\n\n| a |\n|---|\n| 1 |",
}


# --------------------------------------------------------------------------- document shell


class TestDocShell:
    def test_emits_version_1_doc_node(self):  # #128 "emits a version-1 doc node"
        doc = md_to_adf("hello")
        assert doc["version"] == 1
        assert doc["type"] == "doc"
        assert isinstance(doc["content"], list)

    @pytest.mark.parametrize("src", ["", "   ", "\n\n", " \n \t\n"])
    def test_blank_input_is_one_empty_paragraph(self, src):  # #128
        doc = md_to_adf(src)
        assert doc["type"] == "doc" and doc["version"] == 1
        assert len(doc["content"]) == 1
        assert doc["content"][0]["type"] == "paragraph"
        assert text_of(doc["content"][0]) == ""

    def test_blank_line_separates_paragraphs(self):  # #128
        blocks = body("first\n\nsecond")
        assert [b["type"] for b in blocks] == ["paragraph", "paragraph"]
        assert [text_of(b) for b in blocks] == ["first", "second"]


# --------------------------------------------------------------------------- headings


class TestHeadings:
    @pytest.mark.parametrize("level", range(1, 7))
    def test_maps_each_heading_level(self, level):  # #128 "maps each heading level 1-6"
        blocks = body("#" * level + " Title here")
        assert len(blocks) == 1
        assert blocks[0]["type"] == "heading"
        assert blocks[0]["attrs"]["level"] == level
        assert text_of(blocks[0]) == "Title here"

    def test_seven_hashes_is_not_a_heading(self):  # #128 no invalid level is emitted
        for node in find(md_to_adf("####### too deep"), "heading"):
            assert 1 <= node["attrs"]["level"] <= 6
        assert "too deep" in text_of(md_to_adf("####### too deep"))

    def test_heading_text_gets_inline_marks(self):  # #128
        heading = body("## A **bold** word")[0]
        assert heading["type"] == "heading"
        assert ("bold", ["strong"]) in [
            (n["text"], marks_of(n)) for n in find(heading, "text")
        ]


# --------------------------------------------------------------------------- inline marks


class TestInlineMarks:
    def test_bold_italic_and_code_map_to_marks(self):  # #128 "bold, italic and inline code"
        runs = dict(marked("**b** *i* `c`"))
        assert runs["b"] == ["strong"]
        assert runs["i"] == ["em"]
        assert runs["c"] == ["code"]

    def test_underscore_italic_maps_to_em(self):  # #128
        assert ("i", ["em"]) in marked("an _i_ here")

    def test_plain_text_keeps_surrounding_runs_unmarked(self):  # #128 adjacent plain runs merged
        nodes = find(md_to_adf("a **b** c"), "text")
        assert [(n["text"], marks_of(n)) for n in nodes] == [
            ("a ", []),
            ("b", ["strong"]),
            (" c", []),
        ]

    def test_adjacent_plain_runs_are_merged(self):  # #128
        nodes = find(md_to_adf("plain text, with punctuation!"), "text")
        assert len(nodes) == 1

    def test_maps_a_link_to_a_link_mark_with_href(self):  # #128 "maps a link"
        nodes = find(md_to_adf("see [the docs](https://example.com/a?b=1) now"), "text")
        linked = [n for n in nodes if "link" in marks_of(n)]
        assert len(linked) == 1
        assert linked[0]["text"] == "the docs"
        link = next(m for m in linked[0]["marks"] if m["type"] == "link")
        assert link["attrs"]["href"] == "https://example.com/a?b=1"

    def test_code_content_is_literal(self):  # #128 inline code content is literal
        assert marked("`a*b*_c_`") == [("a*b*_c_", ["code"])]

    def test_code_mark_never_combines_with_strong_or_em(self):  # #128 Part B mark rule
        for src in ["**`c`**", "*`c`*", "***`c`***", "`c` **b**"]:
            for n in find(md_to_adf(src), "text"):
                ms = marks_of(n)
                if "code" in ms:
                    assert "strong" not in ms and "em" not in ms, src

    @pytest.mark.parametrize("src", ["[**b**](http://u)", "***x***", "[*i*](http://u)", "[***x***](http://u)"])
    def test_marks_are_emitted_in_documented_order(self, src):  # #128 link, strong, em, code
        for n in find(md_to_adf(src), "text"):
            ms = marks_of(n)
            assert ms == sorted(ms, key=MARK_ORDER.index), (src, ms)

    def test_backslash_escape_yields_literal_character(self):  # #128 backslash escapes
        assert marked(r"\*not em\*") == [("*not em*", [])]

    @pytest.mark.parametrize(
        "src",
        ["**unclosed", "*lonely", "[text](", "[text]", "`open tick", "a ** b ** c", "_x"],
    )
    def test_unmatched_delimiters_stay_literal(self, src):  # #128
        doc = md_to_adf(src)
        assert text_of(doc) == src
        assert all(not marks_of(n) for n in find(doc, "text"))


# --------------------------------------------------------------------------- GFM flanking


class TestEmphasisFlanking:
    def test_does_not_emphasise_underscores_inside_identifiers(self):  # #128
        assert marked("snake_case_name") == [("snake_case_name", [])]

    def test_identifier_inside_a_sentence_stays_plain(self):  # #128
        doc = md_to_adf("call my_func_name now")
        assert text_of(doc) == "call my_func_name now"
        assert all(not marks_of(n) for n in find(doc, "text"))

    def test_spaced_asterisks_are_not_emphasis(self):  # #128 "2 * 3 * 4"
        doc = md_to_adf("2 * 3 * 4")
        assert text_of(doc) == "2 * 3 * 4"
        assert all(not marks_of(n) for n in find(doc, "text"))

    def test_mixed_identifier_and_real_emphasis(self):  # #128 "a_b *c* d_e"
        doc = md_to_adf("a_b *c* d_e")
        assert text_of(doc) == "a_b c d_e"
        assert [(n["text"], marks_of(n)) for n in find(doc, "text") if marks_of(n)] == [
            ("c", ["em"])
        ]

    def test_opener_must_touch_non_space(self):  # #128 flanking: inner side is non-space
        doc = md_to_adf("* not em * nor **  strong **")
        assert all(not marks_of(n) for n in find(doc, "text"))

    def test_asterisk_emphasis_works_inside_a_word(self):  # #128 only `_` is word-restricted
        assert ("b", ["em"]) in marked("a*b*c")


# --------------------------------------------------------------------------- lists


def item_texts(list_node):
    return [text_of(item.get("content", [None])[0]) for item in list_node["content"]]


class TestLists:
    def test_bullet_list_maps_to_bullet_list_of_list_items_of_paragraphs(self):  # #128
        blocks = body("- a\n- b\n* c")
        assert len(blocks) == 1 and blocks[0]["type"] == "bulletList"
        items = blocks[0]["content"]
        assert [i["type"] for i in items] == ["listItem"] * 3
        assert all(i["content"][0]["type"] == "paragraph" for i in items)
        assert item_texts(blocks[0]) == ["a", "b", "c"]

    def test_ordered_list_maps_to_ordered_list(self):  # #128
        blocks = body("1. one\n2. two\n3. three")
        assert len(blocks) == 1 and blocks[0]["type"] == "orderedList"
        assert item_texts(blocks[0]) == ["one", "two", "three"]

    @pytest.mark.parametrize("step", [2, 4])
    def test_nests_bullet_lists_by_indentation(self, step):  # #128 "nests ... by indentation"
        pad = " " * step
        blocks = body(f"- a\n{pad}- b\n{pad}{pad}- c\n- d")
        top = blocks[0]
        assert top["type"] == "bulletList"
        assert item_texts(top) == ["a", "d"]
        first = top["content"][0]["content"]
        assert first[0]["type"] == "paragraph"
        assert first[1]["type"] == "bulletList"
        inner = first[1]
        assert item_texts(inner) == ["b"]
        deepest = inner["content"][0]["content"][1]
        assert deepest["type"] == "bulletList"
        assert item_texts(deepest) == ["c"]

    def test_nests_an_ordered_list_inside_a_bullet_list(self):  # #128
        blocks = body("- a\n  1. x\n  2. y\n- b")
        nested = blocks[0]["content"][0]["content"][1]
        assert nested["type"] == "orderedList"
        assert item_texts(nested) == ["x", "y"]

    def test_list_item_text_carries_inline_marks(self):  # #128
        blocks = body("- some **bold** item")
        assert ("bold", ["strong"]) in [
            (n["text"], marks_of(n)) for n in find(blocks[0], "text")
        ]

    def test_keeps_a_task_list_checkbox_as_literal_text(self):  # #128 "task-list checkbox"
        blocks = body("- [ ] open\n- [x] done")
        assert blocks[0]["type"] == "bulletList"
        assert item_texts(blocks[0]) == ["[ ] open", "[x] done"]
        assert all(not marks_of(n) for n in find(blocks[0], "text"))

    def test_list_followed_by_paragraph_ends_the_list(self):  # #128
        blocks = body("- a\n- b\n\nafter")
        assert [b["type"] for b in blocks] == ["bulletList", "paragraph"]


# --------------------------------------------------------------------------- code blocks


class TestCodeBlocks:
    def test_keeps_code_block_language_and_content(self):  # #128 "keeps code block language"
        blocks = body("```python\nprint('x')\nif y:\n    pass\n```")
        assert len(blocks) == 1 and blocks[0]["type"] == "codeBlock"
        assert blocks[0]["attrs"]["language"] == "python"
        texts = find(blocks[0], "text")
        assert len(texts) == 1
        assert texts[0]["text"] == "print('x')\nif y:\n    pass"
        assert not marks_of(texts[0])

    def test_code_content_is_not_inline_parsed(self):  # #128 unmarked text
        block = body("```\n**not bold** [x](y) _z_\n```")[0]
        assert block["type"] == "codeBlock"
        texts = find(block, "text")
        assert [n["text"] for n in texts] == ["**not bold** [x](y) _z_"]
        assert not marks_of(texts[0])

    def test_fence_without_language_is_still_a_code_block(self):  # #128
        block = body("```\nplain\n```")[0]
        assert block["type"] == "codeBlock"
        assert text_of(block) == "plain"
        assert not block.get("attrs", {}).get("language")

    def test_code_block_text_survives_byte_for_byte(self):  # #128 invariant A5 (md_to_adf side)
        src = "````sh\n```\n\tindented\t\n\n````"
        block = body(src)[0]
        assert block["type"] == "codeBlock"
        assert block["attrs"]["language"] == "sh"
        assert text_of(block) == "```\n\tindented\t\n"

    def test_tilde_or_backtick_text_inside_fence_does_not_close_it(self):  # #128 A5
        block = body("````\n```\nstill code\n````\n\nafter")
        assert block[0]["type"] == "codeBlock"
        assert text_of(block[0]) == "```\nstill code"
        assert block[1]["type"] == "paragraph"
        assert text_of(block[1]) == "after"

    def test_blank_lines_inside_fence_do_not_split_the_block(self):  # #128
        blocks = body("```\na\n\nb\n```")
        assert len(blocks) == 1 and blocks[0]["type"] == "codeBlock"
        assert text_of(blocks[0]) == "a\n\nb"


# --------------------------------------------------------------------------- tables


class TestTables:
    SRC = "| h1 | h2 |\n|----|----|\n| a | b |\n| c | d |"

    def test_makes_the_first_table_row_header_cells(self):  # #128 "first table row header cells"
        table = body(self.SRC)[0]
        assert table["type"] == "table"
        rows = table["content"]
        assert [r["type"] for r in rows] == ["tableRow"] * 3
        assert [c["type"] for c in rows[0]["content"]] == ["tableHeader"] * 2
        for row in rows[1:]:
            assert [c["type"] for c in row["content"]] == ["tableCell"] * 2

    def test_each_cell_wraps_one_paragraph_with_the_cell_text(self):  # #128
        rows = body(self.SRC)[0]["content"]
        grid = [[text_of(c) for c in r["content"]] for r in rows]
        assert grid == [["h1", "h2"], ["a", "b"], ["c", "d"]]
        for row in rows:
            for cell in row["content"]:
                assert [p["type"] for p in cell["content"]] == ["paragraph"]

    def test_cell_text_gets_inline_marks(self):  # #128
        table = body("| h |\n|---|\n| **x** |")[0]
        assert ("x", ["strong"]) in [(n["text"], marks_of(n)) for n in find(table, "text")]

    def test_ragged_rows_are_padded_with_empty_cells(self):  # #128
        table = body("| a | b | c |\n|---|---|---|\n| 1 |")[0]
        assert table["type"] == "table"
        widths = [len(r["content"]) for r in table["content"]]
        assert widths == [3, 3]
        assert [text_of(c) for c in table["content"][1]["content"]] == ["1", "", ""]

    def test_table_between_paragraphs(self):  # #128
        blocks = body("before\n\n| a |\n|---|\n| 1 |\n\nafter")
        assert [b["type"] for b in blocks] == ["paragraph", "table", "paragraph"]


# --------------------------------------------------------------------------- line breaks


class TestLineBreaks:
    def test_joins_soft_line_breaks_with_a_space(self):  # #128 "soft line breaks"
        blocks = body("hard wrapped\ndesign text\nacross lines")
        assert len(blocks) == 1 and blocks[0]["type"] == "paragraph"
        assert text_of(blocks[0]) == "hard wrapped design text across lines"
        assert not find(blocks[0], "hardBreak")

    def test_keeps_explicit_hard_breaks(self):  # #128 "explicit hard breaks"
        para = body("first\\\nsecond")[0]
        assert para["type"] == "paragraph"
        kinds = [n["type"] for n in para["content"]]
        assert kinds == ["text", "hardBreak", "text"]
        assert para["content"][0]["text"] == "first"
        assert para["content"][2]["text"] == "second"


# --------------------------------------------------------------------------- unsupported constructs


class TestUnsupportedConstructs:
    def test_turns_raw_html_into_a_plain_paragraph(self):  # #128 "raw HTML into a plain paragraph"
        src = "<div class=\"x\">raw <b>html</b></div>"
        blocks = body(src)
        assert len(blocks) == 1 and blocks[0]["type"] == "paragraph"
        texts = find(blocks[0], "text")
        assert [n["text"] for n in texts] == [src]
        assert not marks_of(texts[0])

    def test_multiline_html_is_one_literal_text_node(self):  # #128 source lines as one text node
        src = "<table>\n<tr><td>*x*</td></tr>\n</table>"
        blocks = body(src)
        assert len(blocks) == 1 and blocks[0]["type"] == "paragraph"
        texts = find(blocks[0], "text")
        assert len(texts) == 1
        assert texts[0]["text"] == src
        assert not marks_of(texts[0])

    def test_html_gets_no_inline_parsing(self):  # #128 "no inline parsing"
        texts = find(md_to_adf("<p>**b** and [t](u)</p>"), "text")
        assert [n["text"] for n in texts] == ["<p>**b** and [t](u)</p>"]
        assert not marks_of(texts[0])

    def test_keeps_an_image_as_literal_text(self):  # #128 "keeps an image as literal text"
        src = "![alt text](http://x.io/i.png)"
        doc = md_to_adf(src)
        assert text_of(doc) == src
        assert all(not marks_of(n) for n in find(doc, "text"))

    def test_image_inside_a_sentence_is_not_turned_into_a_link(self):  # #128
        doc = md_to_adf("see ![alt](http://x.io/i.png) here")
        assert text_of(doc) == "see ![alt](http://x.io/i.png) here"
        assert not any("link" in marks_of(n) for n in find(doc, "text"))

    @pytest.mark.parametrize("src", ["> quoted text", "> a\n> b", "---", "***", "___"])
    def test_block_quote_and_rule_survive_as_literal_paragraph(self, src):  # #128
        blocks = body(src)
        assert len(blocks) == 1 and blocks[0]["type"] == "paragraph"
        assert text_of(blocks[0]) == src
        assert all(not marks_of(n) for n in find(blocks[0], "text"))


# --------------------------------------------------------------------------- A2 allow-lists


class TestAllowLists:
    def test_allowed_nodes_is_the_documented_set(self):  # #128 invariant A2
        assert isinstance(ALLOWED_NODES, frozenset)
        assert ALLOWED_NODES == frozenset({
            "doc", "paragraph", "heading", "bulletList", "orderedList", "listItem",
            "codeBlock", "table", "tableRow", "tableHeader", "tableCell", "hardBreak", "text",
        })

    def test_allowed_marks_is_the_documented_set(self):  # #128 invariant A2
        assert isinstance(ALLOWED_MARKS, frozenset)
        assert ALLOWED_MARKS == frozenset({"strong", "em", "code", "link"})

    @pytest.mark.parametrize("name", sorted(CORPUS))
    def test_only_documented_nodes_and_marks_are_emitted(self, name):  # #128 invariant A2
        doc = md_to_adf(CORPUS[name])
        for node in walk(doc):
            assert node["type"] in ALLOWED_NODES, (name, node["type"])
            for mark in node.get("marks", []) or []:
                assert mark["type"] in ALLOWED_MARKS, (name, mark["type"])

    def test_every_text_node_has_non_empty_text(self):  # #128 ADF rejects empty text nodes
        for src in CORPUS.values():
            for n in find(md_to_adf(src), "text"):
                assert n["text"] != ""

    def test_link_mark_always_carries_href(self):  # #128
        for n in find(md_to_adf(CORPUS["inline"]), "text"):
            for m in n.get("marks", []) or []:
                if m["type"] == "link":
                    assert m["attrs"]["href"]


# --------------------------------------------------------------------------- A3 purity


class TestPurity:
    def test_module_has_no_io_imports_by_grep(self):  # #128 invariant A3
        pattern = re.compile(r"^\s*(import|from) (os|sys|socket|subprocess|urllib|http)\b", re.M)
        assert pattern.findall(ADF_SOURCE.read_text()) == []

    def test_module_imports_nothing_that_performs_io(self):  # #128 invariant A3 (AST, stricter)
        forbidden = {
            "os", "sys", "socket", "subprocess", "urllib", "http", "requests", "httpx",
            "pathlib", "shutil", "io", "tempfile", "ssl", "asyncio", "ftplib", "smtplib",
        }
        tree = ast.parse(ADF_SOURCE.read_text())
        imported: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.update(a.name.split(".")[0] for a in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported.add(node.module.split(".")[0])
        assert imported & forbidden == set()

    def test_calls_do_not_touch_the_filesystem(self, tmp_path, monkeypatch):  # #128 A3 behaviour
        monkeypatch.chdir(tmp_path)
        md_to_adf(CORPUS["mixed"])
        assert list(tmp_path.iterdir()) == []

    def test_conversion_is_deterministic_and_does_not_mutate_shared_state(self):  # #128
        first = md_to_adf(CORPUS["mixed"])
        second = md_to_adf(CORPUS["mixed"])
        assert first == second
        first["content"].clear()
        assert md_to_adf(CORPUS["mixed"]) == second


# --------------------------------------------------------------------------- A4 malformed input


MALFORMED = [
    "```\nunclosed fence",
    "```python\nstill open\n\n\nmore",
    "| a | b |\n|---|\n| 1 | 2 | 3 |",
    "| a | b |\n| 1 | 2 |",
    "|",
    "| lone",
    "||||",
    "|---|---|",
    "[",
    "]",
    "[]()",
    "[a](",
    "![",
    "![](",
    "**",
    "****",
    "* ",
    "- ",
    "1.",
    "1. ",
    "#",
    "# ",
    "\\",
    "\\\\",
    "`",
    "``",
    "_",
    "__",
    "- a\n      - way too deep\n  - odd\n - off",
    "    indented code-ish",
    "\t- tab list",
    "- a\n\n\n\n- b",
    "<",
    "<div>",
    "> ",
    "\x00\x01\x02",
    "a\r\nb\r\n\r\nc",
    "\u2028 unicode \U0001f600 \u202e",
    "x" * 20000,
    "*" * 501,
    "- " * 300,
    "[" * 200 + "]" * 200,
]


class TestMalformedInput:
    @pytest.mark.parametrize("src", MALFORMED, ids=[repr(s)[:40] for s in MALFORMED])
    def test_no_input_raises_and_a_doc_is_returned(self, src):  # #128 invariant A4
        doc = md_to_adf(src)
        assert doc["type"] == "doc" and doc["version"] == 1
        assert isinstance(doc["content"], list) and doc["content"]
        for node in walk(doc):
            assert node["type"] in ALLOWED_NODES
            for mark in node.get("marks", []) or []:
                assert mark["type"] in ALLOWED_MARKS

    def test_lone_pipe_is_kept_as_text(self):  # #128 "unsupported input becomes text"
        assert text_of(md_to_adf("|")) == "|"

    def test_unclosed_fence_loses_no_text(self):  # #128 nothing is dropped
        text = text_of(md_to_adf("```python\nprint('kept')"))
        assert "print('kept')" in text

    def test_pipe_row_without_separator_is_not_dropped(self):  # #128
        text = text_of(md_to_adf("| a | b |\n| 1 | 2 |"))
        for token in ("a", "b", "1", "2"):
            assert token in text

    def test_crlf_line_endings_are_treated_like_lf(self):  # #128
        assert md_to_adf("a\r\nb\r\n\r\nc") == md_to_adf("a\nb\n\nc")


class TestFallback:
    def test_parser_failure_warns_and_returns_literal_doc(self, monkeypatch):  # #128 review: no silent swallow
        def boom(_lines):
            raise RuntimeError("boom")

        monkeypatch.setattr(_adf, "_blocks", boom)
        with pytest.warns(RuntimeWarning, match="boom"):
            doc = md_to_adf("keep **this**")
        assert doc["type"] == "doc"
        assert text_of(doc) == "keep **this**"


class TestUnsafeLinks:
    @pytest.mark.parametrize("href", ["javascript:alert(1)", "JavaScript:x", "data:text/html,x", "vbscript:x"])
    def test_scripting_scheme_stays_literal_text(self, href):  # #128 review: no live javascript: links
        src = f"[click]({href})"
        doc = md_to_adf(src)
        assert text_of(doc) == src
        assert not any("link" in marks_of(n) for n in find(doc, "text"))

    def test_https_link_still_works(self):  # #128
        assert any("link" in marks_of(n) for n in find(md_to_adf("[a](https://x.io)"), "text"))


# =========================================================================== adf_to_md (#129)
#
# Covers LLD v3 E3.2 §1.1 `describe("adf_to_md")` and `describe("round trip")`, and invariants
# A1 (stability), A5 (code byte-for-byte) and A6 (fidelity). Escaping is asserted by behaviour
# (the output re-parses to the same document), not by one particular escape spelling.


def adoc(*blocks):
    return {"version": 1, "type": "doc", "content": list(blocks)}


def para(*inline):
    return {"type": "paragraph", "content": list(inline)}


def txt(text, *marks):
    node = {"type": "text", "text": text}
    if marks:
        node["marks"] = [
            {"type": "link", "attrs": {"href": m[1]}} if isinstance(m, tuple) else {"type": m} for m in marks
        ]
    return node


def reparse(doc):
    return md_to_adf(adf_to_md(doc))


# Canonical Markdown: adf_to_md(md_to_adf(x)) == x (A6).
CANONICAL = [
    "# Title",
    "## Sub",
    "###### Six",
    "Just a paragraph.",
    "**b** and *i* and `c` and [t](http://x.io/a)",
    "[**bold link**](http://x.io)",
    "[`code link`](http://x.io)",
    "snake_case_name",
    "2 * 3 * 4",
    "a_b *c* d_e",
    "- a\n- b\n  - nested\n- c",
    "1. one\n2. two\n  1. inner",
    "- [ ] open\n- [x] done",
    "- a\n\n1. b",
    "```python\nprint('x')\n```",
    "```\nplain\n```",
    "line one\\\nline two",
    "# H\n\ntext **b**\n\n- x\n- y\n\n```\ncode\n```",
]

HOSTILE = [
    "*", "**", "_", "__", "[", "]", "`", "``", "|", "\\", "a\\b", "trailing\\",
    "# h", "## h", "#", "- x", "-", "+ x", "* x", "1. x", "1) x", "12. x", "> q", "---", "***", "___",
    "~~~", "<b>raw</b>", "![i](http://x.io/i.png)", "[a](b)", "[a]", "a [b] c", "a | b", "a|b|c",
    "*a", "a*", "a * b", "_a", "a_", "snake_case", "a_b_c", "**a", "*a**", "`a", "a`b", "\\*x\\*",
    "\\# h", "&amp;", "a\\\\b", "| a |", ]

# A text node holding a raw newline is not something md_to_adf emits (soft breaks become a space,
# hard breaks a hardBreak node), so A1 does not cover it; see TestNewlineInText.
NEWLINE_TEXT = ["x\n- y", "x\n1. y", "x\n# y"]


class TestAdfToMdNullAndEmpty:
    @pytest.mark.parametrize(
        "doc",
        [None, {}, {"type": "doc"}, {"version": 1, "type": "doc", "content": []}, adoc(para())],
        ids=["none", "empty-dict", "no-content-key", "empty-content", "empty-paragraph"],
    )
    def test_null_or_empty_doc_is_an_empty_body(self, doc):  # #129 "treats a null description as an empty body"
        assert adf_to_md(doc) == ""

    def test_returns_str(self):  # #129
        assert isinstance(adf_to_md(md_to_adf("hello")), str)

    def test_blank_markdown_round_trips_to_empty(self):  # #129
        assert adf_to_md(md_to_adf("")) == ""

    def test_block_without_content_key_does_not_raise(self):  # #129 nothing raises on Jira-shaped input
        assert adf_to_md(adoc({"type": "paragraph"})) == ""
        assert adf_to_md(adoc({"type": "bulletList"})) == ""

    def test_does_not_mutate_its_input(self):  # #129
        doc = md_to_adf("# T\n\n- a *b*\n\n```sh\nx\n```")
        before = repr(doc)
        adf_to_md(doc)
        assert repr(doc) == before


class TestAdfToMdUnknownNodes:
    def test_unknown_block_renders_as_its_text_paragraph(self):  # #129 "renders an undocumented node as its text content"
        panel = {"type": "panel", "attrs": {"panelType": "info"}, "content": [para(txt("note this"))]}
        assert adf_to_md(adoc(panel)) == "note this"

    def test_unknown_block_sits_between_known_blocks(self):  # #129 story 1.3 AC3
        panel = {"type": "panel", "content": [para(txt("note"))]}
        doc = adoc(
            {"type": "heading", "attrs": {"level": 1}, "content": [txt("H")]}, panel, para(txt("after"))
        )
        assert adf_to_md(doc) == "# H\n\nnote\n\nafter"

    def test_unknown_inline_renders_its_text(self):  # #129
        mention = {"type": "mention", "attrs": {"id": "u1"}, "text": "@bob"}
        assert adf_to_md(adoc(para(txt("hi "), mention, txt("!")))) == "hi @bob!"

    def test_deeply_nested_unknown_node_keeps_all_text(self):  # #129 "nothing is dropped"
        deep = {
            "type": "expand",
            "content": [{"type": "blockquote", "content": [para(txt("deep"), txt(" text"))]}],
        }
        out = adf_to_md(adoc(deep))
        assert "deep" in out and "text" in out

    def test_unknown_node_without_text_does_not_raise(self):  # #129
        assert adf_to_md(adoc({"type": "rule"})).strip() == ""

    def test_text_of_unknown_block_is_escaped_like_any_text(self):  # #129 A1 holds for fallbacks
        panel = {"type": "panel", "content": [para(txt("# not a heading"))]}
        out = md_to_adf(adf_to_md(adoc(panel)))
        assert [b["type"] for b in out["content"]] == ["paragraph"]
        assert text_of(out) == "# not a heading"


class TestAdfToMdConstructs:
    def test_headings_levels_1_to_6(self):  # #129
        blocks = [{"type": "heading", "attrs": {"level": n}, "content": [txt(f"h{n}")]} for n in range(1, 7)]
        expected = "\n\n".join("#" * n + f" h{n}" for n in range(1, 7))
        assert adf_to_md(adoc(*blocks)) == expected

    def test_paragraphs_are_separated_by_one_blank_line(self):  # #129
        assert adf_to_md(adoc(para(txt("a")), para(txt("b")))) == "a\n\nb"

    def test_no_trailing_newline(self):  # #129 canonical form is exact
        assert not adf_to_md(md_to_adf("# T\n\ntext")).endswith("\n")

    def test_inline_marks(self):  # #129
        assert adf_to_md(adoc(para(txt("b", "strong")))) == "**b**"
        assert adf_to_md(adoc(para(txt("i", "em")))) == "*i*"
        assert adf_to_md(adoc(para(txt("c", "code")))) == "`c`"

    def test_link_mark(self):  # #129
        assert adf_to_md(adoc(para(txt("t", ("link", "http://x.io/a"))))) == "[t](http://x.io/a)"

    @pytest.mark.parametrize(
        "marks, expected",
        [
            (["strong", ("link", "http://x.io")], "[**t**](http://x.io)"),
            ([("link", "http://x.io"), "strong"], "[**t**](http://x.io)"),
            (["code", ("link", "http://x.io")], "[`t`](http://x.io)"),
        ],
    )
    def test_mark_order_is_link_outermost_regardless_of_input_order(self, marks, expected):  # #129 mark order
        assert adf_to_md(adoc(para(txt("t", *marks)))) == expected

    @pytest.mark.parametrize(
        "marks",
        [["em", "strong"], ["strong", "em"], [("link", "http://x.io"), "em", "strong"], ["em", ("link", "http://x.io"), "strong"]],
    )
    def test_marks_render_in_link_strong_em_order(self, marks):  # #129 mark order via the re-parsed document
        out = reparse(adoc(para(txt("t", *marks))))
        node = find(out, "text")[0]
        assert text_of(out) == "t"
        assert marks_of(node) == [m for m in MARK_ORDER if m in marks_of(node)]
        assert set(marks_of(node)) == {m if isinstance(m, str) else "link" for m in marks}

    def test_inline_code_containing_backticks_survives(self):  # #129
        doc = adoc(para(txt("a`b", "code")))
        assert reparse(doc) == doc

    def test_hard_break(self):  # #129 hardBreak -> backslash + newline
        doc = adoc(para(txt("one"), {"type": "hardBreak"}, txt("two")))
        assert adf_to_md(doc) == "one\\\ntwo"
        assert reparse(doc) == doc

    def test_bullet_list_nested(self):  # #129 two spaces per level
        md = "- a\n- b\n  - c\n    - d\n- e"
        assert adf_to_md(md_to_adf(md)) == md

    def test_ordered_list_is_numbered_sequentially(self):  # #129
        item = lambda t: {"type": "listItem", "content": [para(txt(t))]}  # noqa: E731
        doc = adoc({"type": "orderedList", "content": [item("a"), item("b"), item("c")]})
        assert adf_to_md(doc) == "1. a\n2. b\n3. c"

    def test_mixed_nested_lists_round_trip(self):  # #129
        md = "1. one\n  - sub\n  - sub2\n2. two"
        doc = md_to_adf(md)
        assert reparse(doc) == doc

    def test_list_item_with_marks_and_links(self):  # #129
        md = "- **b** [t](http://x.io) `c`"
        assert adf_to_md(md_to_adf(md)) == md

    def test_task_checkboxes_stay_literal_text(self):  # #129 Open question 1
        assert adf_to_md(md_to_adf("- [ ] open\n- [x] done")) == "- [ ] open\n- [x] done"

    def test_table_round_trips_structure(self):  # #129
        doc = md_to_adf("| a | b |\n|---|---|\n| 1 | 2 |\n| 3 | 4 |")
        out = reparse(doc)
        assert out == doc
        assert [n["type"] for n in find(out, "tableHeader")] == ["tableHeader"] * 2
        assert len(find(out, "tableCell")) == 4

    def test_table_output_is_gfm_pipe_table(self):  # #129
        lines = adf_to_md(md_to_adf("| a | b |\n|---|---|\n| 1 | 2 |")).split("\n")
        assert len(lines) == 3
        assert all(line.startswith("|") and line.endswith("|") for line in lines)
        assert re.fullmatch(r"\|(\s*:?-+:?\s*\|)+", lines[1])

    def test_table_cell_pipe_is_escaped(self):  # #129 "table incl. escaped pipes"
        doc = md_to_adf("| a | b |\n|---|---|\n| x \\| y | 2 |")
        assert "x | y" in text_of(doc)
        out = adf_to_md(doc)
        assert "\\|" in out
        assert reparse(doc) == doc

    def test_table_cell_with_marks_and_links(self):  # #129
        doc = md_to_adf("| **a** | [l](http://x.io) |\n|---|---|\n| `c` | *e* |")
        assert reparse(doc) == doc

    def test_ragged_table_padded_cells_round_trip(self):  # #129
        doc = md_to_adf("| a | b | c |\n|---|---|---|\n| 1 |")
        assert reparse(doc) == doc

    def test_pipe_outside_a_table_is_left_alone(self):  # #129 pipe escaped only inside cells
        assert adf_to_md(adoc(para(txt("a | b")))) == "a | b"


class TestAdfToMdEscaping:
    @pytest.mark.parametrize("text", HOSTILE, ids=[repr(t) for t in HOSTILE])
    def test_plain_text_paragraph_reparses_to_same_text(self, text):  # #129 "escapes markdown specials in text nodes"
        doc = adoc(para(txt(text)))
        assert reparse(doc) == doc

    @pytest.mark.parametrize("text", ["# h", "- x", "+ x", "1. x", "*a*", "[a](b)", "`c`", "**b**"])
    def test_specials_are_not_emitted_raw(self, text):  # #129 escaping actually happens
        assert adf_to_md(adoc(para(txt(text)))) != text

    @pytest.mark.parametrize("text", ["# h", "- x", "+ x", "1. x", "---", "> q"])
    def test_block_leading_special_does_not_change_block_type(self, text):  # #129
        out = reparse(adoc(para(txt(text))))
        assert [b["type"] for b in out["content"]] == ["paragraph"]
        assert text_of(out) == text

    @pytest.mark.parametrize("text", HOSTILE, ids=[repr(t) for t in HOSTILE])
    def test_hostile_text_inside_a_heading(self, text):  # #129
        doc = adoc({"type": "heading", "attrs": {"level": 2}, "content": [txt(text)]})
        assert reparse(doc) == doc

    @pytest.mark.parametrize("text", HOSTILE, ids=[repr(t) for t in HOSTILE])
    def test_hostile_text_inside_a_list_item(self, text):  # #129
        item = {"type": "listItem", "content": [para(txt(text))]}
        doc = adoc({"type": "bulletList", "content": [item]})
        assert reparse(doc) == doc

    @pytest.mark.parametrize("text", HOSTILE, ids=[repr(t) for t in HOSTILE])
    def test_hostile_text_inside_a_table_cell(self, text):  # #129
        cell = lambda kind, t: {"type": kind, "content": [para(txt(t))]}  # noqa: E731
        row = lambda kind: {"type": "tableRow", "content": [cell(kind, text), cell(kind, "z")]}  # noqa: E731
        doc = adoc({"type": "table", "content": [row("tableHeader"), row("tableCell")]})
        assert reparse(doc) == doc

    @pytest.mark.parametrize("text", HOSTILE, ids=[repr(t) for t in HOSTILE])
    def test_hostile_text_with_marks(self, text):  # #129
        for marks in (["strong"], ["em"], [("link", "http://x.io")]):
            doc = adoc(para(txt("pre "), txt(text, *marks), txt(" post")))
            assert text_of(reparse(doc)) == text_of(doc)

    @pytest.mark.parametrize("text", HOSTILE, ids=[repr(t) for t in HOSTILE])
    def test_hostile_text_never_gains_marks_or_structure(self, text):  # #129
        out = reparse(adoc(para(txt(text))))
        assert not any(marks_of(n) for n in find(out, "text"))
        assert not find(out, "bulletList") and not find(out, "orderedList") and not find(out, "heading")

    def test_identifiers_with_underscores_are_not_mangled(self):  # #129 A6
        assert adf_to_md(adoc(para(txt("snake_case_name")))) == "snake_case_name"

    def test_spaced_asterisks_are_not_mangled(self):  # #129 A6
        assert adf_to_md(adoc(para(txt("2 * 3 * 4")))) == "2 * 3 * 4"


class TestNewlineInText:
    @pytest.mark.parametrize("text", NEWLINE_TEXT, ids=[repr(t) for t in NEWLINE_TEXT])
    def test_newline_in_text_keeps_lines_and_gains_no_structure(self, text):  # #129 foreign docs
        out = reparse(adoc(para(txt(text))))
        assert [b["type"] for b in out["content"]] == ["paragraph"]
        assert text_of(out) == text  # hardBreak counts as "\n" in text_of

    @pytest.mark.parametrize("text", NEWLINE_TEXT, ids=[repr(t) for t in NEWLINE_TEXT])
    def test_newline_in_text_survives_in_heading_list_and_cell(self, text):  # #129 foreign docs
        item = {"type": "listItem", "content": [para(txt(text))]}
        cell = {"type": "tableCell", "content": [para(txt(text))]}
        head = {"type": "tableHeader", "content": [para(txt("h"))]}
        doc = adoc(
            {"type": "heading", "attrs": {"level": 2}, "content": [txt(text)]},
            {"type": "bulletList", "content": [item]},
            {"type": "table", "content": [{"type": "tableRow", "content": [head]}, {"type": "tableRow", "content": [cell]}]},
        )
        out = reparse(doc)
        assert [b["type"] for b in out["content"]] == ["heading", "bulletList", "table"]
        assert text_of(out["content"][0]) == text.replace("\n", " ")  # a heading is one line


class TestFidelityA6:
    @pytest.mark.parametrize("md", CANONICAL, ids=[m.split("\n")[0][:40] for m in CANONICAL])
    def test_canonical_corpus_is_reproduced_exactly(self, md):  # #129 A6 adf_to_md(md_to_adf(x)) == x
        assert adf_to_md(md_to_adf(md)) == md

    def test_a6_underscore_identifier_gets_no_emphasis(self):  # #129 A6
        doc = md_to_adf("snake_case_name")
        assert marked("snake_case_name") == [("snake_case_name", [])]
        assert adf_to_md(doc) == "snake_case_name"

    def test_a6_mixed_underscore_and_star_emphasis(self):  # #129 A6 `a_b *c* d_e`
        assert marked("a_b *c* d_e") == [("a_b ", []), ("c", ["em"]), (" d_e", [])]
        assert adf_to_md(md_to_adf("a_b *c* d_e")) == "a_b *c* d_e"

    def test_soft_wrapped_text_comes_back_on_one_line(self):  # #129 documented normalisation
        assert adf_to_md(md_to_adf("line one\nline two")) == "line one line two"

    def test_underscore_emphasis_comes_back_as_same_emphasis(self):  # #129 `_i_` is em either way
        doc = md_to_adf("_i_ word")
        assert reparse(doc) == doc
        assert marked("_i_ word")[0] == ("i", ["em"])


class TestCodeBlocksA5:
    def test_simple_fence_exact(self):  # #129 A5
        assert adf_to_md(md_to_adf("```python\nprint('x')\n```")) == "```python\nprint('x')\n```"

    def test_language_survives(self):  # #129 A5
        out = reparse(adoc({"type": "codeBlock", "attrs": {"language": "rust"}, "content": [txt("fn main() {}")]}))
        assert out["content"][0]["attrs"]["language"] == "rust"

    def test_no_language_stays_without_language(self):  # #129 A5
        out = reparse(adoc({"type": "codeBlock", "content": [txt("x")]}))
        assert not out["content"][0].get("attrs", {}).get("language")

    def test_backticks_tabs_and_trailing_blank_line_survive(self):  # #129 A5
        code = "```\n\tindented\t\n  two spaces\n\n"
        doc = adoc({"type": "codeBlock", "attrs": {"language": "sh"}, "content": [txt(code)]})
        out = reparse(doc)
        block = out["content"][0]
        assert block["type"] == "codeBlock"
        assert text_of(block) == code
        assert block["attrs"]["language"] == "sh"

    def test_trailing_blank_line_from_markdown_survives(self):  # #129 A5 starting from Markdown
        src = "```py\na\n\n```"
        first = md_to_adf(src)
        assert text_of(first) == "a\n"
        assert text_of(reparse(first)) == "a\n"

    def test_fence_is_longer_than_longest_backtick_run(self):  # #129 LLD fenced code rule
        code = "a\n````\nb"
        out = adf_to_md(adoc({"type": "codeBlock", "content": [txt(code)]}))
        first = out.split("\n")[0]
        assert set(first) == {"`"} and len(first) >= 5
        assert code in out

    @pytest.mark.parametrize("code", ["`", "``", "```", "a ``` b", "````\n```", "~~~", "\n\n", "\t", " x ", "x\\", "**b** [a](b) _c_"])
    def test_code_text_is_byte_for_byte(self, code):  # #129 A5
        doc = adoc({"type": "codeBlock", "attrs": {"language": "txt"}, "content": [txt(code)]})
        out = reparse(doc)
        assert len(out["content"]) == 1 and out["content"][0]["type"] == "codeBlock"
        assert text_of(out["content"][0]) == code
        assert out["content"][0]["attrs"]["language"] == "txt"

    def test_empty_code_block_survives(self):  # #129 A5 edge
        doc = adoc({"type": "codeBlock", "content": []})
        out = reparse(doc)
        assert out["content"][0]["type"] == "codeBlock"
        assert text_of(out["content"][0]) == ""

    def test_code_inside_list_context_does_not_leak(self):  # #129
        md = "- a\n\n```\nx\n```"
        doc = md_to_adf(md)
        assert reparse(doc) == doc

    def test_code_content_is_never_escaped(self):  # #129 A5
        out = adf_to_md(adoc({"type": "codeBlock", "content": [txt("*a* _b_ [c](d) # e | f")]}))
        assert "*a* _b_ [c](d) # e | f" in out


class TestRoundTripA1:
    @pytest.mark.parametrize("name", sorted(CORPUS))
    def test_second_round_trip_is_stable_for_each_construct(self, name):  # #129 A1
        first = md_to_adf(CORPUS[name])
        assert md_to_adf(adf_to_md(first)) == first

    @pytest.mark.parametrize("name", sorted(CORPUS))
    def test_markdown_is_a_fixed_point_after_one_pass(self, name):  # #129 A1 (text form)
        once = adf_to_md(md_to_adf(CORPUS[name]))
        assert adf_to_md(md_to_adf(once)) == once

    def test_whole_subset_in_one_document(self):  # #129 "is stable for the whole supported subset"
        src = "\n\n".join(CORPUS.values())
        first = md_to_adf(src)
        assert md_to_adf(adf_to_md(first)) == first

    @pytest.mark.parametrize("text", HOSTILE, ids=[repr(t) for t in HOSTILE])
    def test_hostile_text_as_markdown_input_is_stable(self, text):  # #129 A1 "for any x"
        first = md_to_adf(text)
        assert md_to_adf(adf_to_md(first)) == first

    @pytest.mark.parametrize("text", HOSTILE, ids=[repr(t) for t in HOSTILE])
    def test_hostile_text_in_larger_markdown_is_stable(self, text):  # #129 A1
        src = f"# {text}\n\n- {text}\n  - {text}\n\n1. {text}\n\n| {text} | b |\n|---|---|\n| c | {text} |\n\n{text}"
        first = md_to_adf(src)
        assert md_to_adf(adf_to_md(first)) == first

    @pytest.mark.parametrize("src", MALFORMED)
    def test_malformed_input_is_stable(self, src):  # #129 A1 + A4 together
        first = md_to_adf(src)
        assert md_to_adf(adf_to_md(first)) == first

    def test_unsupported_constructs_survive_as_text(self):  # #129 story 1.2 / 1.3 AC4
        for src in ("<div>raw <b>html</b></div>", "> quoted\n> text", "---", "![alt](http://x.io/i.png)"):
            first = md_to_adf(src)
            assert text_of(reparse(first)) == text_of(first)

    def test_adf_to_md_output_only_reparses_to_allowed_nodes(self):  # #129 A2 through the round trip
        for src in CORPUS.values():
            for node in walk(reparse(md_to_adf(src))):
                assert node["type"] in ALLOWED_NODES
                for mark in node.get("marks", []) or []:
                    assert mark["type"] in ALLOWED_MARKS


class TestAdfToMdOddInput:
    def test_non_numeric_heading_level_and_none_child_do_not_raise(self):  # #129 evaluator risk
        doc = adoc({"type": "heading", "attrs": {"level": "x"}, "content": [txt("h")]}, None)
        assert adf_to_md(doc) == "# h"

    @pytest.mark.parametrize(
        "doc",
        [
            adoc({"type": "table", "content": [{"type": "tableRow", "content": [{"type": "tableCell", "content": [para(None)]}]}]}),
            adoc(para({"type": "text", "text": "a", "marks": 5})),
            adoc(para({"type": "text", "text": "a", "marks": [{"type": "link", "attrs": "x"}]})),
            adoc({"type": "heading", "attrs": "x", "content": [txt("h")]}),
            adoc({"type": "codeBlock", "attrs": [1], "content": [txt("c")]}),
            adoc(para({"type": "text", "text": None})),
        ],
        ids=["cell-none", "marks-int", "link-attrs-str", "heading-attrs-str", "code-attrs-list", "text-none"],
    )
    def test_wrong_typed_fields_never_raise(self, doc):  # #129 review: nothing raises
        assert isinstance(adf_to_md(doc), str)
