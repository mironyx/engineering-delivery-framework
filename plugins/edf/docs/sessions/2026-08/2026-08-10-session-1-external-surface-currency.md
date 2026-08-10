# Session Log — External Surface Currency

## Summary

Diagnosed and fixed a recurring framework failure: implementation agents writing
code against an external specification from training recall rather than the
current spec, with the review agent that exists to catch this never firing.
Triggered by a real incident — new development against the MCP protocol used a
stale shape and survived an explicit in-session correction until the human
pushed back.

Root cause was not a single bug but a gate on the wrong axis, plus a
design-time rule with no downstream consumer. Fixed across `/lld`,
`/feature-core`, `/pr-review`, and `edf:lld-review`. PR #44, no linked issue —
framework maintenance raised directly from the incident.

## Approach rationale

Two candidate triggers for "research this surface":

1. **Any changed file imports a direct dependency.** Rejected. It would have
   missed the incident entirely — a protocol spec revision is not a package
   version and may have no manifest entry at all — while firing on nearly every
   PR, which is the cost the existing gate was added to avoid.
2. **First use of an external surface anywhere in the repo.** Chosen. Modifying
   code that already uses a surface has in-repo precedent to imitate, so recall
   is anchored and research is largely wasted spend. First use has no precedent,
   so the code comes entirely from recall. Cost falls to once per surface per
   repo rather than once per PR.

The deeper change is making the pinned version an artefact rather than a
conversational instruction. The LLD template already carried a "pin the version"
rule, but as prose in a Backend-layer blockquote that nothing downstream read. A
version stated in chat has no anchor either — which is why the incident survived
an explicit comment.

## Work completed

PR: https://github.com/mironyx/engineering-delivery-framework/pull/44

| Commit | Scope |
|--------|-------|
| `39fbd75` | First-use gate, External Surfaces table, feature-core Step 3a |
| `4cfa169` | Prose tightened, `PATTERNS_NEEDED` renamed to `SURFACE_RESEARCH` |

| File | Change |
|------|--------|
| `skills/lld/template.md` | New first-class `## External Surfaces` table opening Part B — surface, version/revision, doc URL, verified, `New to repo`. Inline pin rule now points at it. |
| `skills/lld/SKILL.md` | Self-critique items for table completeness and grep-determined `New to repo`; existing "verified against docs" bullet de-duplicated against the table. |
| `skills/feature-core/SKILL.md` | New Step 3a — pinned version is binding, `WebFetch` for new/unverified rows, no research for established surfaces. `WebFetch`/`WebSearch` added to `allowed-tools`. |
| `skills/pr-review/SKILL.md` | `EXTERNAL_SURFACES` + `NEW_SURFACES` replace `FRAMEWORK_DEPS`; `SURFACE_RESEARCH` gate; Agent B runs on either size path, gains `WebFetch`, reports `version-mismatch` as a blocker. |
| `agents/lld-review.md` | Verifies the table exists, is complete including manifest-less surfaces, and that `New to repo` was grep-determined. |
| both flowcharts | Step 3a; Agent B trigger decoupled from diff size. |
| manifests | 0.10.28 → 0.10.29 |

## Decisions made

- **Four defects, one symptom.** (1) `PATTERNS_NEEDED` required the diff to touch
  the manifest, `.env`, a framework config, or a file importing a package named
  in `{{ANTI_PATTERNS}}` — a from-scratch integration touches none of those.
  (2) Agent B was defined only under the ≥150-line path; below it, Agent Q
  covered "framework anti-patterns" with no `WebSearch` tool. (3) Agent B
  substituted `{{FRAMEWORK_DEPS_WITH_VERSIONS}}`, never defined anywhere.
  (4) Nothing downstream read the LLD's pins or `Unverified — recall-based`
  markers.
- **`PATTERNS_NEEDED` renamed to `SURFACE_RESEARCH`.** It is a prompt-local
  variable the skill computes at run time — nothing stores it, which made it
  ungreppable and confusing when read as a repo artefact. The old name also
  described the retired file-pattern gate.
- **Unit is "external surface", not "framework dependency".** Anything whose
  contract is defined outside the repo, explicitly including protocol and
  wire-format specs with no manifest presence. Without this the fix would still
  have missed the triggering incident.
- **Version-mismatch is block severity.** A diff implementing a different
  revision than the one pinned is the exact failure mode, not a warning.
- **Test agents left alone.** `test-author` and `feature-evaluator` still have no
  web tools. `feature-core` is the implementing agent and is where the contract
  now binds; extending it to the test agents is a separate decision.

## Review feedback addressed

Human review during the session, no automated `/pr-review` pass (the skill under
change was the reviewer):

- **Prose too verbose; waste should be removed alongside additions.** Second
  commit is net −113/+79 against the first. Cut the Step 3a intro and
  cost-rationale paragraphs, condensed the template's column rules and rationale,
  and removed a pre-existing paragraph in Agent B that restated the four bullets
  directly above it. Balance was explicitly requested — mechanisms kept intact.
- **"What is `PATTERNS_NEEDED`, I cannot find it in any repo?"** Answered and
  acted on via the rename above.
- Follow-up from the same pass: the skill's frontmatter description and
  cost-adaptive summary still described the retired gate; corrected, and
  `WebFetch` added to `allowed-tools`.

## LLD Sync report

Skipped — no LLD covers this change. Framework maintenance raised directly from
an incident rather than through `/kickoff` → `/architect`.

## Cost retrospective

No cost data. No linked issue, so no feature ID was registered and
`query-feature-cost.py` has nothing to aggregate; the session was never tagged
via `tag-session.py`. Session ran outside the `/feature` pipeline — diagnosis and
framework edits driven conversationally.

Qualitative drivers:

- **Diagnosis dominated.** Reading the four skills end to end to establish the
  gate was skipped, not merely wrong, was the bulk of the work. Cheap relative to
  the recurring rework it prevents.
- **One wrong first proposal.** The initial gate keyed off dependency imports and
  would have missed the incident. Caught only when the human supplied the
  concrete failure (MCP spec, no manifest entry). Cost: one revision round.
  Lesson — get the triggering incident's specifics *before* proposing the fix,
  not after.
- **Two commits where one was possible.** Verbosity in the first commit needed a
  tightening pass. The "remove waste while adding lines" rule applies during
  authoring, not as a follow-up.

## Next steps

- **`kb/` is missing entirely** despite `CLAUDE.md` documenting
  `kb/architecture.md`, `kb/anti-patterns.md`, `kb/conventions.md`, and
  `kb/file-map.md`. `{{ANTI_PATTERNS}}` and `{{ARCHITECTURE_RULES}}` are
  therefore empty on every `/pr-review` run in this repo, so the free static
  anti-pattern check and Agent Q's design-principle checks do nothing here.
  Worth an issue.
- **Validate the new gate on the next from-scratch integration.** The mechanism
  is untested against a live case — watch whether the LLD's External Surfaces
  table actually gets populated with manifest-less surfaces, since that is the
  step most likely to be skipped in practice.
- Consider whether `test-author` needs doc access when tests encode a protocol
  shape.
