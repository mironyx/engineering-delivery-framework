# /pr-review — Process flowchart

Visual overview of the adaptive code review pipeline. Cost-adaptive: diff size sets the number of quality agents (1 for small diffs, 2 for large); `PATTERNS_NEEDED` independently adds Agent B on either path when the diff makes first contact with an external surface. Agent spawns are purple, decisions are orange.

```mermaid
flowchart TD
    START(["fa:fa-play /pr-review invoked"]) --> S1

    S1["S1: Gather context<br/>Diff, changed files, CLAUDE.md,<br/>kb/architecture.md,<br/>kb/anti-patterns.md, manifest"] --> S1_CHK{"Diff empty?"}
    S1_CHK -->|"Yes"| STOP_EMPTY(["fa:fa-ban Nothing to review"])
    S1_CHK -->|"No"| S2

    S2["S2: Classify<br/>DIFF_LINE_COUNT, CHANGED_FILES,<br/>EXTERNAL_SURFACES, NEW_SURFACES,<br/>PATTERNS_NEEDED"] --> S2_SIZE{"Diff size?"}

    S2_SIZE -->|"< 150 lines"| S3_SINGLE
    S2_SIZE -->|">= 150 lines"| S3_MULTI

    S3_SINGLE(("Agent Q: Quality<br/>All checks in one pass<br/>Bugs, justification, design,<br/>compliance, anti-patterns,<br/>design conformance, helper reuse"))

    S3_SINGLE --> S3_PAT

    subgraph PARALLEL["Parallel Agents (>= 150 lines)"]
        S3A(("Agent A: Code Quality<br/>Bugs, justification,<br/>design principles,<br/>CLAUDE.md compliance,<br/>anti-patterns"))
        S3C(("Agent C: Design Conformance<br/>LLD matching, silent swallow,<br/>diagnostics, helper reuse,<br/>DB efficiency"))
    end

    S3_MULTI --> S3A
    S3_MULTI --> S3C

    S3A --> S3_PAT{"PATTERNS_NEEDED?<br/>New external surface, or<br/>manifest/env/config changed"}
    S3C --> S3_PAT
    S3_PAT -->|"Yes"| S3B(("Agent B: Surface currency<br/>WebFetch pinned spec for new<br/>surfaces, best-practice search,<br/>version-mismatch check"))
    S3_PAT -->|"No"| S4
    S3B --> S4

    S4["S4: Consolidate and output<br/>Merge JSON arrays, deduplicate,<br/>sort by severity: blocks first"] --> S4_FIND{"Findings?"}
    S4_FIND -->|"No"| S4_CLEAN["No issues found"]
    S4_FIND -->|"Yes"| S4_REPORT["Report: Blockers + Warnings<br/>PR mode: post as comment"]

    S4_CLEAN --> S5
    S4_REPORT --> S5

    S5["S5: Cost<br/>query-feature-cost.py<br/>Terminal only, best-effort"]

    S5 --> DONE(["fa:fa-check Review complete"])

    %% ── Styles ──
    classDef startend fill:#d4f0d4,stroke:#2d7d2d,color:#1a3a1a
    classDef process fill:#d6e8f7,stroke:#2d5f8a,color:#1a2f44
    classDef agent fill:#e8d6f7,stroke:#6b2d8a,color:#2d1a3a
    classDef decision fill:#f7eed6,stroke:#8a6d2d,color:#443a1a
    classDef stop fill:#f7d6d6,stroke:#8a2d2d,color:#441a1a

    class START,DONE startend
    class S1,S2,S4_CLEAN,S4_REPORT,S5 process
    class S3_SINGLE,S3A,S3C,S3B agent
    class S1_CHK,S2_SIZE,S3_PAT,S4_FIND decision
    class STOP_EMPTY stop
```
