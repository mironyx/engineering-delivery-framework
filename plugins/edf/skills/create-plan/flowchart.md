# /create-plan — Process flowchart

Visual overview of the implementation plan creation process. Reads inputs, checks existing state, clarifies open questions, proposes breakdown, and writes the plan. Human gates are red.

```mermaid
flowchart TD
    START(["fa:fa-play /create-plan invoked"]) --> S1

    S1["S1: Read input<br/>Requirements doc, ADR,<br/>issue, or free-form"] --> S1_READ["Read all references:<br/>ADRs, requirements, LLDs,<br/>source files"]

    S1_READ --> S2["S2: Check existing state<br/>Open issues, design docs<br/>Avoid duplicates"]

    S2 --> S3["S3: Clarify before writing<br/>Present understanding,<br/>resolve open questions"] --> S3_CHK{"Open questions?"}
    S3_CHK -->|"Yes"| S3_ASK(["fa:fa-hand-o-right Resolve with user"])
    S3_CHK -->|"No"| S4
    S3_ASK --> S3

    S4["S4: Propose epic + task breakdown<br/>Decomposition rules from ADR-0018"] --> S4_GATE(["fa:fa-hand-o-right Wait for user approval"])

    S4_GATE --> S5["S5: Write plan<br/>docs/plans/YYYY-MM-DD-short-name.md"]

    S5 --> S6["S6: Report next step<br/>Suggest /architect epic N<br/>or /architect plan-path"]

    S6 --> DONE(["fa:fa-check Plan complete"])

    %% ── Styles ──
    classDef startend fill:#d4f0d4,stroke:#2d7d2d,color:#1a3a1a
    classDef process fill:#d6e8f7,stroke:#2d5f8a,color:#1a2f44
    classDef decision fill:#f7eed6,stroke:#8a6d2d,color:#443a1a
    classDef human fill:#f7d6d6,stroke:#8a2d2d,color:#441a1a

    class START,DONE startend
    class S1,S1_READ,S2,S3,S4,S5,S6 process
    class S3_CHK decision
    class S3_ASK,S4_GATE human
```
