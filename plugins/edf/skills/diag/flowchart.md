# /diag — Process flowchart

Visual overview of the on-demand diagnostics check. Identifies target files, opens them in the editor, reads diagnostics exports, fixes findings, and runs CodeScene MCP health checks. Decisions are orange, blocking gates are red.

```mermaid
flowchart TD
    START(["fa:fa-play /diag invoked"]) --> S1

    S1["S1: Identify target files<br/>Args provided → check those<br/>Otherwise → .diagnostics/ + git diff"] --> S2

    S2["S2: Open files in editor<br/>open-in-editor.sh, sleep 5<br/>Triggers CodeScene analysis"] --> S3

    S3["S3: Read diagnostics<br/>Parse .diagnostics/*.json<br/>Extract severity, message, line"] --> S4

    S4["S4: Report findings<br/>Errors first, then Warnings<br/>Suppress Info/Hints"] --> S4_CHK{"Errors or<br/>Warnings?"}
    S4_CHK -->|"No"| S6
    S4_CHK -->|"Yes"| S4_FIX["Fix all findings"]

    S4_FIX --> S5["S5: Confirm resolution<br/>Re-read diagnostics,<br/>verify timestamp advanced"]
    S5 --> S5_CHK{"Clean?"}
    S5_CHK -->|"No"| S4_FIX
    S5_CHK -->|"Yes"| S6

    S6["S6: CodeScene MCP health check<br/>code_health_score per file"] --> S6_CHK{"Score < 4.0?"}
    S6_CHK -->|"Yes, red"| S6_FIX["code_health_review →<br/>fix all findings → re-check"]
    S6_CHK -->|"4.0-9.8, yellow"| S6_REVIEW["Review findings,<br/>fix in-scope items"]
    S6_CHK -->|"> 9.8, green"| DONE

    S6_FIX --> S6_CHK
    S6_REVIEW --> DONE(["fa:fa-check Diagnostics clean"])

    %% ── Styles ──
    classDef startend fill:#d4f0d4,stroke:#2d7d2d,color:#1a3a1a
    classDef process fill:#d6e8f7,stroke:#2d5f8a,color:#1a2f44
    classDef decision fill:#f7eed6,stroke:#8a6d2d,color:#443a1a

    class START,DONE startend
    class S1,S2,S3,S4,S4_FIX,S5,S6,S6_FIX,S6_REVIEW process
    class S4_CHK,S5_CHK,S6_CHK decision
```
