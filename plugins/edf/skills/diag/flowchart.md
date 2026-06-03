# /diag — Process flowchart

Visual overview of the on-demand diagnostics check. Identifies target files, opens them in the editor, reads diagnostics exports, fixes findings, runs CodeScene MCP health checks, and enforces the SonarQube quality gate. Decisions are orange, blocking gates are red.

```mermaid
flowchart TD
    START(["fa:fa-play /diag invoked"]) --> S1

    S1["S1: Identify target files<br/>Args provided → check those<br/>Otherwise → .diagnostics/ + git diff"] --> S2

    S2{"S2: .diagnostics/<br/>directory exists?"} -->|"No (worktree/CI)"| S7
    S2 -->|"Yes"| S3

    S3["S3: Open files in editor<br/>open-in-editor.sh, sleep 5<br/>Triggers CodeScene analysis"] --> S4

    S4["S4: Read diagnostics<br/>Parse .diagnostics/*.json<br/>Extract severity, message, line"] --> S5

    S5["S5: Report findings<br/>Errors first, then Warnings<br/>Suppress Info/Hints"] --> S5_CHK{"Errors or<br/>Warnings?"}
    S5_CHK -->|"No"| S7
    S5_CHK -->|"Yes"| S5_FIX["Fix all findings"]

    S5_FIX --> S6["S6: Confirm resolution<br/>Re-read diagnostics,<br/>verify timestamp advanced"]
    S6 --> S6_CHK{"Clean?"}
    S6_CHK -->|"No"| S5_FIX
    S6_CHK -->|"Yes"| S7

    S7["S7: CodeScene MCP health check<br/>code_health_score per file"] --> S7_CHK{"Score < 4.0?"}
    S7_CHK -->|"Yes, red"| S7_FIX["code_health_review →<br/>fix all findings → re-check"]
    S7_CHK -->|"4.0-9.8, yellow"| S7_REVIEW["code_health_review →<br/>fix all findings<br/>(skip only if blocked)"]
    S7_CHK -->|"> 9.8, green"| S8

    S7_FIX --> S7_CHK
    S7_REVIEW --> S8

    S8["S8: SonarQube quality gate<br/>sonarqube:sonar-quality-gate"] --> S8_CHK{"Gate pass?"}
    S8_CHK -->|"Yes"| DONE
    S8_CHK -->|"No"| S8_FIX["sonarqube:sonar-list-issues →<br/>fix all findings → re-check<br/>(skip only if blocked)"]
    S8_FIX --> S8

    DONE(["fa:fa-check Diagnostics clean"])

    %% ── Styles ──
    classDef startend fill:#d4f0d4,stroke:#2d7d2d,color:#1a3a1a
    classDef process fill:#d6e8f7,stroke:#2d5f8a,color:#1a2f44
    classDef decision fill:#f7eed6,stroke:#8a6d2d,color:#443a1a

    class START,DONE startend
    class S1,S3,S4,S5,S5_FIX,S6,S7,S7_FIX,S7_REVIEW,S8,S8_FIX process
    class S2,S5_CHK,S6_CHK,S7_CHK,S8_CHK decision
```
