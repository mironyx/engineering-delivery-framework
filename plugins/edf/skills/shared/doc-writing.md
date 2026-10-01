# Document Writing Guide

Shared rules for every skill that writes a document (discovery, requirements, HLD, plan, ADR,
LLD, issue bodies, reports, session logs). Review agents use the same rules to flag waste.

**Concise, never thin.** Every line must help the reader decide, build, or verify. Cut
everything else — but never cut substance to hit a length.

## Never cut (the quality floor)

- Decisions, and the reason when it is not obvious.
- Contracts: signatures, types, schemas, payloads, file paths.
- Invariants with their verification method; acceptance criteria including negative cases.
- Edge cases, failure modes, constraints a later reader would otherwise violate.
- Rejected alternatives someone would otherwise re-propose (one line each).
- Open questions and explicit deferrals.

If a rule below conflicts with this list, this list wins.

## Cut (waste patterns)

| Pattern | Instead |
|---|---|
| Restating another doc (requirements, HLD, ADR, template, kb/) | Link with an anchor. One clause of context at most |
| Prose that narrates a diagram or table line by line | Keep the diagram; add only what it cannot show |
| Preamble and meta — "This section describes…", "As noted above", "It is important to note" | Start with the content |
| The same constraint in Purpose, Invariants, ACs, and Tasks | State once, reference by ID |
| Headings for sections that do not apply, filled with "N/A" / "None" / "See HLD" | Omit the heading. If the template mandates it, one line saying why it is empty |
| Revision history or how-we-got-here narrative in the body — "v1.4 did X", "this replaces DP3", "simplified from the earlier design" | Rewrite to the current state. Withdrawn scope gets one line in the out-of-scope list |
| Change Log / Document Control rows that tell how a problem was found, list small fixes, or restate the body | Routine revision: one line — what changed, by section or story ID. Shape change (a decision withdrawn or reversed, scope moved): a short paragraph — what changed, why, and the trade accepted, for readers of the earlier version |
| Resolved open questions kept with their deliberation | Fold the decision into the body (principle, glossary, AC) with a one-line reason; delete the question |
| Process records in the deliverable — testability reports, review-fix lists, next-step todo lists | Put them in the gate presentation or session log, not the document |
| A paragraph justifying an omission — "No diagram: the gate's negative case applies because…" | Omit silently, or one line naming the absent signal |
| An AC with a parenthetical defending itself — "(per DP6 — a valid state, not an error)" | The condition only; cite the principle ID if the reason matters |
| Generic best practice, standard-library behaviour, restating the skill's own rules | Omit — the reader already has it |
| Summary sections that repeat the body; closing recaps | One summary at most, at the top |
| Justification padding — "This ensures that…", "This is important because…" after an obvious point | Delete the sentence |
| One-row tables, one-item lists, nested bullets restating the parent | Plain sentence |

## Size to the change

Length tracks the number of decisions and contracts, not the number of template sections. A
docs-only or single-file change gets a short document; do not expand it to fill the template.
Inflating a small idea into enterprise-scale analysis is a defect, not thoroughness.

## Style

- Lead with the conclusion, then the detail.
- Prefer a diagram to prose for flows, structure and state; do not then narrate it in prose.
- Tables for comparisons and mappings; bullets for lists; prose only for reasoning.
- Specific nouns over abstractions — "returns 409 with `{error: 'stale'}`", not "handles conflicts appropriately".

## Self-edit before writing (mandatory)

Before writing or presenting the document at a gate, re-read the draft once against the waste
table. For each sentence ask: *would the reader lose anything if this were gone?* If not,
delete it. Then check the quality floor is still intact.
