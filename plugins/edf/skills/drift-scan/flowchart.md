# /drift-scan — Process flowchart

Visual overview of the drift detection pipeline. Gathers artefacts across the full delivery stack, analyses drift at two levels, classifies findings, and produces a coverage matrix.

```mermaid
flowchart TD
    START(["fa:fa-play /drift-scan invoked"]) --> S1

    S1["S1: Gather artefacts<br/>Requirements, design docs,<br/>ADRs, plans, source files"] --> S2

    S2["S2: Analyse drift<br/>Requirements ↔ Design<br/>Design ↔ Code"] --> S2_CLASSIFY

    subgraph ANALYSIS["Drift Analysis"]
        S2_CLASSIFY{"Classify each<br/>finding"}
        S2_CLASSIFY -->|"Runtime bug risk"| S2_CRITICAL["Critical"]
        S2_CLASSIFY -->|"Bug/data loss risk"| S2_WARNING["Warning"]
        S2_CLASSIFY -->|"Cosmetic/future"| S2_INFO["Info"]
    end

    S2_CRITICAL --> S3
    S2_WARNING --> S3
    S2_INFO --> S3

    S3["S3: Produce coverage matrix<br/>Epic → design coverage →<br/>ADR coverage → code status → drift"]

    S3 --> S4["S4: Save report<br/>docs/reports/drift/<br/>YYYY-MM-DD-drift-report.md"]

    S4 --> S5["S5: Summarise<br/>Critical/Warning/Info counts,<br/>top 3 findings, report path"]

    S5 --> DONE(["fa:fa-check Drift scan complete"])

    %% ── Styles ──
    classDef startend fill:#d4f0d4,stroke:#2d7d2d,color:#1a3a1a
    classDef process fill:#d6e8f7,stroke:#2d5f8a,color:#1a2f44
    classDef decision fill:#f7eed6,stroke:#8a6d2d,color:#443a1a

    class START,DONE startend
    class S1,S2,S2_CRITICAL,S2_WARNING,S2_INFO,S3,S4,S5 process
    class S2_CLASSIFY decision
```
