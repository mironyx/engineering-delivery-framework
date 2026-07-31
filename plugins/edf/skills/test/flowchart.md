# /test — Process flowchart

Visual overview of the verification runner. Parses the mode or file path, infers the language, resolves a wrapper-script command, and delegates execution to the `edf:test-runner` agent so verbose output never reaches the caller's context. Decisions are orange.

```mermaid
flowchart TD
    START(["fa:fa-play /test invoked"]) --> S1

    S1["S1: Parse $ARGUMENTS<br/>Split on whitespace,<br/>read first token"] --> S1_CHK{"First token is<br/>a file path?"}

    S1_CHK -->|"Yes (.ts/.tsx/.py or a path separator)"| S1_FILE["Mode: file<br/>Language inferred<br/>from extension"]
    S1_CHK -->|"No (keyword)"| S1_KW["Mode: all / full / typecheck /<br/>lint / build / e2e / audit<br/>Language: 2nd token, else all"]

    S1_FILE --> S2
    S1_KW --> S2

    S2["S2: Resolve command<br/>Map mode → wrapper script(s)<br/>under starters/scripts/"] --> S3

    S3["S3: Execute<br/>Launch edf:test-runner agent<br/>with the resolved command"] --> S4

    S4{"S4: Result?"}
    S4 -->|"PASS"| DONE
    S4 -->|"FAIL"| FAIL["Report failure<br/>(first 10 lines)<br/>Do NOT retry"]

    FAIL --> RETURN(["fa:fa-times Return to caller<br/>caller decides fix and re-run"])
    DONE(["fa:fa-check PASS reported"])

    %% ── Styles ──
    classDef startend fill:#d4f0d4,stroke:#2d7d2d,color:#1a3a1a
    classDef process fill:#d6e8f7,stroke:#2d5f8a,color:#1a2f44
    classDef decision fill:#f7eed6,stroke:#8a6d2d,color:#443a1a
    classDef failend fill:#f7d6d6,stroke:#8a2d2d,color:#441a1a

    class START,DONE startend
    class RETURN failend
    class S1,S1_FILE,S1_KW,S2,S3,FAIL process
    class S1_CHK,S4 decision
```
