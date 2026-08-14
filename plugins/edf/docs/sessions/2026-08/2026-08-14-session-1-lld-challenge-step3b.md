# Session Log — LLD Challenge at feature-core Step 3b

## Summary

Fixed a framework instruction that was correct in intent but inert in practice.
`/feature-core` Step 3b already told the implementing agent to "critically
evaluate the LLD — do not follow it blindly", yet in practice the agent almost
always transcribed the LLD as written. Suboptimal design choices were caught
during human review instead, costing rework on every feature.

Replaced the prose with three questions that must be answered **in writing** —
including when the answer is "no change needed" — plus one rule bounding what
the agent may change unilaterally. PR #55, no linked issue — framework
maintenance raised directly from the user's observation.

## Approach rationale

The instruction was not wrong; it produced no artefact. Two structural causes:

1. **No output on the keep branch.** Step 3b defined an output shape only for
   the *deviate* path — state what the LLD said, state what you're doing
   instead, note it in the PR. An agent that follows the LLD writes nothing, so
   the critique could be passed by thinking nothing. It was the only step in the
   pipeline with no written output; every neighbour (3b's approach list, 3c's
   pressure statement, 3dF's session log) forces text.
2. **Asymmetric cost.** Following costs zero. Deviating costs a justification, a
   PR `## Design deviations` section, and downstream `/lld-sync` reconciliation.
   A cost-minimising agent follows every time.

The fix is symmetry: make writing "keep" cost the same as writing "improve".
That is the whole mechanism. Everything else considered was scaffolding.

**On the definition of "simpler".** The user's motivating case was an LLD
specifying two `DELETE` statements where one would do. That case is the reason
the naive version of this fix would not have worked: two `DELETE`s are not
broken. They are explicit and readable, so an agent asking "is there a simpler
way?" answers "no" in good faith and the issue still reaches human review.
Question 2 therefore defines "simpler" as **fewer of something you can count** —
statements, round trips, branches, files, concepts, moving parts — with the rule
*"if you cannot name what got smaller, it is not simpler."* That converts a
taste judgement into a counting exercise. Two `DELETE`s versus one is fewer
statements and fewer round trips: countable, nameable, hard to hand-wave.

## Work completed

PR: https://github.com/mironyx/engineering-delivery-framework/pull/55

| Commit | Scope |
|--------|-------|
| `3255745` | Step 3b rewrite, flowchart, version bump |

| File | Change |
|------|--------|
| `skills/feature-core/SKILL.md` | Step 3b prose critique replaced with three mandatory written questions and a two-branch action rule. Heading renamed to "Pick the simplest approach and challenge the LLD". |
| `skills/feature-core/flowchart.md` | New `S3b: Answer 3 LLD challenge questions` process node; the decision now has three branches — keep / build your version / stop-and-ask — with a red `Stop: ask user` terminal wired into the existing style classes. |
| manifests | 0.10.29 → 0.10.30 |

The two-branch rule is what stops the agent throwing the design away:

- **AC and public contract unchanged** → build your version, note it in the PR
  under `## Design deviations` for `/lld-sync`.
- **AC, public contract, schema, or another task's files change** → stop and ask
  the user.

Free hand on internals; never a silent redesign of anything visible from
outside.

## Decisions made

- **Kept `## Design deviations` as the single channel.** An earlier draft added
  a `[refinement]` / `[contract]` tag so `/lld-sync` could reconcile a rename
  cheaply. Dropped — fragmenting the traceability channel to save `/lld-sync` a
  little work is a bad trade, and the tagging was unproven.
- **Rejected a six-probe critique table.** The first proposal enumerated
  reinvention, decomposition, contract fit, pattern currency, simpler primitive,
  and testability as separate rows with per-row verdicts. It had the same
  weakness as the naive Q2 — probe rows invite "Keep" answers — while costing
  far more prose. Three questions carry the same forcing function.
- **Rejected a second re-check at Step 4cF.** Step 3b runs at the point of
  *minimum* information about the LLD's fit: before tests exist, before a line
  is written. A post-test re-check would catch what 3b cannot. Dropped as
  disproportionate for a first attempt; it is the obvious next lever if the
  written-answer version underperforms.
- **Rejected a reduced Light-track variant.** A sub-30-line fix rarely has LLD
  structure worth challenging, but carving out an exception costs more words
  than letting the three questions answer themselves trivially.
- **Left MD013 line-length alone.** Lint flags line-length across both changed
  files, but every added line is under 80 columns — the hits are pre-existing
  lines and mermaid node definitions matching surrounding style. Reformatting
  untouched lines would bury the change.

## Review feedback addressed

No `/pr-review` run — docs-only change to skill instructions, no code paths
touched. The substantive review happened conversationally *before* implementation:

- **"I do not fully understand the proposals — this is a bit confusing and
  complicated."** The six-probe table, the tagging scheme, the Step 4cF
  re-check, and the Light-track variant were all cut in response. What shipped
  is roughly a quarter the size of the first proposal and strictly more likely
  to be followed.
- **"Imagine the case sql function — currently it does 2 deletes instead of
  one… will it be covered?"** Correctly identified that the simplified version
  would probably *not* fire on that case. Produced the countable-simpler
  definition, which is the part of this change most likely to do real work.

## LLD Sync report

Skipped — no LLD covers this change. Framework maintenance raised directly from
the user's observation rather than through `/kickoff` → `/architect`.
`lld-sync/SKILL.md:47` still references `feature-core` Step 3b for deviation
notes and remains accurate; no downstream edit needed.

## Cost retrospective

No cost data. No linked issue, so no feature ID was registered and
`query-feature-cost.py` has nothing to aggregate; the session was never tagged
via `tag-session.py`. There is no `.env` in this repo, so `EDF_FEATURE_PREFIX`
is unset and session logs here carry no feature-ID suffix. Session ran outside
the `/feature` pipeline — driven conversationally from `/architect`.

Qualitative drivers:

- **Two rounds of over-engineering before the useful answer.** The first
  proposal was a six-probe table with a tagging scheme, a second checkpoint, and
  a track-specific variant. The user rejected it as confusing; the second was
  accepted. Roughly half the session's output was written and then discarded.
- **The concrete failing case arrived third, and changed the design.** The
  two-`DELETE` example came only after the simplified proposal was already
  agreed, and immediately exposed that Q2 would return "no change" on exactly
  the case it existed to catch. **This is the same lesson the 2026-08-10 session
  log already recorded** — *"get the triggering incident's specifics before
  proposing the fix, not after"* — and it was not applied. The lesson is written
  down and still not operational. Worth treating as a process gap rather than a
  repeated individual slip.
- **Cheap mechanically.** Two files, ~20 net lines, one commit. Diagnosis and
  three rounds of design were the entire cost.

## Next steps

- **The mechanism is unvalidated.** No feature has yet run against the new
  Step 3b. Watch the next `/feature` on an LLD with a known soft spot: does the
  agent write three real answers, and does Q2's counting rule actually surface
  anything? If it still sails through, the next lever is making the questions
  produce a *checkable* answer (an artefact a later step verifies) rather than
  merely a written one.
- **Counting cuts both ways.** Q2 can now be used to argue *for* merging things
  that were deliberately separate. The AC-and-contract rule bounds the damage,
  but watch for an agent collapsing a structure that had a reason.
- **`kb/` is still missing entirely** despite `CLAUDE.md` documenting
  `kb/architecture.md`, `kb/anti-patterns.md`, `kb/conventions.md`, and
  `kb/file-map.md`. Carried forward unactioned from the 2026-08-10 session log.
  Still worth an issue.
- **VS Code flags two false-positive broken anchors** in
  `feature-core/SKILL.md` (lines 553 and 614, `#managing-technical-debt`). The
  anchor resolves correctly to the `## Managing technical debt` heading at line
  31 — the extension is resolving same-file anchors as file paths. Pre-existing,
  not worth changing the links to satisfy a linter bug.
