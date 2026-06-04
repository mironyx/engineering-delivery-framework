# /feature-end — Process flowchart

Visual overview of the post-review wrap-up pipeline. Handles session log (find by feature ID per ADR-0037), cost tracking, rebase, merge, cleanup, manifest updates, and epic checklist ticking. Decisions are orange, blocking gates are red.

```mermaid
flowchart TD
    START(["fa:fa-play /feature-end invoked"]) --> S1

    S1["S1: Gather context<br/>Find PR, extract branch,<br/>check review status"] --> S1_CHK{"Changes<br/>requested?"}
    S1_CHK -->|"Yes"| STOP_REVIEW(["fa:fa-ban Stop: CHANGES_REQUESTED"])
    S1_CHK -->|"No"| S1_5

    S1_5["S1.5: LLD Sync<br/>Run edf:lld-sync if<br/>LLD covers this issue"] --> S1_5_CHK{"Already<br/>synced?"}
    S1_5_CHK -->|"Yes"| S2
    S1_5_CHK -->|"No"| S1_5_RUN(("edf:lld-sync"))
    S1_5_RUN --> S2

    S2["S2: Find session log by feature ID<br/>Append narrative sections<br/>(or write full log if not found)"] --> S2_5["S2.5: Query final cost<br/>query-feature-cost.py --stage final"]
    S2_5 --> S2_6["S2.6: Cost retrospective<br/>Read checkpoint table from<br/>session log (if Full track)"]

    S2_6 --> S3["S3: Commit remaining changes<br/>Session log + final fixes"]
    S3 --> S3_5["S3.5: Rebase onto latest base<br/>git rebase origin/base"]
    S3_5 --> S3_5_CHK{"Conflict?"}
    S3_5_CHK -->|"Yes"| STOP_CONFLICT(["fa:fa-ban Stop: rebase conflict"])
    S3_5_CHK -->|"No"| S4

    S4["S4: Merge PR<br/>gh pr merge --squash"] --> S4_CHK{"Merged?"}
    S4_CHK -->|"No"| STOP_MERGE(["fa:fa-ban Stop: merge failed"])
    S4_CHK -->|"Yes"| S5

    S5["S5+6: Clean up & update board<br/>Delete branch, move to Done,<br/>close issue"] --> S6_4["S6.4: Update coverage manifest<br/>Flip status to Implemented,<br/>populate files:"]
    S6_4 --> S6_5["S6.5: Tick parent epic<br/>checkbox in epic body"]

    S6_5 --> S7["S7: Report<br/>PR merged, issue closed,<br/>suggest next item"]

    S7 --> DONE(["fa:fa-check Feature end complete"])

    %% ── Styles ──
    classDef startend fill:#d4f0d4,stroke:#2d7d2d,color:#1a3a1a
    classDef process fill:#d6e8f7,stroke:#2d5f8a,color:#1a2f44
    classDef agent fill:#e8d6f7,stroke:#6b2d8a,color:#2d1a3a
    classDef decision fill:#f7eed6,stroke:#8a6d2d,color:#443a1a
    classDef stop fill:#f7d6d6,stroke:#8a2d2d,color:#441a1a

    class START,DONE startend
    class S1,S1_5,S2,S2_5,S2_6,S3,S3_5,S4,S5,S6_4,S6_5,S7 process
    class S1_5_RUN agent
    class S1_CHK,S1_5_CHK,S3_5_CHK,S4_CHK decision
    class STOP_REVIEW,STOP_CONFLICT,STOP_MERGE stop
```
