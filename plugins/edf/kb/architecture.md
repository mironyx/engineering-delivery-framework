# Architecture

Project-specific architecture rules and patterns. Referenced by EDF skills via concept name, not path.

## Boundary rule

<!-- e.g. "`src/lib/engine/` must have zero imports from Next.js, Supabase, or any framework" -->

## API composition pattern

<!-- e.g. "Every route uses `createApiContext` + `ApiContext` injection; controller/service split" -->

## DB contract

<!-- e.g. "Types referencing DB columns must match `src/types/database.types.ts` exactly — no `as unknown as` casts" -->

## Issue tracker access

All issue operations go through `bin/tracker.py` (ADR-0041). Only `bin/_tracker_github.py`
may call `gh issue`, `gh project` or `gh api …/issues`; only `tracker.py` reads `JIRA_*`.
Environment values come from `_edf_env.resolve` (OS env, then `.env`; empty means unset).
Backends raise `_tracker_contract.TrackerError`; tests drive `gh` through the `fake_gh`
fixture, never by patching `subprocess`.
Among the tracker modules only `bin/_jira_client.py` may import `urllib` or `http.client`, and
only `bin/_tracker_jira.py` may call it. Bodies and comments pass through `bin/_adf.py` (`md_to_adf`, `adf_to_md`); no other
code builds ADF. Jira tests use the `fake_jira` fixture (local HTTPS server), not patching.
