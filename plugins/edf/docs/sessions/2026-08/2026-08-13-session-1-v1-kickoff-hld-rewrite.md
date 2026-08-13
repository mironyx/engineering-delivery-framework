# Session Log — V1 Kickoff and HLD Rewrite

## Summary

Ran `/kickoff` on `v1-requirements.md` to rebuild V1's design foundation after
requirements v1.1 invalidated most of the existing HLD. Produced a rewritten
HLD (v1.1), one ADR, an epic-shaped plan, and a reconciled board.

The session began as `/architect` — the user asked for LLDs and issues. Analysis
found the HLD contradicted the requirements it was supposed to serve, so the
work was redirected to `/kickoff` first. That redirection was the highest-value
decision of the session: generating twelve task issues against a design
describing a retired architecture would have propagated the contradiction into
every downstream artefact, and `/pr-review` and `/lld-sync` both read the HLD
later.

## Why the HLD needed a rewrite, not a patch

`v1-design.md` v0.2 was built on the `edf://` custom URL scheme and a VSCode
extension that would intercept it for hover-preview and open-beside. A spike
recorded in ADR-0038's rejection note had already falsified both premises:

1. Mermaid runs its sanitizer at `securityLevel: strict` and strips the `href`
   for any unrecognised scheme, in **every** diagram type. `edf://` never
   reached the DOM.
2. `vscode.window.onDidReceivePreviewMessage`, the API the entire `postMessage`
   architecture depended on, does not exist in the public VS Code API.

Roughly half the document described that system: capabilities C4, C5 and C8,
component C2.4's whole responsibility set, and Flows 2, 3, 5 and 6. A patch
would have left a document arguing with itself.

## Approach rationale

**Requirements as authority over the HLD.** With the input being a requirements
doc rather than a plan, ADR-0022's tiered process makes requirements the scope
authority. Every capability was rederived from the ten REQ anchors rather than
salvaged from v0.2, which is why the new C5 (conformance evidence) and C7
(installable build) exist — v0.2 had no capability for either, despite Stories
1.6 and 2.2 needing them.

**One ADR, not two.** An extension-architecture ADR was proposed and then
dropped after the user challenged whether any ADR was needed. The challenge was
correct: extension scope is already Design Principle 5, distribution is Design
Principle 7 plus Story 2.2's Notes, and the test runner is Story 2.2 AC1. An ADR
transcribing approved requirements adds a document without adding a decision.
Nothing needed superseding either — ADR-0038 is *Rejected*, so it binds nothing.

ADR-0039 survived that test on three grounds the other lacked: the decision was
already gotten wrong once at real cost (an HLD, a template section, a skill
section and ~250 lines of extension); its rationale is empirical and perishable,
being a measured fact about Mermaid 11.12.2; and ADR-0038's rejection note
explicitly deferred it to this gate.

**Scaffold questions pushed down, not settled.** Whether to delete or quarantine
`extensions/edf-review/` is a task-level call, reversible from git history. It
was recorded as HLD Open Questions 1 and 2 and routed to Epic E1.2's LLD rather
than inflated into an architecture decision.

## Gate findings worth keeping

**Gate 1 (`edf:hld-review` + drift scan) — 2 blockers, 14 warnings.** Both
blockers were missing components rather than wrong ones: C7 had no owner, and
relative-path resolution — the single behaviour C4's entire claim rests on — was
owned by nothing, since C2.5 scoped itself to Mermaid parsing only. Added C2.7
(Extension Build and Test Harness) and C2.8 (Host Markdown Renderer).

The drift scan's sharpest observation: **C2.5's non-responsibilities are the
causal spine of the design.** "The sanitizer strips unrecognised schemes" is the
sole justification for workspace-relative paths — delete it and C4's central
choice becomes an unexplained preference, which is exactly how v0.2 shipped
`edf://`.

**Gate 2 (drift scan) — 1 critical, 10 warnings.** The critical finding was a
structural flaw in the plan: Stories 1.1–1.4 sit in Epic E1.1, but their
acceptance criteria are phrased as *generation* behaviour ("when `/lld` Step 2
evaluates the feature's characteristics…"), which is component C2.2 — owned by
E1.3. E1.1's exit criteria were template-scoped, so **E1.1 could have been
marked done with four stories still open**, or silently absorbed skill work and
collided with E1.3 in `SKILL.md`, breaking the parallelisation claim.

Fixed with an explicit closure seam rather than a re-shuffle, because the split
is deliberate — the HLD states it in C2.1's non-responsibilities, and the
requirements encode it by giving Story 3.1 the generation side of the same
concerns. Stories 1.1–1.4 now close in two halves: definition (E1.1,
`template.md`) and application (E1.3, `SKILL.md`), neither epic closing them
alone.

The same scan caught that the plan said "the two prohibitions" where ADR-0039's
matrix has three parse-error cases, and that the path-form constraint had a
*check* in E1.3 but no *definition* in E1.1 — a check against an undefined rule.

## Requirements defects found

Two, both fixed:

- **Story 1.3 AC5 named GitLab** while Story 1.6's Notes said GitLab is not
  verified in V1. The HLD had silently followed 1.6. As written, AC5 was an
  acceptance criterion no component owned and no verification exercised — it
  would have passed by assumption, the same failure mode as `edf://`. Struck in
  requirements v1.2.
- **The requirements' implementation note claimed** `template.md` and `SKILL.md`
  "already carry the click-support-matrix fix". They do not — both still use
  `link … @ edf://` for sequence diagrams and `click X href "…" "tooltip"`
  elsewhere, with no `stateDiagram-v2` or `erDiagram` rule. Stories 1.4 and 3.1
  are full implementation work, not verify-and-harden. Recorded in the plan's
  task shapes.

## Open thread

The sequence-diagram `link` directive (distinct syntax from `click`) was never
tested — ADR-0038 measured only `click`. The current template uses `link`, and
the rejection note attributes a render failure to `click` in a snippet
containing none. The user's recollection is that it caused problems with
`edf://`, which is consistent with the sanitiser finding. Recorded in ADR-0039
as deliberately not used, with the reasoning that the Structural Overview
already provides a click path to the same components. If sequence-diagram
navigability is ever wanted, this is where to start.

## Work completed

| Artefact | Path |
|---|---|
| HLD (rewritten, v1.1) | `plugins/edf/docs/design/v1/v1-design.md` |
| ADR-0039 (Accepted) | `plugins/edf/docs/adr/0039-workspace-relative-paths-for-diagram-navigability.md` |
| Implementation plan | `plugins/edf/docs/plans/2026-08-13-v1-implementation-plan.md` |
| Requirements v1.2 | `plugins/edf/docs/requirements/v1-requirements.md` |

Board: #28 → Epic E1.1, #30 → Epic E1.2, #31 → Epic E1.3 (all rewritten,
`version:v1` added). Closed #29 (dissolved epic) and its orphaned tasks #34,
#37, #41, #42. Task issues #32, #33, #35, #36, #38, #39, #40 left for
`/architect` to reconcile.

Commits: `7f50d8f`, `b591c3b`, `677b225`, `7906b5d`, `c4a8a99`, `1942c88`,
`ac95d30`.

## Drift-scan verdicts

- **Gate 1:** 10/10 REQ anchors covered, no scope creep, no capability without a
  requirement. 1 critical (GitLab), 7 warnings — all resolved before sign-off.
- **Gate 2:** 10/10 anchors each claimed by exactly one epic, 8/8 capabilities
  and 8/8 components owned. 1 critical (story closure seam), 10 warnings — all
  resolved.

## Next step

`/architect plugins/edf/docs/plans/2026-08-13-v1-implementation-plan.md` to
produce per-epic LLDs, coverage manifests and task issues. E1.1 and E1.2 can
start in parallel; E1.3 follows E1.1.
