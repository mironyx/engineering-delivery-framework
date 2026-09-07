# Session log — EDF-81

## Approach rationale
- **Issue:** #81
- **Approach chosen:** Replace direct `WebFetch`/`WebSearch` in feature-core Step 3a with a delegated general-purpose sub-agent. The sub-agent fetches external-surface docs and returns a compact 20-30 line summary (signatures, wire shapes, gotchas), keeping 10-50k token raw pages out of the main session context.
- **LLD deviations:** none (no LLD for this issue)
- **Pressure:** Light — ~33 lines added to SKILL.md (1 source file, no test files)

## Work completed
- Modified `plugins/edf/skills/feature-core/SKILL.md` Step 3a: replaced direct `WebFetch`/`WebSearch` instructions with a sub-agent spawn block including a `Return contract` capping output at 20-30 lines
- Updated `plugins/edf/skills/feature-core/flowchart.md`: changed `S3A_FETCH` from a process node to an agent node (purple), moved to the `agent` CSS class
- PR: https://github.com/mironyx/engineering-delivery-framework/pull/89
- Files changed: SKILL.md (+30/-5), flowchart.md (+3/-3), plugin.json (+1/-1), marketplace.json (+1/-1)

## Decisions made
- The existing decision table (mandatory/optional/skip fetch) is unchanged — only *how* the fetch result reaches the main context differs
- Used `general-purpose` sub-agent type (not a named agent) since the research is lightweight and one-shot
- Return contract capped at 20-30 lines, matching the discipline from `feature-evaluator.md`'s `Return contract` section
- Preserved doc URL and confirmed version in the summary for citation in `## Design deviations` / session log

## Review feedback addressed
- No review feedback received (self-merged)

## LLD Sync report
Skipped — no LLD covers this issue.

## Cost retrospective
- Cost data unavailable (Prometheus not configured)
- This was a Light-track change: single file edit, no sub-agents spawned during implementation, no test cycles
- The net effect of this change should reduce future feature-core token costs by ~10-50k tokens per unresearched external surface

## Cost checkpoints
| Step | Timestamp | Cost (cumulative) | Tokens (cumulative) | Note |
|------|-----------|--------------------|----------------------|------|

## Concerns & Deferred Items

## Next steps
- Verify manually: trigger a Step 3a fetch against a real external surface and confirm the main context only receives the compact summary