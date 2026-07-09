# /feature-team — Process flowchart

Visual overview of the parallel implementation pipeline. The lead parses arguments, spawns
teammate agents in waves, monitors progress, gates on human review, and tears down. Agent
spawns are purple, decisions are orange, blocking gates are red.

```mermaid
flowchart TD
    START(["fa:fa-play /feature-team invoked"]) --> S0

    %% ── Step 0: Pre-flight ──
    S0["S0: git checkout main &&<br/>git pull origin main"] --> S0_CHK{"Success?"}
    S0_CHK -->|"No (uncommitted changes)"| STOP_PREFLIGHT(["fa:fa-ban Stop: tell user"])
    S0_CHK -->|"Yes"| S1

    %% ── Step 1: Parse arguments ──
    S1{"S1: Mode?"} -->|"epic N"| S1_EPIC
    S1 -->|"-n N"| S1_N["Query board for top N<br/>Todo items"]
    S1 -->|"explicit numbers"| S1_DIRECT["Use issue numbers directly"]

    subgraph EPIC_MODE["Epic Mode"]
        S1_EPIC["Read epic: gh issue view"] --> S1_EPIC_LABEL{"Has epic<br/>label?"}
        S1_EPIC_LABEL -->|"No"| STOP_NOT_EPIC(["fa:fa-ban Not an epic"])
        S1_EPIC_LABEL -->|"Yes"| S1_EPIC_TASKS["Parse unchecked tasks<br/>from checklist"]
        S1_EPIC_TASKS --> S1_EPIC_EMPTY{"Unchecked<br/>tasks?"}
        S1_EPIC_EMPTY -->|"No"| STOP_NO_TASKS(["fa:fa-ban No remaining tasks"])
        S1_EPIC_EMPTY -->|"Yes"| S1_WAVES{"Wave info<br/>in body?"}
        S1_WAVES -->|"Execution Order table"| S1_WAVES_TABLE["Parse waves from table"]
        S1_WAVES -->|"Mermaid diagram"| S1_WAVES_DAG["Derive waves by<br/>topological sort"]
        S1_WAVES -->|"Neither"| S1_WAVES_NONE["All tasks in parallel<br/>Warn: no dependency info"]
        S1_WAVES_TABLE --> S1_EPIC_BOARD
        S1_WAVES_DAG --> S1_EPIC_BOARD
        S1_WAVES_NONE --> S1_EPIC_BOARD
        S1_EPIC_BOARD["Move epic to In Progress<br/>gh-project-status.sh"]
    end

    S1_EPIC_BOARD --> S1_GUARD
    S1_N --> S1_GUARD
    S1_DIRECT --> S1_GUARD

    S1_GUARD{"Any issue has<br/>epic label?"}
    S1_GUARD -->|"Yes"| STOP_EPIC_TASK(["fa:fa-ban Use epic mode instead"])
    S1_GUARD -->|"No"| S1_READ["Read each issue:<br/>gh issue view --json title,body,labels"]

    %% ── Steps 2-3: Validate & task list ──
    S1_READ --> S2["S2: Validate each issue<br/>Design ref + acceptance criteria"]
    S2 --> S2_CHK{"All valid?"}
    S2_CHK -->|"No"| STOP_VALIDATE(["fa:fa-ban Report failures, stop"])
    S2_CHK -->|"Yes"| S3["S3: Create shared task list<br/>One per issue, state: pending"]

    %% ── Steps 4-6: Wave orchestration loop ──
    S3 --> WAVE_ENTRY["Begin wave"]
    WAVE_ENTRY --> S4_PRE

    subgraph WAVE["Wave Orchestration (Steps 4-6)"]
        S4B(("S4: Agent calls<br/>One per teammate<br/>Same message, background<br/>Team forms automatically")) --> S4B_NOTE["Each teammate: worktree →<br/>tag session → edf:feature-core →<br/>report PR, wait for edf:feature-end"]
        S4B_NOTE --> S5["S5: Monitor<br/>Teammates notify lead<br/>when idle or blocked"]
        S5 --> S6["S6: Report PRs to user"]
        S6 --> S6_GATE["Human review gate<br/>Lead MUST NOT send edf:feature-end<br/>autonomously"]
        S6_GATE --> S6_WAIT["Wait for user:<br/>edf:feature-end N"]
        S6_WAIT --> S6_FWD["Lead forwards edf:feature-end<br/>to teammate via SendMessage"]
        S6_FWD --> S6_TEAM_DONE["Teammate runs edf:feature-end<br/>reports complete"]
        S6_TEAM_DONE --> S6_WAVES{"More waves?"}
        S6_WAVES -->|"Yes"| S6_SHUTDOWN["SendMessage shutdown_request<br/>then pane cleanup if split-pane mode"]
        S6_SHUTDOWN --> WAVE_ENTRY
    end

    S6_WAVES -->|"No, all done"| S7

    %% ── Steps 7-9: Teardown ──
    subgraph TEARDOWN["Steps 7-9: Teardown"]
        S7["S7: Final summary<br/>Issue → PR → merged<br/>Notes from feature-ends"]
        S7 --> S7_EPIC{"Epic mode?"}
        S7_EPIC -->|"Yes"| S7_CLOSE["Close epic:<br/>gh-project-status done<br/>gh issue close"]
        S7_EPIC -->|"No"| S8
        S7_CLOSE --> S8["S8: Team session log<br/>docs/sessions/YYYY-MM/YYYY-MM-DD-team-...md"]
        S8 --> S9(("S9: SendMessage shutdown_request<br/>to ALL remaining teammates<br/>Parallel, same message"))
        S9 --> S9B["S9b: If split-pane mode,<br/>glob session-*/config.json<br/>for pane_ids, tmux kill-pane each.<br/>In-process mode: nothing to clean up."]
    end

    S9B --> DONE(["fa:fa-check Team complete"])

    %% ── Styles ──
    classDef startend fill:#d4f0d4,stroke:#2d7d2d,color:#1a3a1a
    classDef process fill:#d6e8f7,stroke:#2d5f8a,color:#1a2f44
    classDef agent fill:#e8d6f7,stroke:#6b2d8a,color:#2d1a3a
    classDef decision fill:#f7eed6,stroke:#8a6d2d,color:#443a1a
    classDef stop fill:#f7d6d6,stroke:#8a2d2d,color:#441a1a

    class START,DONE startend
    class S0,S1_N,S1_DIRECT,S1_EPIC,S1_EPIC_TASKS,S1_WAVES_TABLE,S1_WAVES_DAG,S1_WAVES_NONE,S1_EPIC_BOARD,S1_READ,S2,S3,WAVE_ENTRY,S4B_NOTE,S5,S6,S6_GATE,S6_WAIT,S6_FWD,S6_TEAM_DONE,S6_SHUTDOWN,S7,S7_CLOSE,S8,S9B process
    class S4B,S9 agent
    class S0_CHK,S1,S1_EPIC_LABEL,S1_EPIC_EMPTY,S1_WAVES,S1_GUARD,S2_CHK,S6_WAVES,S7_EPIC decision
    class STOP_PREFLIGHT,STOP_NOT_EPIC,STOP_NO_TASKS,STOP_EPIC_TASK,STOP_VALIDATE stop
```
