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
