# Session log — EDF-47

## Approach rationale

- **Issue:** #47 — v1-e1-1: renderer conformance fixture, harness and committed report
- **Approach chosen:** Productionise the LLD §B.1.3 prototype as a Node ESM harness
  (`tests/conformance/check-diagrams.mjs`) that parses **and renders** every fenced mermaid
  block under jsdom with `securityLevel: 'strict'`, pinned to `mermaid@11.12.2`. Author the
  fixture LLD exercising one diagram per type, both link forms, the two negative cases and a
  nested-depth (`../../../`) link, then record the measured results in a committed report.
- **LLD deviations:** one render pass per block serves both the D5 anchor check and the D6
  `classDef` check, rather than a separate render per check. Negative-case fixtures live in
  `tests/conformance/fixtures/` so the main fixture stays green. Harness gains `--design-root`
  and `--json` flags (additive).
- **Pressure:** heavy — ~350 src lines across 2 source files (harness + package manifest),
  plus fixture/report docs and pytest coverage.
- **Constraint honoured:** read-only on `plugins/edf/skills/lld/template.md`. Any defect the
  harness finds there is recorded in the report and raised as a follow-up issue, not fixed here.

## Cost checkpoints

| Step | Timestamp | Cost (cumulative) | Tokens (cumulative) | Note |
|------|-----------|--------------------|----------------------|------|
| 3c | 2026-08-15T17:44:12Z | $0.00 | 0 in / 0 out | pressure: heavy — ~350 src lines, 2 source files (harness + manifest); docs + verification tooling |
