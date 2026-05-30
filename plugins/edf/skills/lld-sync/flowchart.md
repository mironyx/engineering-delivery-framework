# /lld-sync — Process flowchart

Visual overview of the post-implementation LLD feedback loop. Detects mode (refactor vs feature), gathers context, analyses the delta, updates the LLD/kb/manifest, and produces a sync report. Decisions are orange.

```mermaid
flowchart TD
    START(["fa:fa-play /lld-sync invoked"]) --> MODE

    MODE{"Mode detection"} -->|"refactor label<br/>or Trigger section"| REFACTOR["Refactor mode<br/>Directive: apply sweep<br/>targets from issue body"]
    MODE -->|"otherwise"| FEATURE["Feature mode<br/>Reactive: analyse what<br/>was built vs spec"]

    REFACTOR --> S1
    FEATURE --> S1

    S1["S1: Gather context<br/>Issue body, PR body + comments,<br/>LLD file, git diff changed files, tests"]

    S1 --> S2

    S2{"S2: Mode?"} -->|"refactor"| S2_REF["Verify: additions match spec,<br/>files were edited, sweeps applied"]
    S2 -->|"feature"| S2_FEAT["Analyse delta:<br/>Additions / Corrections /<br/>Omissions / Confirmations"]

    S2_REF --> S3
    S2_FEAT --> S3

    S3["S3: Update the LLD<br/>Surgical edits, implementation<br/>notes for Corrections,<br/>preserve stable anchors"]

    S3 --> S3A["S3a: Update knowledge base<br/>New helpers → kb/architecture.md<br/>Re-implementations → kb/anti-patterns.md"]

    S3A --> S3B["S3b: Update coverage manifest<br/>Corrections → flip to Revised<br/>Additions → new manifest entry<br/>Bump Document Control version"]

    S3B --> S3C["S3c: Remove shipped Rev X blocks<br/>Promote new stories to permanent,<br/>delete empty Pending changes sections"]

    S3C --> S3D_CHECK{"Refactor epic<br/>fully closed?"}
    S3D_CHECK -->|"Yes"| S3D["S3d: Refactor LLD lifecycle<br/>Retire / Promote to ADR /<br/>Persist as component LLD"]
    S3D_CHECK -->|"No"| S4
    S3D --> S4

    S4["S4: Produce sync report<br/>Corrections, Additions,<br/>Omissions, Confirmations,<br/>LLD updated file + version"]

    S4 --> DONE(["fa:fa-check LLD sync complete"])

    %% ── Styles ──
    classDef startend fill:#d4f0d4,stroke:#2d7d2d,color:#1a3a1a
    classDef process fill:#d6e8f7,stroke:#2d5f8a,color:#1a2f44
    classDef decision fill:#f7eed6,stroke:#8a6d2d,color:#443a1a

    class START,DONE startend
    class REFACTOR,FEATURE,S1,S2_REF,S2_FEAT,S3,S3A,S3B,S3C,S3D,S4 process
    class MODE,S2,S3D_CHECK decision
```
