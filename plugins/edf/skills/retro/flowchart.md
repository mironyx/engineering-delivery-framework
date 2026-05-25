# /retro — Process flowchart

Visual overview of the process retrospective. Gathers data from sessions, git history, issues, board, drift reports, and previous retros; assesses health across six dimensions; writes report with scorecard and actions.

```mermaid
flowchart TD
    START(["fa:fa-play /retro invoked"]) --> S1

    S1["S1: Gather data<br/>Session logs, git history,<br/>GitHub issues, project board,<br/>drift reports, previous retro"]

    S1 --> S2

    S2["S2: Assess process health<br/>Backlog hygiene, Definition of done,<br/>Commit discipline, Session continuity,<br/>Drift management, Multi-agent readiness"]

    S2 --> S3["S3: Write report<br/>docs/reports/retro/<br/>YYYY-MM-DD-process-retro.md<br/>What went well, needs improving,<br/>actions, health scorecard"]

    S3 --> S4["S4: Run drift scan<br/>Fresh drift report, reference<br/>findings in retro"]

    S4 --> S5["S5: Execute quick-win actions<br/>Any action <5 min →<br/>do it now, mark Done"]

    S5 --> S6["S6: Summarise<br/>Health scorecard,<br/>top 3 actions,<br/>report path"]

    S6 --> DONE(["fa:fa-check Retro complete"])

    %% ── Styles ──
    classDef startend fill:#d4f0d4,stroke:#2d7d2d,color:#1a3a1a
    classDef process fill:#d6e8f7,stroke:#2d5f8a,color:#1a2f44

    class START,DONE startend
    class S1,S2,S3,S4,S5,S6 process
```
