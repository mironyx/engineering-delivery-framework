"""Markdown to ADF converter (pure, standard library only).

Converts the Supported Markdown subset into an Atlassian Document Format document.
Nothing here performs I/O. Anything outside the subset survives as literal text, and
no input raises.

Design reference: plugins/edf/docs/design/v3/lld-v3-e3-2-jira-backend.md §1.1
"""

from __future__ import annotations

import re
import string
import warnings

ALLOWED_NODES: frozenset[str] = frozenset({
    "doc", "paragraph", "heading", "bulletList", "orderedList", "listItem",
    "codeBlock", "table", "tableRow", "tableHeader", "tableCell", "hardBreak", "text",
})
ALLOWED_MARKS: frozenset[str] = frozenset({"strong", "em", "code", "link"})

_MARK_ORDER = ("link", "strong", "em", "code")
_PUNCT = frozenset(string.punctuation)

_FENCE = re.compile(r"^ {0,3}(`{3,}|~{3,})[ \t]*([^\s`]*)[^`]*$")
_FENCE_CLOSE = re.compile(r"^ {0,3}(`{3,}|~{3,})[ \t]*$")
_HEADING = re.compile(r"^ {0,3}(#{1,6})(?:[ \t]+(.*?))?[ \t]*$")
_RULE = re.compile(r"^ {0,3}([-*_])(?: *\1){2,} *$")
_QUOTE = re.compile(r"^ {0,3}>")
_HTML = re.compile(r"^ {0,3}<[A-Za-z/!?]")
_LIST = re.compile(r"^([ \t]*)([-*+]|\d{1,9}[.)])(?:[ \t]+(.*))?$")
_LIST_INTERRUPT = re.compile(r"^ {0,3}(?:[-*+]|1[.)])[ \t]+\S")
_SEPARATOR_CELL = re.compile(r"^:?-+:?$")
_PIPE = re.compile(r"(?<!\\)\|")
_BACKTICKS = re.compile(r"`+")
_UNSAFE_SCHEME = re.compile(r"^\s*(?:javascript|data|vbscript):", re.I)


def md_to_adf(markdown: str) -> dict:
    """Convert the Supported Markdown subset to an ADF doc; never raises."""
    text = markdown.replace("\r\n", "\n").replace("\r", "\n")
    try:
        blocks = _blocks(text.split("\n"))
    except Exception as exc:  # noqa: BLE001 — the contract is "no input raises"
        warnings.warn(f"md_to_adf fell back to literal text: {exc!r}", RuntimeWarning, stacklevel=2)
        blocks = _literal_blocks(text)
    if not blocks:
        blocks = [{"type": "paragraph", "content": []}]
    return {"version": 1, "type": "doc", "content": blocks}


# --------------------------------------------------------------------------- blocks


def _blocks(lines: list[str]) -> list[dict]:
    out: list[dict] = []
    i = 0
    while i < len(lines):
        if not lines[i].strip():
            i += 1
            continue
        node, i = _next_block(lines, i)
        out.append(node)
    return out


# Justification: one dispatch point keeps the "first line decides the block" rule in one place.
def _next_block(lines: list[str], i: int) -> tuple[dict, int]:
    line = lines[i]
    fence = _FENCE.match(line)
    if fence:
        return _fence(lines, i, fence)
    heading = _HEADING.match(line)
    if heading:
        return _heading(heading), i + 1
    if _RULE.match(line):
        return _literal_paragraph([line]), i + 1
    if _QUOTE.match(line) or _HTML.match(line):
        return _until_blank(lines, i)
    if _LIST.match(line):
        return _list_block(lines, i)
    if _is_table(lines, i):
        return _table_block(lines, i)
    return _paragraph(lines, i)


# Justification: unsupported blocks all become the same literal paragraph; one builder, no drift.
def _literal_paragraph(lines: list[str]) -> dict:
    return {"type": "paragraph", "content": [{"type": "text", "text": "\n".join(lines)}]}


# Justification: fallback path when parsing fails; keeps the source text rather than raising.
def _literal_blocks(text: str) -> list[dict]:
    return [_literal_paragraph(chunk.split("\n")) for chunk in re.split(r"\n\s*\n", text) if chunk.strip()]


# Justification: block quotes and raw HTML end at a blank line and take no inline parsing.
def _until_blank(lines: list[str], i: int) -> tuple[dict, int]:
    j = i
    while j < len(lines) and lines[j].strip():
        j += 1
    return _literal_paragraph(lines[i:j]), j


# Justification: fence handling is self-contained (opener length, info string, byte-exact body).
def _fence(lines: list[str], i: int, opener: re.Match) -> tuple[dict, int]:
    marker, lang = opener.group(1), opener.group(2)
    j = i + 1
    while j < len(lines):
        close = _FENCE_CLOSE.match(lines[j])
        if close and close.group(1)[0] == marker[0] and len(close.group(1)) >= len(marker):
            break
        j += 1
    code = "\n".join(lines[i + 1:j])
    node: dict = {"type": "codeBlock", "content": [{"type": "text", "text": code}] if code else []}
    if lang:
        node["attrs"] = {"language": lang}
    return node, min(j + 1, len(lines))


# Justification: keeps _next_block flat; heading text takes inline parsing like a paragraph.
def _heading(match: re.Match) -> dict:
    return {
        "type": "heading",
        "attrs": {"level": len(match.group(1))},
        "content": _inline(match.group(2) or ""),
    }


# Justification: a paragraph ends at a blank line or at a block that may interrupt it.
def _interrupts(lines: list[str], i: int) -> bool:
    line = lines[i]
    return bool(
        not line.strip()
        or _FENCE.match(line)
        or _HEADING.match(line)
        or _RULE.match(line)
        or _QUOTE.match(line)
        or _LIST_INTERRUPT.match(line)
        or _is_table(lines, i)
    )


def _paragraph(lines: list[str], i: int) -> tuple[dict, int]:
    j = i + 1
    while j < len(lines) and not _interrupts(lines, j):
        j += 1
    text = "\n".join(line.strip() for line in lines[i:j])
    return {"type": "paragraph", "content": _inline(text)}, j


# --------------------------------------------------------------------------- lists


# Justification: collecting item lines first lets nesting be resolved by indentation alone.
def _list_block(lines: list[str], i: int) -> tuple[dict, int]:
    items: list[list] = []  # [indent, kind, text, line index]
    j = i
    while j < len(lines):
        line = lines[j]
        if not line.strip():
            k = j
            while k < len(lines) and not lines[k].strip():
                k += 1
            if k < len(lines) and _LIST.match(lines[k]) and not _RULE.match(lines[k]):
                j = k
                continue
            break
        match = _LIST.match(line)
        if match and not _RULE.match(line):
            indent = len(match.group(1).expandtabs(4))
            kind = "orderedList" if match.group(2)[0].isdigit() else "bulletList"
            items.append([indent, kind, match.group(3) or "", j])
        elif items and not _interrupts(lines, j):
            items[-1][2] += "\n" + line.strip()
        else:
            break
        j += 1
    node, pos = _list(items, 0, items[0][0])
    # A change of kind or a shallower indent ends this list; the rest is re-read as a new block.
    return node, (items[pos][3] if pos < len(items) else j)


def _list(items: list[list], i: int, base: int) -> tuple[dict, int]:
    kind = items[i][1]
    node: dict = {"type": kind, "content": []}
    while i < len(items):
        indent, item_kind, text, _ = items[i]
        if indent < base:
            break
        if indent > base:
            nested, i = _list(items, i, indent)
            node["content"][-1]["content"].append(nested)
            continue
        if item_kind != kind:
            break
        node["content"].append({
            "type": "listItem",
            "content": [{"type": "paragraph", "content": _inline(text)}],
        })
        i += 1
    return node, i


# --------------------------------------------------------------------------- tables


def _cells(line: str) -> list[str]:
    body = line.strip()
    if body.startswith("|"):
        body = body[1:]
    if body.endswith("|") and not body.endswith("\\|"):
        body = body[:-1]
    return [cell.strip() for cell in _PIPE.split(body)]


# Justification: a table needs header and separator rows of equal width; GFM says otherwise it is text.
def _is_table(lines: list[str], i: int) -> bool:
    if i + 1 >= len(lines) or "|" not in lines[i] or "|" not in lines[i + 1]:
        return False
    sep = _cells(lines[i + 1])
    return all(_SEPARATOR_CELL.match(c) for c in sep) and len(sep) == len(_cells(lines[i]))


# Justification: splits table row collection from the dispatcher so _next_block stays flat
def _table_block(lines: list[str], i: int) -> tuple[dict, int]:
    rows = [_cells(lines[i])]
    j = i + 2
    while j < len(lines) and lines[j].strip() and "|" in lines[j]:
        rows.append(_cells(lines[j]))
        j += 1
    return _table(rows), j


def _table(rows: list[list[str]]) -> dict:
    width = max(len(r) for r in rows)
    out = []
    for n, row in enumerate(rows):
        kind = "tableHeader" if n == 0 else "tableCell"
        cells = [
            {"type": kind, "content": [{"type": "paragraph", "content": _inline(c)}]}
            for c in row + [""] * (width - len(row))
        ]
        out.append({"type": "tableRow", "content": cells})
    return {"type": "table", "content": out}


# --------------------------------------------------------------------------- inline


def _inline(text: str) -> list[dict]:
    """Tokenise inline Markdown into ADF text and hardBreak nodes."""
    return _merge(_flatten(_emphasis(_scan(text)), frozenset(), None))


# Justification: GFM flanking decides whether a delimiter run can open or close emphasis.
def _flanking(prev: str, nxt: str, ch: str) -> tuple[bool, bool]:
    space_p = prev == "" or prev.isspace()
    space_n = nxt == "" or nxt.isspace()
    punct_p = not space_p and not prev.isalnum()
    punct_n = not space_n and not nxt.isalnum()
    left = not space_n and (not punct_n or space_p or punct_p)
    right = not space_p and (not punct_p or space_n or punct_n)
    if ch == "*":
        return left, right
    return left and (not right or punct_p), right and (not left or punct_n)


# Justification: code spans bind tighter than anything else, so they are cut out first.
def _code_span(text: str, i: int) -> tuple[tuple | None, int]:
    end = i
    while end < len(text) and text[end] == "`":
        end += 1
    size = end - i
    for run in _BACKTICKS.finditer(text, end):
        if len(run.group()) == size:
            code = text[end:run.start()].replace("\n", " ")
            if len(code) > 2 and code[0] == code[-1] == " " and code.strip():
                code = code[1:-1]
            return ("code", code), run.end()
    return None, end


# Justification: link syntax is matched on brackets and parentheses, not on regex, to allow nesting.
def _match_link(text: str, i: int) -> tuple[str, str, int] | None:
    depth, j = 0, i
    while j < len(text):
        if text[j] == "\\":
            j += 2
            continue
        depth += (text[j] == "[") - (text[j] == "]")
        if depth == 0:
            break
        j += 1
    else:
        return None
    if text[j + 1:j + 2] != "(":
        return None
    k, depth = j + 2, 1
    while k < len(text):
        if text[k] == "\\":
            k += 2
            continue
        depth += (text[k] == "(") - (text[k] == ")")
        if depth == 0:
            break
        k += 1
    else:
        return None
    label, dest = text[i + 1:j], text[j + 2:k].strip()
    if not label or not dest or any(c.isspace() for c in dest):
        return None
    href = re.sub(r"\\([!-/:-@\[-`{-~])", r"\1", dest)
    if _UNSAFE_SCHEME.match(href):
        return None  # scripting schemes never become a live link; the source stays as text
    return label, href, k + 1


# Justification: single left-to-right tokeniser; code, links and delimiter runs share one cursor
def _scan(text: str) -> list:
    toks: list = []
    buf: list[str] = []

    # Justification: closure over buf/toks so every token flushes pending plain text first
    def put(token) -> None:
        if buf:
            toks.append(("text", "".join(buf)))
            buf.clear()
        toks.append(token)

    i, n = 0, len(text)
    while i < n:
        c = text[i]
        nxt = text[i + 1] if i + 1 < n else ""
        if c == "\\" and nxt == "\n":
            put(("br",))
            i += 2
        elif c == "\\" and nxt in _PUNCT and nxt:
            buf.append(nxt)
            i += 2
        elif c == "\n":
            buf.append(" ")
            i += 1
        elif c == "`":
            token, j = _code_span(text, i)
            if token:
                put(token)
            else:
                buf.append(text[i:j])
            i = j
        elif c in "[!" and (c == "[" or nxt == "["):
            start = i if c == "[" else i + 1
            link = _match_link(text, start)
            if link is None:
                buf.append(c)
                i += 1
            elif c == "!":
                buf.append(text[i:link[2]])  # image: kept as literal source text
                i = link[2]
            else:
                put(("link", link[0], link[1]))
                i = link[2]
        elif c in "*_":
            j = i
            while j < n and text[j] == c:
                j += 1
            can_open, can_close = _flanking(text[i - 1] if i else "", text[j] if j < n else "", c)
            if can_open or can_close:
                put({"ch": c, "n": j - i, "orig": j - i, "open": can_open, "close": can_close})
            else:
                buf.append(text[i:j])
            i = j
        else:
            buf.append(c)
            i += 1
    if buf:
        toks.append(("text", "".join(buf)))
    return toks


# Justification: CommonMark's "rule of 3" decides whether an opener/closer pair may match.
def _find_opener(toks: list, i: int) -> int | None:
    closer = toks[i]
    for j in range(i - 1, -1, -1):
        opener = toks[j]
        if not (isinstance(opener, dict) and opener["ch"] == closer["ch"] and opener["open"] and opener["n"]):
            continue
        total = opener["orig"] + closer["orig"]
        both = opener["orig"] % 3 == 0 and closer["orig"] % 3 == 0
        if (opener["close"] or closer["open"]) and total % 3 == 0 and not both:
            continue
        return j
    return None


# Justification: CommonMark delimiter-stack resolution, separate from tokenising for testability
def _emphasis(toks: list) -> list:
    i = 0
    while i < len(toks):
        closer = toks[i]
        if not (isinstance(closer, dict) and closer["close"] and closer["n"]):
            i += 1
            continue
        j = _find_opener(toks, i)
        if j is None:
            i += 1
            continue
        opener = toks[j]
        use = 2 if opener["n"] >= 2 and closer["n"] >= 2 else 1
        opener["n"] -= use
        closer["n"] -= use
        toks[j + 1:i] = [("strong" if use == 2 else "em", toks[j + 1:i])]
        i = j + 2
        if opener["n"] == 0:
            del toks[j]
            i -= 1
        if closer["n"] == 0:
            del toks[i]
    return toks


# Justification: one place builds a text node so mark order and the no-empty-text rule hold everywhere.
def _text_node(text: str, marks: frozenset, href: str | None) -> dict:
    node: dict = {"type": "text", "text": text}
    ordered = [m for m in _MARK_ORDER if m in marks or (m == "link" and href)]
    if ordered:
        node["marks"] = [
            {"type": "link", "attrs": {"href": href}} if m == "link" else {"type": m}
            for m in ordered
        ]
    return node


# Justification: turns the resolved token tree into flat ADF nodes with accumulated marks
def _flatten(toks: list, marks: frozenset, href: str | None) -> list[dict]:
    out: list[dict] = []
    for tok in toks:
        if isinstance(tok, dict):
            out.append(_text_node(tok["ch"] * tok["n"], marks, href))
            continue
        kind = tok[0]
        if kind == "text":
            out.append(_text_node(tok[1], marks, href))
        elif kind == "code":  # code never combines with strong/em
            out.append(_text_node(tok[1], marks - {"strong", "em"} | {"code"}, href))
        elif kind == "br":
            out.append({"type": "hardBreak"})
        elif kind == "link":
            out.extend(_flatten(_emphasis(_scan(tok[1])), marks, tok[2]))
        else:
            out.extend(_flatten(tok[1], marks | {kind}, href))
    return out


# Justification: adjacent runs with identical marks collapse; empty text is not valid ADF.
def _merge(nodes: list[dict]) -> list[dict]:
    out: list[dict] = []
    for node in nodes:
        if node["type"] == "text":
            if not node["text"]:
                continue
            if out and out[-1]["type"] == "text" and out[-1].get("marks") == node.get("marks"):
                out[-1] = {**out[-1], "text": out[-1]["text"] + node["text"]}
                continue
        out.append(node)
    return out


# --------------------------------------------------------------------------- ADF to Markdown

_BLOCK_LEAD = re.compile(r"^(?:#{1,6}(?:\s|$)|[-+*](?:\s|$)|\d{1,9}[.)](?:\s|$)|[>~])")
_TASK_LEAD = re.compile(r"^\[[ x]\] ")
_RAW_LEAD = re.compile(r"^ {0,3}(?:>|<[A-Za-z/!?])")
_BLANK_LINE = re.compile(r"\n\s*\n")
_MARK_WRAP = (("code", "`"), ("em", "*"), ("strong", "**"))


def adf_to_md(doc: dict | None) -> str:
    """Render an ADF document as Markdown; None or an empty doc gives ''. Never raises on odd nodes."""
    if not isinstance(doc, dict):
        return ""
    return _join_blocks(_kids(doc))


# Justification: one place drops non-dict children, so no renderer needs its own guard for odd input.
def _kids(node: dict) -> list[dict]:
    content = node.get("content")
    return [c for c in content if isinstance(c, dict)] if isinstance(content, list) else []


# Justification: joins rendered blocks with one blank line and skips empty ones.
def _join_blocks(nodes: list) -> str:
    return "\n\n".join(out for out in (_block(n) for n in nodes) if out)


# Justification: one dispatch by node type; anything unknown degrades to its text, never dropped.
def _block(node: dict) -> str:
    kind = node.get("type")
    content = _kids(node)
    if kind == "heading":
        level = _level((node.get("attrs") or {}).get("level"))
        return f"{'#' * level} {_inlines(content, flat=True)}".rstrip()
    if kind == "paragraph":
        return _paragraph_md(content)
    if kind in ("bulletList", "orderedList"):
        return "\n".join(_list_lines(node, 0))
    if kind == "codeBlock":
        return _code_block(node)
    if kind == "table":
        return _table_md(content)
    return _paragraph_md([{"type": "text", "text": _text_of(node)}])


# Justification: Jira may send a non-numeric level; a heading must still render.
def _level(value: object) -> int:
    return min(max(value, 1), 6) if isinstance(value, int) else 1


# Justification: concatenates the text under any node so unknown nodes lose nothing.
def _text_of(node: dict) -> str:
    own = node.get("text")
    if isinstance(own, str):
        return own
    children = _kids(node)
    sep = " " if any(c.get("content") is not None for c in children) else ""
    return sep.join(_text_of(c) for c in children)


# Justification: keeps literal quote/HTML/rule paragraphs raw so they re-parse to themselves.
def _paragraph_md(content: list) -> str:
    if len(content) == 1 and content[0].get("type") == "text" and not content[0].get("marks"):
        text = content[0].get("text")
        text = text if isinstance(text, str) else ""
        # A literal paragraph made from a block quote or raw HTML re-parses to itself when emitted as is.
        if (_RAW_LEAD.match(text) or (_RULE.match(text) and "\n" not in text)) and not _BLANK_LINE.search(text):
            return text
    return _inlines(content, lead=True)


# Justification: renders a run of inline nodes; flags carry block/cell/list context.
def _inlines(
    content: list, *, lead: bool = False, cell: bool = False, task: bool = False, item: bool = False, flat: bool = False
) -> str:
    out: list[str] = []
    for n, node in enumerate(content):
        first = lead and n == 0
        out.append(_inline_node(node, first or (item and n == 0 and _RULE.match(_text_of(node)) is not None), cell, task and n == 0, flat))
    return "".join(out)


# Justification: inline dispatch; a hard break is backslash + newline, anything unknown is its text.
def _inline_node(node: dict, lead: bool, cell: bool, task: bool, flat: bool) -> str:
    if node.get("type") == "hardBreak":
        return " " if cell or flat else "\\\n"
    text = _text_of(node)
    marks = {m.get("type"): m for m in node.get("marks") or [] if isinstance(m, dict)}
    if "code" in marks:
        out = _code_md(text)
        marks.pop("strong", None)
        marks.pop("em", None)
        return _wrap_link(_wrap(out, marks), marks)
    body = _escape(text, lead=lead and not marks, cell=cell, task=task, flat=flat)
    return _wrap_link(_wrap(body, marks), marks)


# Justification: delimiters must hug non-space text, so edge whitespace moves outside them.
def _wrap(body: str, marks: dict) -> str:
    wraps = [d for kind, d in _MARK_WRAP if kind in marks and kind != "code"]
    if not wraps or not body.strip():
        return body
    core = body.strip(" \t")
    head, tail = body[:len(body) - len(body.lstrip(" \t"))], body[len(core) + len(body) - len(body.lstrip(" \t")):]
    for d in wraps:
        core = d + core + d
    return head + core + tail


# Justification: link mark is always the outermost wrapper, so it is applied last.
def _wrap_link(body: str, marks: dict) -> str:
    link = marks.get("link")
    if not link:
        return body
    href = str((link.get("attrs") or {}).get("href", ""))
    href = re.sub(r"([\\()])", r"\\\1", href).replace(" ", "%20")
    return f"[{body}]({href})"


# Justification: a code span needs a backtick fence longer than any run inside, padded at the edges.
def _code_md(text: str) -> str:
    text = text.replace("\n", " ")
    runs = [len(r) for r in _BACKTICKS.findall(text)]
    fence = "`" * next(n for n in range(1, len(text) + 3) if n not in runs)
    pad = " " if text[:1] == "`" or text[-1:] == "`" or (text[:1] == text[-1:] == " " and text.strip()) else ""
    return f"{fence}{pad}{text}{pad}{fence}"


# Justification: escaping is context-aware (flanking) so `snake_case` and `2 * 3` stay unescaped.
def _escape(text: str, *, lead: bool = False, cell: bool = False, task: bool = False, flat: bool = False) -> str:
    lines = text.split("\n")
    out = []
    for n, line in enumerate(lines):
        out.append(_escape_line(line, lead=(lead if n == 0 else True), cell=cell, task=task and n == 0))
    return " ".join(out) if cell or flat else "\\\n".join(out)


# Justification: per-line escaping lets each line of a multi-line text re-check block-leading markers.
def _escape_line(text: str, *, lead: bool, cell: bool, task: bool) -> str:
    out: list[str] = []
    skip_to = 0
    if lead and not (task and _TASK_LEAD.match(text)):
        digits = re.match(r"\d+", text)
        if digits and _BLOCK_LEAD.match(text):
            out.append(digits.group() + "\\")
            skip_to = digits.end()
        elif _BLOCK_LEAD.match(text) or text.startswith("~~~") or _RULE.match(text):
            out.append("\\" + text[0])
            skip_to = 1
    n = len(text)
    i = skip_to
    while i < n:
        c = text[i]
        if c in "*_":
            j = i
            while j < n and text[j] == c:
                j += 1
            out.append(("\\" + c) * (j - i) if _delimiter(text, i, j, c) else text[i:j])
            i = j
            continue
        if c == "[" and task and i == 0 and _TASK_LEAD.match(text):
            out.append("[ ] " if text[1] == " " else "[x] ")
            i = 4
            continue
        if c in "\\`[]" or (c == "|" and cell):
            out.append("\\" + c)
        elif lead and i == 0 and c == "~" and text.startswith("~~~"):
            out.append("\\" + c)
        else:
            out.append(c)
        i += 1
    return "".join(out)


# Justification: a run is risky if it could open or close emphasis in any neighbouring context.
def _delimiter(text: str, i: int, j: int, ch: str) -> bool:
    prevs = [text[i - 1]] if i else ["", "!"]
    nexts = [text[j]] if j < len(text) else ["", "!"]
    return any(any(_flanking(p, q, ch)) for p in prevs for q in nexts)


# Justification: fence length is derived from content so no content line can close it early (A5).
def _code_block(node: dict) -> str:
    code = "".join(_text_of(c) for c in _kids(node))
    lang = str((node.get("attrs") or {}).get("language") or "")
    if re.search(r"[\s`]", lang):
        lang = ""
    longest = max((len(r) for r in _BACKTICKS.findall(code)), default=0)
    fence = "`" * max(3, longest + 1)
    return f"{fence}{lang}\n{code}\n{fence}"


# Justification: recursion over nested lists with an absolute indent keeps sibling sub-lists apart.
def _list_lines(node: dict, indent: int) -> list[str]:
    ordered = node.get("type") == "orderedList"
    lines: list[str] = []
    pad = " " * indent
    for n, item in enumerate(_kids(node), 1):
        marker = f"{n}." if ordered else "-"
        texts: list[str] = []
        children = _kids(item)
        sublists = [c for c in children if c.get("type") in ("bulletList", "orderedList")]
        for child in children:
            if child in sublists:
                continue
            if child.get("type") == "paragraph":
                texts.append(_inlines(_kids(child), task=not texts, item=not texts))
            else:
                texts.append(_escape(_text_of(child)))
        lines.append(f"{pad}{marker} {' '.join(texts)}".rstrip() if texts else f"{pad}{marker}")
        # Sibling sub-lists of one item must not merge on re-parse: earlier ones sit deeper than later ones.
        for k, sub in enumerate(sublists):
            lines += _list_lines(sub, indent + 2 * (len(sublists) - k))
    return lines


# Justification: tables need a header, separator and padded rows; kept apart from block dispatch.
def _table_md(rows: list) -> str:
    grid = [[_inlines(_cell_inlines(c), cell=True) for c in _kids(r)] for r in rows]
    width = max((len(r) for r in grid), default=0)
    if not width:
        return ""
    grid = [r + [""] * (width - len(r)) for r in grid]
    fmt = lambda r: "| " + " | ".join(r) + " |"  # noqa: E731
    return "\n".join([fmt(grid[0]), fmt(["---"] * width)] + [fmt(r) for r in grid[1:]])


# Justification: a cell holds block children; their inline content is flattened into one line.
def _cell_inlines(cell: dict) -> list:
    out: list = []
    for child in _kids(cell):
        if out:
            out.append({"type": "text", "text": " "})
        out += child.get("content") or [{"type": "text", "text": _text_of(child)}]
    return out
