# /bug — Process flowchart

Visual overview of the bug investigation pipeline. From vague symptom through root cause analysis, LLD coverage check, classification, and issue creation. Agent spawns are purple, decisions are orange, blocking gates are red.

```mermaid
flowchart TD
    START(["fa:fa-play /bug invoked"]) --> S1

    S1["S1: Parse input<br/>Free-form text, file path,<br/>issue number, or context"] --> S1_AMBIG{"Ambiguous?"}
    S1_AMBIG -->|"Yes"| STOP_ASK(["fa:fa-hand-o-right Ask user to clarify"])
    S1_AMBIG -->|"No"| S2

    S2["S2: Check existing issues<br/>gh issue list --state open"] --> S2_EXISTS{"Match found?"}
    S2_EXISTS -->|"Yes, has root cause"| STOP_DUP(["fa:fa-ban Already tracked as #N"])
    S2_EXISTS -->|"Yes, lacks detail"| S2_ENRICH["Will enrich existing #N"]
    S2_EXISTS -->|"No"| S3

    S2_ENRICH --> S3

    S3["S3: Investigate<br/>Locate symptom → trace call chain<br/>→ identify root cause"] --> S3_AGENT{"Broad search<br/>needed?"}
    S3_AGENT -->|"Yes"| S3_EXPLORE(("Explore agent<br/>Codebase search"))
    S3_AGENT -->|"No"| S4
    S3_EXPLORE --> S4

    S4["S4: Check LLD coverage<br/>Read relevant LLD,<br/>locate manifest entry"] --> S5

    S5{"S5: Classify"} -->|"Code-only"| S5_CODE["LLD accurate,<br/>only implementation wrong"]
    S5 -->|"LLD gap"| S5_LLD["Design incomplete,<br/>code + LLD must change"]
    S5 -->|"Missing functionality"| S5_MISSING["Story never implemented,<br/>needs design first"]

    S5_CODE --> S6
    S5_LLD --> S6
    S5_MISSING --> S6

    S6["S6: Create or enrich issue<br/>Symptom, root cause, affected files,<br/>manifest ref, fix approach, ACs, BDD"]
    S6 --> S7

    S7["S7: Report<br/>Class, issue link,<br/>recommended next step"] --> DONE(["fa:fa-check Investigation complete"])

    %% ── Styles ──
    classDef startend fill:#d4f0d4,stroke:#2d7d2d,color:#1a3a1a
    classDef process fill:#d6e8f7,stroke:#2d5f8a,color:#1a2f44
    classDef agent fill:#e8d6f7,stroke:#6b2d8a,color:#2d1a3a
    classDef decision fill:#f7eed6,stroke:#8a6d2d,color:#443a1a
    classDef stop fill:#f7d6d6,stroke:#8a2d2d,color:#441a1a
    classDef human fill:#f7d6d6,stroke:#8a2d2d,color:#441a1a

    class START,DONE startend
    class S1,S2,S2_ENRICH,S3,S4,S5_CODE,S5_LLD,S5_MISSING,S6,S7 process
    class S3_EXPLORE agent
    class S1_AMBIG,S2_EXISTS,S3_AGENT,S5 decision
    class STOP_ASK human
    class STOP_DUP stop
```
