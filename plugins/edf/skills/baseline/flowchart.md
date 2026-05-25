# /baseline — Process flowchart

Visual overview of the requirements reconciliation pipeline. Gathers data across the full stack, reconciles code vs docs at AC level, identifies emergent features, and produces a coverage matrix. Propose-only — never mutates state.

```mermaid
flowchart TD
    START(["fa:fa-play /baseline invoked"]) --> S0

    S0["S0: Parse arguments<br/>All versions or scoped<br/>to a single version"]

    S0 --> S1

    subgraph GATHER["1. Gather Data"]
        S1_REQS["Read ALL requirements<br/>Current + future versions"]
        S1_DESIGN["Read design docs<br/>LLDs, HLDs, ADRs, plans"]
        S1_CODE["Survey source tree<br/>src/, engine, API, types,<br/>schema/migrations"]
        S1_TESTS["Scan tests as<br/>coverage indicators"]
        S1_ISSUES["Closed issues + git history<br/>Coverage manifests"]
    end

    S1 --> S1_REQS
    S1_REQS --> S1_DESIGN
    S1_DESIGN --> S1_CODE
    S1_CODE --> S1_TESTS
    S1_TESTS --> S1_ISSUES

    S1_ISSUES --> S2

    subgraph RECONCILE["2. Reconcile: Code vs Docs"]
        S2_CLASSIFY{"Per story:"}
        S2_CLASSIFY -->|"Code + tests match spec"| S2_DELIVERED["Delivered"]
        S2_CLASSIFY -->|"Some ACs met, others not"| S2_PARTIAL["Partial"]
        S2_CLASSIFY -->|"Code exists, behaviour differs"| S2_DIVERGENT["Divergent"]
        S2_CLASSIFY -->|"No code exists"| S2_NOT_STARTED["Not started"]
        S2_CLASSIFY -->|"Explicitly removed"| S2_DESCOPED["Descoped"]
    end

    S2 --> S2_CLASSIFY

    S2_DELIVERED --> S3
    S2_PARTIAL --> S3
    S2_DIVERGENT --> S3
    S2_NOT_STARTED --> S3
    S2_DESCOPED --> S3

    S3["3. Identify emergent features<br/>Infrastructure, organic additions,<br/>orphaned code"]

    S3 --> S4["4. Produce coverage matrix<br/>Epic → source file → stories<br/>→ delivered/partial/divergent/<br/>not started/descoped → coverage %"]

    S4 --> S5["5. Write report<br/>docs/reports/baseline/<br/>YYYY-MM-DD-baseline.md"]

    S5 --> S6["6. Summarise<br/>Coverage matrix, counts,<br/>top 3 divergences,<br/>emergent features, report path"]

    S6 --> DONE(["fa:fa-check Baseline complete"])

    %% ── Styles ──
    classDef startend fill:#d4f0d4,stroke:#2d7d2d,color:#1a3a1a
    classDef process fill:#d6e8f7,stroke:#2d5f8a,color:#1a2f44
    classDef decision fill:#f7eed6,stroke:#8a6d2d,color:#443a1a

    class START,DONE startend
    class S0,S1_REQS,S1_DESIGN,S1_CODE,S1_TESTS,S1_ISSUES,S2_DELIVERED,S2_PARTIAL,S2_DIVERGENT,S2_NOT_STARTED,S2_DESCOPED,S3,S4,S5,S6 process
    class S2_CLASSIFY decision
```
