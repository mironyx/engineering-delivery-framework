# Renderer Conformance Report

## Document Control

| Field | Value |
|-------|-------|
| Version | 1.0 |
| Status | Committed evidence |
| Author | LS / Claude |
| Measured | 2026-08-15 |
| Issue | [#47](https://github.com/mironyx/engineering-delivery-framework/issues/47) |
| Epic | [#28](https://github.com/mironyx/engineering-delivery-framework/issues/28) |
| Design reference | [lld-v1-e1-1-template-vocabulary.md §1.3](lld-v1-e1-1-template-vocabulary.md) |
| Fixture under test | [conformance-fixture.md](conformance-fixture.md) |
| Harness | [tests/conformance/check-diagrams.mjs](../../../../../tests/conformance/check-diagrams.mjs) |

---

## Headline

**The mechanical checks pass, and the GitHub navigability premise does not hold.**

Every diagram in the fixture parses, renders, and emits exactly the anchors it declares under
the pinned Mermaid version. But on GitHub, mermaid diagrams are rendered inside a
**cross-origin sandboxed iframe**, so a document-relative `click` href resolves against
`viewscreen.githubusercontent.com` instead of against the document's directory in the repo —
and returns HTTP 404. In VS Code's markdown preview, an anchor inside a rendered SVG is not
recognised by the preview's link handler at all.

So under both hosts, **neither link form navigates today**. The diagrams render correctly and
carry correct hrefs; the hosts do not act on them. This is the same failure class the epic
exists to remove — a rule that reads sensibly, parses, renders, and does nothing — found one
level further out than D1–D6 looked.

This does not invalidate the conventions in `template.md`: the hrefs it produces are correct,
minimal and inspectable, and they resolve correctly under document-relative semantics wherever
those semantics are actually applied. It does mean
[v1-design.md §C4](v1-design.md#c4-renderer-native-navigable-diagram-surface) ("Renderer-Native
Navigable Diagram Surface") currently claims a capability neither host delivers. See
[Follow-ups](#follow-ups).

---

## Pinned versions

| Surface | Version | How established |
|---|---|---|
| `mermaid` (harness) | `11.12.2` | Pinned exactly in `tests/conformance/package.json`; `npm ls` confirms `mermaid@11.12.2` |
| `dompurify` | `3.4.13` | Resolved from `^3` |
| `@braintree/sanitize-url` | `7.1.2` | Resolved from `^7` |
| `jsdom` | `26.1.0` | Harness host |
| Node.js | `25.8.2` | Harness runtime |
| VS Code (pinned by the LLD) | `1.121` | External Surfaces table, [lld-v1-e1-1-template-vocabulary.md](lld-v1-e1-1-template-vocabulary.md) |
| VS Code (actually measured) | `1.127.0` | `code --version` on the measuring machine |
| VS Code bundled mermaid | `11.15.0` | `mermaid-markdown-features@10.0.0`, version string in `markdown-preview-out/index.js` |
| GitHub markdown renderer | undated | `viewscreen.githubusercontent.com/markdown/mermaid`, observed 2026-08-15 |

> **Version drift already present.** The LLD pins VS Code `1.121` bundling mermaid `11.12.2`.
> The machine this report was measured on runs VS Code `1.127.0`, whose bundled mermaid is
> **`11.15.0`** — not the harness's `11.12.2`. The host renderer and the harness are therefore
> already one minor version apart. Nothing in the results below turned on that gap, but it is
> exactly the drift the re-verification trigger exists to catch, and it was found by measuring
> rather than by reading the pin.

### Re-verification trigger

**A change to either pinned version — Mermaid `11.12.2` or VS Code `1.121` — invalidates this
report and requires re-measurement.** Re-run the harness and repeat the two host observations.
Because the VS Code figure has already drifted to `1.127.0` / mermaid `11.15.0`, the VS Code
rows below should be treated as due for re-measurement at the next touch of this epic.

Re-run the machine-checkable half with:

```sh
node tests/conformance/check-diagrams.mjs plugins/edf/docs/design/v1/conformance-fixture.md
node tests/conformance/check-diagrams.mjs --template plugins/edf/skills/lld/template.md
```

---

## Per diagram type, per renderer, both link forms

Link forms: **path** = document-relative path (`../…`); **frag** = `#LLD-` anchor fragment.
"Anchors" is the count of `<a href>` elements in the rendered SVG, against the count of `click`
directives declared in the block.

### Mermaid 11.12.2 (harness, `securityLevel: 'strict'`)

| Diagram type | Link form | Clicks declared | Anchors rendered | Result |
|---|---|---|---|---|
| `sequenceDiagram` | none — negative case | 0 | 0 | **pass** — no click emitted, diagram parses and renders |
| `stateDiagram-v2` | path + frag | 2 | 2 | **pass** — `click` without `_self` |
| `flowchart` | path + frag | 3 | 3 | **pass** |
| `classDiagram` | path + frag | 5 | 5 | **pass** — includes the nested-depth path |
| `erDiagram` | none — negative case | 0 | 0 | **pass** — no click emitted, no anchor generated |

### GitHub

Rendered at `viewscreen.githubusercontent.com` in a cross-origin sandboxed iframe, one iframe
per fenced block. Measured with a headless browser against the pushed branch.

| Diagram type | Link form | Anchors in SVG | Href preserved | Navigates on click | Result |
|---|---|---|---|---|---|
| `sequenceDiagram` | none — negative case | 0 | — | — | **pass** — nothing emitted, nothing broke |
| `stateDiagram-v2` | path | 2 (total) | yes, verbatim | **no** — resolves off-origin | **fail** |
| `stateDiagram-v2` | frag | — | yes, verbatim | **no** — resolves inside the iframe | **fail** |
| `flowchart` | path | 3 (total) | yes, verbatim | **no** — resolves off-origin | **fail** |
| `flowchart` | frag | — | yes, verbatim | **no** — resolves inside the iframe | **fail** |
| `classDiagram` | path | 5 (total) | yes, verbatim | **no** — resolves off-origin | **fail** |
| `classDiagram` | frag | — | yes, verbatim | **no** — resolves inside the iframe | **fail** |
| `erDiagram` | none — negative case | 0 | — | — | **pass** — no click, no anchor |

Anchor counts on GitHub match the harness exactly (0 / 2 / 3 / 5 / 0), and GitHub does not
rewrite or strip the hrefs. The failure is entirely one of **base URL**:

| Authored href | Resolves to on GitHub | HTTP |
|---|---|---|
| `../../../skills/lld/template.md` | `https://viewscreen.githubusercontent.com/skills/lld/template.md` | **404** (confirmed) |
| `../../../../../CLAUDE.md` | `https://viewscreen.githubusercontent.com/CLAUDE.md` | **404** (confirmed) |
| `#LLD-v1-e1-1-fixture-report` | `…/markdown/mermaid?…#LLD-v1-e1-1-fixture-report` | in-iframe no-op |

Each anchor carries `target="_parent"`, so a click navigates the whole tab to that 404 rather
than failing quietly in the frame. Extra `..` segments do not help — they clamp at the origin
root, so **no** number of `..` segments can reach the repository from that iframe.

> **Method and limitation.** Anchor presence, href values, `target`, the resolved absolute URLs
> and the 404 status were all measured directly. A live click-through was attempted but the
> mermaid iframes load lazily and the click did not reproduce reliably in headless mode, so the
> "navigates on click" column is an inference from the resolved URL plus the confirmed 404 plus
> `target="_parent"` — not from an observed navigation. Stated explicitly rather than rounded up.

### VSCode preview

| Diagram type | Link form | Anchor in SVG | Preview handler acts on it | Result |
|---|---|---|---|---|
| `sequenceDiagram` | none — negative case | 0 | — | **pass** |
| `stateDiagram-v2` | path + frag | yes | **no** | **fail** |
| `flowchart` | path + frag | yes | **no** | **fail** |
| `classDiagram` | path + frag | yes | **no** | **fail** |
| `erDiagram` | none — negative case | 0 | — | **pass** |

### VSCode native-open finding — **no**

| Finding | Value |
|---|---|
| Does a relative *file* link clicked inside a rendered Mermaid SVG open natively in VS Code's markdown preview? | **no** |

Recorded as `no`, measured rather than recalled. VS Code 1.127.0's markdown preview registers a
document-level click handler that walks up from the event target and acts only when
`t.tagName === "A" && t.href`. An SVG anchor is not an `HTMLAnchorElement`: its `tagName` is the
lowercase `"a"` (SVG is case-sensitive XML) and it exposes no `.href` *property*, only the
attribute. Both conditions fail, so the preview never posts its `openLink` message and the click
falls through.

Reproduced by rendering the fixture's flowchart with mermaid, injecting the SVG into a document
alongside an ordinary markdown link as a positive control, and running the shipped handler's
logic verbatim:

| Link | `tagName` | Handler verdict |
|---|---|---|
| Ordinary markdown link | `"A"` | `openLink` → VS Code opens the file natively |
| Anchor inside the mermaid SVG | `"a"` | no match → no `openLink`, click falls through |

This answers the open question the LLD flagged as the sole unverified cell in
[v1-design.md §C2.8](v1-design.md#c28-host-markdown-renderer). It is a `no`.

> **Method and limitation.** Measured against the handler source shipped in VS Code 1.127.0
> (`markdown-language-features/media/index.js`) reproduced faithfully in jsdom with a positive
> control, not by clicking in the live GUI. The DOM facts it turns on — SVG `tagName` casing and
> the absence of an `.href` property — are not version-specific.

---

## Nested-depth relative link (D1)

The row that would have caught the ADR-0039 defect. The fixture links from
`plugins/edf/docs/design/v1/` to the repository root — **five** `..` segments, well past the
three the acceptance criteria require:

| Property | Result |
|---|---|
| Href as authored | `../../../../../CLAUDE.md` |
| Parses under mermaid 11.12.2 | **yes** |
| Renders as an anchor with the href intact | **yes** |
| Resolves under document-relative semantics | **yes** — to the repository-root `CLAUDE.md`, which exists |
| Inside `design-root` | **yes** |
| Under ADR-0039's superseded form (`plugins/edf/…`, no `..`) | **would 404** — resolves to `plugins/edf/docs/design/v1/plugins/edf/…` |
| Resolves on GitHub | **no** — `https://viewscreen.githubusercontent.com/CLAUDE.md`, HTTP 404 |

The harness's containment and existence checks pass on it, confirming D1's adopted form is the
correct one *as a path form*. The GitHub column is a separate defect, in the host, not the form.

A shorter three-segment link (`../../../skills/lld/template.md`) is also present and behaves
identically, so the result is not an artefact of the depth chosen.

---

## Palette distinguishability

All four palette roles — `error`, `auth`, `external` and `new` — were rendered and their
computed fills inspected. **All four are distinguishable from each other and from the default
node fill in both renderers**, with the one type-specific exception noted below.

| Role | Fill | Mermaid 11.12.2 (harness) | GitHub (computed fill) | VSCode preview |
|---|---|---|---|---|
| `error` | `#f7d6d6` | CSS rule emitted | `rgb(247, 214, 214)` — distinguishable | same engine as harness |
| `auth` | `#f7eed6` | CSS rule emitted | `rgb(247, 238, 214)` — distinguishable | same engine as harness |
| `external` | `#d6e8f7` | CSS rule emitted | `rgb(214, 232, 247)` — distinguishable | same engine as harness |
| `new` | `#d4f0d4` | CSS rule emitted | `rgb(212, 240, 212)` — distinguishable | same engine as harness |

On GitHub the fixture's flowchart yields six distinct computed fills — all four palette colours
plus the default node fill and the text fill — confirming that no two roles collapse to the same
rendered colour. The `stateDiagram-v2` block shows the two roles it uses (`error`, `new`),
matching its source.

The VSCode column is recorded as "same engine as harness" rather than measured independently:
VS Code renders through a bundled mermaid (`11.15.0`) with the same `classDef` mechanism, and
palette application is a mermaid-level behaviour, not a host behaviour — unlike navigation,
which is where the two hosts diverge.

> **Per-block `classDef` confirmed necessary (D6).** Every diagram in the fixture repeats the
> `classDef` lines it uses, and each block's referenced roles all resolve to an emitted CSS rule.
> The harness fails a block whose `class` statement names a role the same block never declared,
> so D6 cannot silently regress.

> **`classDef` does not apply to `classDiagram` at all.** Measured on 11.12.2: a `classDiagram`
> carrying `classDef new …` plus `class Harness new` in the same block emits **no** CSS rule and
> **no** palette fill — the node is not even given the class attribute. The `cssClass "A,B" new`
> form does attach the attribute but still produces no rule or fill. Separately, the comma-list
> form `class A,B role` is a **parse error** in `classDiagram`, though it is valid in `flowchart`
> and `stateDiagram-v2`. The fixture's `classDiagram` therefore carries no palette classes, by
> design. See [Follow-ups](#follow-ups).

---

## Sanitiser gates

Re-measured independently, confirming ADR-0039's finding (LLD D3). Each URL is pushed through
`@braintree/sanitize-url`, DOMPurify's SVG profile, and a real `mermaid.render` — the third gate
being the only one that proves what reaches the DOM.

| URL | Survives | Expected | Result |
|---|---|---|---|
| `../../../skills/lld/template.md` | yes | yes | **pass** |
| `#LLD-v1-e1-1-fixture-report` | yes | yes | **pass** |
| `https://mermaid.js.org/config/usage.html` | yes | yes | **pass** |
| `edf://src/lib/example/service.ts` | **no** | no | **pass** — stripped, never reaches the DOM |
| `javascript:alert(1)` | **no** | no | **pass** — stripped |

Both negative controls are stripped exactly as ADR-0039 reports, which is what makes the
positive rows credible rather than a harness artefact.

---

## `template.md` conformance (read-only)

Run as `--template`, which treats example paths and fragments as illustrative placeholders
(LLD Invariant 4) while enforcing parse, render, anchor-form, D5 and D6 in full.

| Check | Result |
|---|---|
| Every fenced mermaid block parses | **pass** |
| Rendered anchors equal declared clicks | **pass** — 2 clicks, 2 anchors |
| All four palette roles emit CSS rules | **pass** |
| `#LLD-` fragment form | **pass** |
| Example paths resolve | placeholders, as designed |

T1 (#45) and T2 (#46) are confirmed correct on every mechanical check. Two defects were found
in `template.md` that are **not** fixed here — this task is read-only on that file, by
constraint. See [Follow-ups](#follow-ups).

---

<a id="follow-ups"></a>

## Follow-ups

Each needs its own issue. None is fixed in #47.

1. **GitHub renders mermaid in a cross-origin iframe, so no diagram link navigates.**
   Highest priority, because it challenges the premise of
   [§C4](v1-design.md#c4-renderer-native-navigable-diagram-surface) rather than an
   implementation detail. This needs a decision, not a patch: keep the links as correct,
   inspectable metadata that works wherever document-relative semantics apply and accept that
   GitHub does not honour them; or drop the navigability claim from the HLD; or pursue a
   host-specific mechanism. Evidence is in this report.

2. **`template.md`'s outer ```` ```markdown ```` fence closes prematurely.**
   The fence opened at line 10 is closed at **line 322** — the closing fence of the nested
   `stateDiagram-v2` example, which is written bare rather than with the `` `` `` escape the
   other inner examples use. Everything from line 323 on therefore renders as *live markdown*
   rather than as template source: the flowchart at 335–360 renders as a real diagram, and the
   fence opened at line 707 is never closed. Pre-existing — `git blame` dates both unescaped
   fences to 2026-08-02, well before this epic, so it was not introduced by #45 or #46.
   Consequence: the harness sees only **one** renderable mermaid block in `template.md`, so the
   other worked examples are never machine-checked.

3. **State the `classDiagram` palette and comma-list constraints in `template.md`.**
   `classDef` styling does not reach `classDiagram` nodes at all on 11.12.2, and `class A,B role`
   is a parse error there while valid elsewhere. An author following the palette section will
   write a `classDiagram` that parses, renders, and is silently unstyled — the D6 failure mode
   again, this time type-specific rather than block-specific.

---

## Harness self-finding

Worth recording because it is the same failure class, one level up.

The harness's first implementation counted anchors by parsing the rendered SVG as
`image/svg+xml`. When a node label contains `<br/>`, mermaid emits it into a `foreignObject` as
unclosed `<br>` — valid HTML, invalid XML. The XML parse therefore returned a `parsererror`
document and **zero** anchors, and the harness confidently reported two perfectly good diagrams
as having silently lost every link. The checker parsed successfully and was measuring the wrong
thing.

Fixed by parsing as `text/html`. The lesson is the epic's own: a green or red result is only
worth what its measurement method is worth, and the method has to be checked against a case
where the answer is already known.
