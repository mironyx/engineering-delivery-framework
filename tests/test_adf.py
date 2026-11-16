"""Tests for the Markdown to ADF converter, `md_to_adf` side (issue #128).

Covers LLD v3 E3.2 §1.1 `describe("md_to_adf")` and invariants A2 (allow-lists), A3 (purity),
A4 (no input raises) and the md_to_adf half of A5 (code block text and language survive).
`adf_to_md` and round trips are out of scope here (Task 2).

The module is pure, so every test calls the public function directly; there is no HTTP or SDK
boundary to mock. `tests/conftest.py` puts plugins/edf/bin on sys.path.
"""

from __future__ import annotations

import ast
import pathlib
import re

import pytest

import _adf
from _adf import ALLOWED_MARKS, ALLOWED_NODES, md_to_adf

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
