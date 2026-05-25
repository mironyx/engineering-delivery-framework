# /feature — Process flowchart

Visual overview of the autonomous implementation cycle. The skill handles pre-flight, issue selection, branch creation, and hands off to /feature-core. Agent spawns are purple, decisions are orange, blocking gates are red.

```mermaid
flowchart TD
    START(["fa:fa-play /feature invoked"]) --> S0

    S0["S0: Pre-flight<br/>git checkout main && git pull"] --> S0_CHK{"Clean?"}
    S0_CHK -->|"No"| STOP_DIRTY(["fa:fa-ban Stop: uncommitted changes"])
    S0_CHK -->|"Yes"| S1

    S1{"S1: Arguments?"} -->|"epic N"| S1_EPIC["Read epic, pick first<br/>unchecked task"]
    S1 -->|"issue number"| S1_DIRECT["Use issue directly"]
    S1 -->|"none"| S1_TOP["gh issue list<br/>--label kind:task<br/>--state open --limit 1"]

    S1_EPIC --> S1_EMPTY{"Tasks remain?"}
    S1_EMPTY -->|"No"| STOP_EPIC_DONE(["fa:fa-ban Epic has no remaining tasks"])
    S1_EMPTY -->|"Yes"| S1_GUARD
    S1_DIRECT --> S1_GUARD
    S1_TOP --> S1_GUARD

    S1_GUARD{"Epic label?"} -->|"Yes"| STOP_EPIC(["fa:fa-ban Use /feature epic N"])
    S1_GUARD -->|"No"| S1_VALIDATE["Validate: design ref,<br/>BDD specs, acceptance criteria"]
    S1_VALIDATE --> S1_VALIDATE_CHK{"Sufficient<br/>context?"}
    S1_VALIDATE_CHK -->|"No"| STOP_CONTEXT(["fa:fa-ban Stop: missing context"])
    S1_VALIDATE_CHK -->|"Yes"| S1_TAG["Tag session<br/>tag-session.py"]

    S1_TAG --> S2["S2: Create feature branch<br/>feat/slug from origin/main"]
    S2 --> S2_BOARD["Move issue to In Progress<br/>gh-project-status.sh"]

    S2_BOARD --> S3(("S3: /feature-core<br/>Hand off to core<br/>implementation cycle"))

    S3 --> DONE(["fa:fa-check Feature complete"])

    %% ── Styles ──
    classDef startend fill:#d4f0d4,stroke:#2d7d2d,color:#1a3a1a
    classDef process fill:#d6e8f7,stroke:#2d5f8a,color:#1a2f44
    classDef agent fill:#e8d6f7,stroke:#6b2d8a,color:#2d1a3a
    classDef decision fill:#f7eed6,stroke:#8a6d2d,color:#443a1a
    classDef stop fill:#f7d6d6,stroke:#8a2d2d,color:#441a1a

    class START,DONE startend
    class S0,S1_EPIC,S1_DIRECT,S1_TOP,S1_VALIDATE,S1_TAG,S2,S2_BOARD process
    class S3 agent
    class S0_CHK,S1,S1_EMPTY,S1_GUARD,S1_VALIDATE_CHK decision
    class STOP_DIRTY,STOP_EPIC_DONE,STOP_EPIC,STOP_CONTEXT stop
```
