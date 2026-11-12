# /diag — Process flowchart

Visual overview of the on-demand diagnostics check. Identifies target files, runs CodeScene MCP health checks, runs SonarQube MCP analysis of the changed files (S3, only when invoked as `edf:diag sonar`), and reads diagnostics-exporter output last — skipped without error when `.diagnostics/` does not exist. Decisions are orange.

```mermaid
flowchart TD
    START(["fa:fa-play /diag invoked"]) --> S1

    S1["S1: Identify target files<br/>File args → check those<br/>Otherwise → git diff (src/ + tests/)"] --> S2

    S2["S2: CodeScene MCP health check<br/>code_health_score per file"] --> S2_CHK{"Score < 4.0?"}
    S2_CHK -->|"Yes, red"| S2_FIX["code_health_review →<br/>fix all findings → re-check"]
    S2_CHK -->|"4.0-9.8, yellow"| S2_REVIEW["code_health_review →<br/>fix all findings<br/>(skip only if blocked)"]
    S2_CHK -->|"> 9.8, green"| S3_GATE

    S2_FIX --> S2_CHK
    S2_REVIEW --> S3_GATE

    S3_GATE{"'sonar' in<br/>$ARGUMENTS?"} -->|"No (default)"| S4
    S3_GATE -->|"Yes"| S3_TOOL{"MCP analysis tool?<br/>analyze_file_list /<br/>analyze_code_snippet /<br/>run_advanced_code_analysis"}
    S3_TOOL -->|"None"| S3_SKIP["Report skipped + config hint<br/>(never sonar CLI)"]
    S3_TOOL -->|"Available"| S3["S3: changed-lines.py →<br/>analyse changed files"]
    S3 --> S3_FIX["Fix all issues on changed lines<br/>+ top 2 pre-existing by severity"]
    S3_FIX --> S3_RE["Re-analyse once"]
    S3_RE --> S4
    S3_SKIP --> S4

    S4{"S4: .diagnostics/<br/>exists?"} -->|"No (worktree/CI)"| DONE
    S4 -->|"Yes"| S4_OPEN["Open files in editor<br/>open-in-editor.sh, sleep 5"]
    S4_OPEN --> S4_READ["Read .diagnostics/*.json<br/>Errors first, then Warnings"]
    S4_READ --> S4_CHK{"Errors or<br/>Warnings?"}
    S4_CHK -->|"No"| DONE
    S4_CHK -->|"Yes"| S4_FIX["Fix all findings →<br/>re-read, re-score changed files"]
    S4_FIX --> S4_CHK

    DONE(["fa:fa-check Diagnostics clean"])

    %% ── Styles ──
    classDef startend fill:#d4f0d4,stroke:#2d7d2d,color:#1a3a1a
    classDef process fill:#d6e8f7,stroke:#2d5f8a,color:#1a2f44
    classDef decision fill:#f7eed6,stroke:#8a6d2d,color:#443a1a

    class START,DONE startend
    class S1,S2,S2_FIX,S2_REVIEW,S3,S3_SKIP,S3_FIX,S3_RE,S4_OPEN,S4_READ,S4_FIX process
    class S2_CHK,S3_GATE,S3_TOOL,S4,S4_CHK decision
```
