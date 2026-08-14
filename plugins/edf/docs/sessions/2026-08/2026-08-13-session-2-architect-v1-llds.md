# Session Log — V1 Architect: Three Epic LLDs

## Summary

Ran `/architect` on `2026-08-13-v1-implementation-plan.md` across all three V1
epics. Produced three LLDs, three coverage manifests, nine task issues, and
three rewritten epic bodies. Closed seven stale task issues from the pre-rewrite
run.

The session's defining feature was that **three of the claims the epics were
commissioned to encode turned out to be false**, and all three were caught by
measuring rather than reading. Two were in the inputs (ADR-0039 and the
implementation plan); one was in this session's own output.

## The measurement detour

Before authoring, a read of ADR-0039 surfaced an internal contradiction: it
mandates a "workspace-relative path … no leading slash and no `..` segments",
illustrated as `src/lib/auth/helper.ts`, while its own Cons note that resolution
"depends on the document's own location". Both cannot hold. Relative links
resolve against the containing document's directory, so the mandated form
resolves to `plugins/edf/docs/design/v1/plugins/edf/skills/…` from an LLD — a
404 for every source link the framework would ever generate.

The user pushed back on proceeding by argument and asked whether it could be
tested. It could, and doing so changed the design three times.

### What was measured

A harness built from `mermaid@11.12.2` (the version ADR-0039 pins), `dompurify@3`,
`@braintree/sanitize-url@7` and `jsdom` — parse checks, both sanitiser gates, and
filesystem path resolution.

| Finding | Status |
|---|---|
| **D1** — ADR-0039's path form 404s from a nested document | Confirmed defect |
| **D2** — the sequence-diagram `link` directive parses fine | Plan's claim false |
| **D3** — the other nine `click`-matrix rows | Confirmed |
| **D4** — a `;` inside `Note` text is a parse error | New finding |

Both negative controls (`edf://` and `javascript:` stripped by the sanitiser)
reproduced ADR-0039's headline result, which is what makes the one mismatch
credible rather than a harness artefact.

## Why each finding mattered

**D1 — the path form.** ADR-0039's measured claims are sound; its *path-form
constraint* was never measured. That is the same failure the ADR was written to
correct, recurring one level down. Adopted: document-relative paths with `..`
permitted, and the ADR's safety intent preserved by a containment check —
a link must resolve inside a declared `design-root` — rather than a syntactic ban.

The `design-root` framing came from the user, who observed that in a monorepo the
base should be a module root rather than the repository root. That is a better
rule than "must stay inside the repo": from this LLD, `../../../` lands exactly on
`plugins/edf/`, so an EDF LLD linking to EDF sources never needs the repo root at
all, and a module-root rule additionally catches cross-module links.

> **Recorded for the implementer:** `design-root` for *this* repository is
> nonetheless the **repository root**, not `plugins/edf/`. Every E1.1 and E1.3
> task must edit `.claude-plugin/marketplace.json`, which sits outside the plugin
> module. The narrower choice looks more natural and is wrong here.

**D2 — the `link` directive.** The implementation plan instructed this epic to
encode "all three parse-error cases (`sequenceDiagram` fatal on `click` *and* on
the `link` directive…)". ADR-0039 never claimed that — it says `link` is unused
by *choice* and explicitly notes it "is not re-evaluated with a workspace-relative
path in V1". The plan converted a design choice into a parse fact, and both the
`/lld` instructions and epic #28's exit criteria inherited it.

Left unmeasured, that would have entered `template.md` as a normative parse rule
and E1.3's self-critique gate as a grep for a non-existent error — a check that
reports a non-error trains authors to ignore the section it lives in.

**D4 — semicolons.** Found by running the harness against this session's own
first-draft LLD. Two of its sequence diagrams failed to parse, and the
enforcement-annotation examples it specified for `template.md` used
`mechanism; rejection` — which does not render. Fixed, and promoted to a
normative rule in E1.1 T2 and a parse check in E1.3 T2.

That D4 was caught at all is the argument for E1.1's T3 existing: it is the first
defect the conformance harness found in real content, and it was in content
written by the same process that would have shipped it.

## Decomposition

Nine tasks across three epics. Sizing followed the shared-file rule more than the
line-count rule — E1.1's and E1.3's tasks all write one file each
(`template.md`, `SKILL.md`), so they serialise regardless of logical coupling,
and the split buys reviewability rather than parallelism.

| Epic | Tasks | Issues |
|---|---|---|
| E1.1 #28 | link forms → gates/palette/annotations → conformance | #45, #46, #47 |
| E1.2 #30 | scaffold+harness → pure modules → command → packaging | #48–#51 |
| E1.3 #31 | Step 2 rules → Step 2.5 gate | #52, #53 |

E1.2's two pure modules were merged into one task (~170 lines combined, below the
split bar); the previous run had them as separate issues.

## Parallelism vs. kickoff's map

The plan warned that the shared `plugin.json` / `marketplace.json` bumps might
serialise E1.1 and E1.3 more tightly than epic ownership suggests. File-level
analysis confirms the hazard but finds **no additional serialisation needed** —
E1.3 already depends on E1.1 via Design Principle 6, so no two version-bumping
tasks fall in the same wave. E1.2 touches neither file and runs start-to-finish in
parallel. Kickoff's map holds as written.

## Stale issue cleanup

Closed #32, #33, #35, #36, #38, #39, #40 as superseded. Each referenced an LLD
file that no longer exists, used retired epic/story numbering, and — for the three
extension tasks — mandated vitest, which Story 2.2 AC1 replaces with
`@vscode/test-electron` + Mocha. Rewriting seven bodies whose every reference had
changed was more error-prone than regenerating them.

## Deviation from the skill

`/lld`'s own Step 2 diagram-generation rules still instruct emitting `edf://`
links and sequence-diagram `link` directives — the very defects E1.3 exists to
fix. They were not followed; ADR-0039 as revised was followed instead. This is a
transitional inconsistency that closes when #52 merges.

## Verification

Every LLD was run through the harness before commit:

| LLD | Diagrams | Link targets | Anchors |
|---|---|---|---|
| E1.1 | 8/8 parse | 16 resolve | 3/3 match |
| E1.2 | 7/7 parse | 13 resolve | 4 defined, 3 referenced |
| E1.3 | 5/5 parse | 11 resolve | 2/2 match |

Cross-manifest coverage audit: 10/10 REQ anchors covered, 0 orphaned, with
Stories 1.1–1.4 correctly double-owned by E1.1 and E1.3 per the plan's closure
seam.

## Open items for the human

1. **ADR-0039 revision approach** — dated revision in place vs. a superseding
   ADR-0040. Carried by #45.
2. **Story 1.4 AC7 amendment** — the requirement contradicts D1; amending an
   approved requirement post-Gate-2 needs sign-off. Also #45.
3. **GitHub and VSCode click-through remain unmeasured.** The harness settles
   parse, sanitiser and resolution; whether either renderer actually *navigates*
   needs a human with a browser and an editor. That is #47's remaining job, and
   it is the last place this design is still taking something on trust.

## Commits

- `9687f44` docs: LLD for #28 — E1.1 LLD template & diagram vocabulary
- `f7285a4` docs: LLD for #30 — E1.2 VSCode extension review feedback
- `89ec1c7` docs: LLD for #31 — E1.3 skill instructions & quality gates
- `994a0be` docs: backfill task issue numbers into v1 coverage manifests
