# Drift Report: Requirements ↔ Design ↔ Code

**Scan date:** 2026-11-16
**Project phase:** v3 (Jira issue tracker) — E3.1 shipped; E3.2–E3.4 not started. Scope: v3 artefacts and the tracker code (`plugins/edf/bin/tracker.py`, `_tracker_contract.py`, `_tracker_github.py`). Docs live under `plugins/edf/docs`, not `docs/`.

## Summary

| Severity | Count |
|----------|-------|
| Critical | 0 |
| Warning  | 1 |
| Info     | 3 |

**Overall drift score:** Low. E3.1 code, LLD (v0.5), coverage manifest and plugin versions agree; one stale TODO reference.

## Critical Issues

None.

## Warnings

- **Stale TODO ref** — `plugins/edf/bin/_tracker_github.py:530` carries `TODO(#121)` (epic-read cause dropped to keep the old message byte-identical), but #121 is closed. The TODO is now owned by nobody. Re-point it at E3.3 (#116), where the shim is dropped.

## Informational

- **Manifest statuses** — `REQ-tracker-script-select-tracker-from-environment` is `Approved` though its GitHub half merged in #118; the other five are `Revised`. All stay below `Implemented` until E3.2's Jira half merges (per manifest comments); expected.
- **Exit criteria** — #114's three exit-criteria boxes are unticked although all tasks merged (see the retro, action 5).
- **Manifest scope** — the manifest covers 6 of 9 v3 `REQ-` anchors; the other 3 belong to E3.2–E3.4 (future phase).

## Coverage Matrix

| Epic | Stories | Designed | ADR'd | Code implemented | Coverage |
|------|---------|----------|-------|------------------|----------|
| E3.1 Tracker script and GitHub backend (#114) | 1.1–1.5, 2.1 AC4 | LLD v3-e3-1 v0.5 | ADR-0041, ADR-0018 rev | GitHub half, all 8 ops | Aligned |
| E3.2 Jira backend + converter (#115) | 1.x Jira half | Not yet (architect pending) | ADR-0041 | None | Future phase |
| E3.3 Pipeline on tracker script (#116) | 2.x | Not yet | ADR-0041 | None | Future phase |
| E3.4 Tracker onboarding (#117) | 3.x | Not yet | ADR-0041 | None | Future phase |
