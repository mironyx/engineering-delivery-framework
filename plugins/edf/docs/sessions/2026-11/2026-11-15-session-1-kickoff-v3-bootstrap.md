# Session — 2026-11-15 — kickoff v3 bootstrap

**Session tag:** KICK-ojixe · **Skill:** `/kickoff` (delta mode) · **Branch:** `docs/v3-kickoff`

## Summary

Resumed the v3 (Jira issue tracker) kickoff from Gate 1. A prior session (14 Nov) had drafted
the delta HLD and applied the `edf:hld-review` fixes. This session tidied the HLD, ran three
drift scans, added a `close` tracker operation to keep GitHub `status` byte-identical, accepted
ADR-0041 (tracker abstraction), added a Jira revision to ADR-0018, wrote a 4-epic plan and
created epics #114–#117. No production code was written.

## Shipped

| Commit | Scope |
|---|---|
| ad0ca8b, 7f052a8 | HLD v0.1–0.2 (prior session) |
| 22c6809 | HLD 0.3: Flow 5 moved into Level 3, diagram edge removed, bullets tightened |
| 0d1dfda | HLD 0.4: Gate 1 fixes (`close` op, `starters/` scope, GitHub epic model); requirements change log reordered |
| 7a3beb6 | HLD: idempotent `close` in today's step order |
| 0678920, 81638db | ADR-0041 tracker abstraction, Accepted |
| bb4f394 | ADR-0018 revision: epic model on Jira |
| e8fe6d1, bdafabf | v3 implementation plan + Gate 2 fixes |

## Board state

| Issue | Epic | Depends on |
|---|---|---|
| #114 | E3.1 Tracker script and GitHub backend | — |
| #115 | E3.2 Jira backend and Markdown↔ADF converter | #114 (converter can start early) |
| #116 | E3.3 Pipeline on the tracker script | #114 to start, #115 to close |
| #117 | E3.4 Tracker onboarding | — |

New label `version:v3`. No `area:` labels exist in the repo, so none were applied.

## Cross-cutting decisions

- **ADR-0041:** a single standard-library Python tracker script with GitHub and Jira backends
  is the only route to issue data. A guard test covers `skills/`, `agents/`, `bin/` and
  `starters/`. The `gh-*.sh` scripts stay as shims until migration completes.
- **The respx exception:** Jira backend tests use a local `http.server` fake, because
  standard-library-only rules out `httpx`. This must be recorded in `CLAUDE.md` when E3.2 lands.
- **`status` versus `close`:** `status` changes board state only. `close` is the merge-time
  closure (GitHub: board → epic tick → `gh issue close`, idempotent, always exits 0; Jira:
  → Done).
- **ADR-0018 revision:** on Jira, epics are native Epics, tasks link through `parent`,
  progress comes from child statuses, and the epic body has no task checklist.

## Drift-scan verdicts

| Scan | Result |
|---|---|
| Gate 1, first run | 2 block (parent-not-found error form; GitHub `status done` closing issues), 5 warn, 7 info. All fixed |
| Gate 1, re-scan | 0 block, 1 new warn (`close` failure tolerance). Fixed |
| Gate 2 (plan) | 0 block, 4 warn (E3.3 depends on E3.2 to close; tracker-neutral AC split; redaction ownership; parity tests before shim removal), 6 info. All fixed |

## What didn't go to plan

- The kickoff argument path was misspelt (`requiremetns`). It resolved to the real file
  without asking.
- The HLD came in about 420 lines against the 300-line delta target. The gate fixes added
  rather than removed lines.
- The first drift scan caught the HLD silently changing GitHub behaviour: C3.2 folded
  `gh issue close` into `status done`. `hld-review` had passed it.
- Commits failed because the machine has no git identity. Per-command `-c user.*` was used,
  matching the existing author.

## Process notes for `/retro`

- **Byte-identical parity is hard to check.** "Absorb existing behaviour" claims need a check
  against the actual script source. Neither `hld-review` nor the HLD draft did this; the drift
  agent caught it by reading `feature-end/SKILL.md`.
- **CLAUDE.md conflicts surface late.** The CLAUDE.md "respx" rule conflicts with the plugin's
  no-install constraint, and that only came up at ADR time. Worth a kb/ note on plugin
  runtime constraints.
- **The epic-issue template assumes GitHub.** The kickoff Step 8 template's `## Tasks`
  checklist doesn't apply on Jira. Kickoff and architect migration in E3.3 must handle it.

## Skill self-reflection

- **Worked:** gating, plus resuming the drift agent through SendMessage for the re-scans. It
  kept context and cut repeated file reads.
- **Struggled:** Step 1.5 says "ask if rewrite, otherwise abort" but has no "resume at a
  gate" path, which is the common case after an interrupted session.
- **Suggestion:** add a resume row to the bootstrap-modes table. When the HLD exists and its
  status is "awaiting Gate N", resume at that gate, and the orientation summary lists which
  steps have commits.

## Next step

`/architect #114` (E3.1). The E3.2 converter task and E3.4 (#117) can be designed in parallel.
Before the E3.2 smoke run, add a Blocked status to the `SCRUM` workflow.
