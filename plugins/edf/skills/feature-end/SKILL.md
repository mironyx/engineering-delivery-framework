---
name: feature-end
description: Wrap up a completed feature after PR review. Writes session log, commits remaining changes, merges PR, switches to parent branch, cleans up. Invoking this skill IS the approval — no further confirmations.
allowed-tools: Read, Write, Edit, MultiEdit, Bash, Glob, Grep, Agent, Skill, TodoWrite
---

# Feature End — Post-Review Wrap-Up

Finalises a feature branch after the PR has been reviewed and approved. Handles session log, final commit, merge, and cleanup.

**Pre-requisite:** A PR exists for the current branch (or the given issue) and has been reviewed/approved.

**Usage:**
- `/feature-end` — detects the PR from the current branch (original behaviour)
- `/feature-end <issue-number>` — looks up the PR for the given issue. If an orphaned worktree exists (crashed teammate), switches into it and recovers. Otherwise checks out the branch (used by `edf:feature-team` lead when triggering remotely via message).

A [flowchart.md](flowchart.md) companion file visualises this pipeline. Update it when changing the wrap-up sequence, merge strategy, or cleanup steps.

## Process

Execute these steps sequentially. Do not skip steps.

**Autonomy rule:** Invoking `/feature-end` IS the user's approval to merge and clean up. Do not stop to ask for merge confirmation, do not ask "ready to merge?", do not wait for "approved" — run all steps straight through. Only stop for the conditions listed under **Blocker policy** at the end of this file.

### Step 1: Gather context

If an issue number argument was provided:
1. Find the PR for the issue:
   ```bash
   gh pr list --search "closes #<issue-number>" --json number,title,baseRefName,state,url,headRefName --state open
   ```
   If no open PR is found, try `--state merged` in case it was already merged. If still none, stop and report.
2. Extract the head branch (`headRefName`) and read the session ID — PR body first, prom file as fallback:
   ```bash
   OLD_SESSION_ID=$(gh pr view <pr-number> --json body --jq '.body' | bash ${CLAUDE_PLUGIN_ROOT}/hooks/run-python.sh ${CLAUDE_PLUGIN_ROOT}/bin/extract-session-id.py --issue <issue-number>)
   ```
3. Detect an orphaned worktree — a worktree on that branch left behind by a crashed teammate:
   ```bash
   MAIN_REPO=$(dirname "$(git rev-parse --git-common-dir)")
   ORPHAN_WORKTREE=$(git worktree list | python3 -c "
   import sys
   lines = sys.stdin.read().strip().splitlines()
   for line in lines:
       parts = line.split()
       if len(parts) >= 3 and parts[2] == '[<head-branch>]' and parts[0] != '$MAIN_REPO':
           print(parts[0])
           break
   ")
   ```
4. **If an orphaned worktree is found (crash recovery mode):**
   - Switch into it and register this recovery session under the same feature ID for cost aggregation:
     ```bash
     cd "$ORPHAN_WORKTREE"
     bash ${CLAUDE_PLUGIN_ROOT}/hooks/run-python.sh ${CLAUDE_PLUGIN_ROOT}/bin/tag-session.py <issue-number> --cont
     ```
   - Proceed with all remaining steps from inside the worktree. `IS_WORKTREE=yes` will be detected automatically in Step 5+6, which handles self-cleanup.
5. **If no orphaned worktree is found** (normal mode — e.g. triggered by lead via SendMessage):
   ```bash
   gh pr checkout <pr-number>
   ```

If no argument was provided (original behaviour):
1. Identify the current branch: `git branch --show-current`.
2. Find the open PR for this branch: `gh pr view --json number,title,baseRefName,state,reviews,url`.
   - If no PR exists, stop and report: "No open PR found for the current branch."

In both cases:
- Extract the **base branch**, **PR number**, and **URL**.
- Find the associated issue number from the PR body (look for `Closes #N` or `#N` references).
- Derive the feature ID: `FEATURE_ID="${EDF_FEATURE_PREFIX}-<issue-number>"`. Read `EDF_FEATURE_PREFIX` from `.env`.
- **Check review status:** `gh pr view <number> --json reviewDecision --jq .reviewDecision`. If the result is `CHANGES_REQUESTED`, stop and report per the Blocker policy. (Empty/null or `APPROVED` are fine — repos without required reviews will return empty.)
- Read the latest session log in `docs/sessions/` (search recursively — session logs are organised in `YYYY-MM/` monthly folders per ADR-0036). **Skip this in crash recovery mode** (`OLD_SESSION_ID` set) — the JSONL read in Step 2 provides the implementation history instead.

### Step 1.5: Sync the LLD (pressure-adaptive)

**Idempotency check:** Before running, check whether lld-sync was already completed this run:
```bash
git log --oneline origin/main..HEAD | grep -i "lld-sync\|lld sync" | head -1
```
If a matching commit exists, skip this step and note "lld-sync already committed" in the session log.

**Determine whether the issue has an LLD:** check the issue body for an `LLD reference` link or
search `docs/design/v*/lld-*.md` (new version-foldered per ADR-0036) and `docs/design/lld-*.md`
(legacy flat) for files referencing this issue number. If no LLD covers this
issue (chore or infrastructure task), skip and note "lld-sync skipped — no LLD covers this
issue" in the session log.

- **Any change that touches files under an LLD:** Run `edf:lld-sync <issue-number>` to update
  the LLD with implementation learnings. **Capture the structured sync report (Corrections /
  Additions / Omissions / Confirmations / LLD updated) — Step 2 copies it verbatim into the
  session log under `## LLD Sync report`.** Decisions narrative and review feedback narrative
  still go into their own sections; the `## LLD Sync report` section is the unedited
  `edf:lld-sync` Step 4 output, preserved for future readers.

### Step 2: Write or complete session log — MANDATORY

**Idempotency check:** find the session log by feature ID:
```bash
ls docs/sessions/YYYY-MM/*-<FEATURE_ID>.md 2>/dev/null | head -1
```
If a file exists, skip to step 2.2 (append narrative). Otherwise, the file does not exist
(Light track, or crash recovery where feature-core didn't run) — proceed to step 2.1 (write full log).

**Do not skip.** A session log must always be written, even for small changes.

**2.1 — Log not found (Light track / crash recovery): write full log in one pass**

If no existing session log was found (feature-core was on Light track, or was skipped):

1. Determine the filename:
   - Slug: derive from issue title (2-4 words, kebab-case).
   - N: increment from the latest log for today in `docs/sessions/YYYY-MM/`.
   - Filename: `docs/sessions/YYYY-MM/YYYY-MM-DD-session-N-<slug>-<FEATURE_ID>.md`
2. **Crash recovery only** — if `OLD_SESSION_ID` is set and non-empty, recover the original session's implementation history from its JSONL:
   ```python
   import json, pathlib, subprocess, os, re

   result = subprocess.run(['git', 'rev-parse', '--git-common-dir'], capture_output=True, text=True)
   root = pathlib.Path(result.stdout.strip()).parent.resolve()
   path_str = str(root).lower().replace(":\\", "--").replace("\\", "-").replace("/", "-").replace(":", "")
   jsonl_path = pathlib.Path.home() / '.claude' / 'projects' / path_str / f'{OLD_SESSION_ID}.jsonl'

   if jsonl_path.exists():
       events = [json.loads(l) for l in jsonl_path.read_text().splitlines() if l.strip()]
       # Extract: file writes/edits (tool_use name in Write/Edit/MultiEdit),
       # test run results (Bash with test/typecheck/lint), assistant reasoning messages,
       # and any tool_result content showing pass/fail outcomes.
       # Use this as the primary source for "Work completed" and "Decisions made".
   ```
   Note in the session log: _"Session recovered from crashed teammate (original session: `<OLD_SESSION_ID>`)."_
3. Write the full session log with all sections (approach rationale, work completed, decisions, LLD sync report, cost retrospective).
   Use `## Approach rationale` as the first section even on Light track — it is cheap to add and valuable later.
4. Skip to step 2.3 (stage).

**2.2 — Log found (Full track): append narrative sections**

Read the existing session log. It contains `## Approach rationale` and `## Cost checkpoints` written
by feature-core (per ADR-0037). Append the remaining sections:

- **## Work completed** — what was implemented, issue number, PR link
- **## Decisions made** — approach choices, design deviations, anything the next dev should know
- **## Review feedback** — what pr-review found, what was fixed, what was deferred
- **## LLD Sync report** — paste the structured `edf:lld-sync` Step 4 output **verbatim** (the Corrections / Additions / Omissions / Confirmations / LLD updated sections you saw in the previous turn). Do not summarise or paraphrase; future readers and the dogfood retro need the unedited report. If `edf:lld-sync` was skipped because no LLD covers this issue, write: _"Skipped — no LLD covers this issue."_
- **## Cost retrospective** — see Step 2.6; write a data-backed analysis using the `## Cost checkpoints` table already in the file.
- **## Next steps** — follow-up items, suggested next board item

**2.3 — Stage**

Stage the session log:
```bash
git add docs/sessions/YYYY-MM/YYYY-MM-DD-session-N-<slug>-<FEATURE_ID>.md
```

### Step 2.5: Query final feature cost

**Idempotency check:** Skip if the `ai-cost-final` label is already on the issue:
```bash
gh issue view <issue-number> --json labels --jq '.labels[].name' | grep -q "^ai-cost-final" && echo "SKIP" || echo "RUN"
```
If `SKIP`, note "cost already labelled" in the session log and proceed to Step 2.6.

Query Prometheus for the full feature total (all sessions since `edf:feature` started — same
session IDs registered in the textfile). This is the **final** cost snapshot; comparing it
to the cost recorded in the PR body at creation time shows how much effort was spent
post-PR (review fixes, re-runs, etc.). Applies `ai-cost-final:*`, `input-tokens-final:*`, and `output-tokens-final:*` labels to the issue and PR (complementing the `*-pr` labels written at PR creation).

Derive the issue number from the git log and run the shared script:

```bash
ISSUE=$(git log --oneline -10 | grep -o '#[0-9]*' | head -1 | tr -d '#')
PR=$(gh pr view --json number --jq .number 2>/dev/null || echo "")
COST_OUTPUT=$(bash ${CLAUDE_PLUGIN_ROOT}/hooks/run-python.sh ${CLAUDE_PLUGIN_ROOT}/bin/query-feature-cost.py --issue $ISSUE ${PR:+--pr $PR} --stage final)
echo "$COST_OUTPUT"
```

**If the command must run as a background task**, redirect to a file and use the Read tool:
```bash
bash ${CLAUDE_PLUGIN_ROOT}/hooks/run-python.sh ${CLAUDE_PLUGIN_ROOT}/bin/query-feature-cost.py --issue $ISSUE ${PR:+--pr $PR} --stage final > /tmp/cost-output.txt 2>&1
```
Then read `/tmp/cost-output.txt` with the Read tool — never `cat`, which can silently produce empty output on some platforms.

Post the output as a PR comment:

```bash
gh pr comment <number> --body "$COST_OUTPUT"
```

Store the cost figures — you will include them in the session log in Step 2.

### Step 2.6: Cost retrospective

Analyse the full cost and write a brief retrospective to include in the session log under
`## Cost retrospective`. This is the institutional memory that makes future features cheaper.

**Data source:** If the session log already contains a `## Cost checkpoints` table (written by
feature-core on Full track per ADR-0037), use it as the primary data source. The gaps between
rows are the cost buckets:
- **3c → 5:** design reading + test-author + implementation + fix cycles (the implementation friction)
- **5 → 8:** diagnostics + evaluator + commit/push (quality gate overhead)
- **8 → 9:** review + review fixes (post-PR rework)

If no checkpoint table exists (Light track), fall back to git log analysis as below.

1. **Cost summary:** PR-creation cost (from PR body `Usage` section) vs final total.
   Delta = post-PR work (review fixes, re-runs, extra commits).
   On Full track, the Step 8 checkpoint row IS the PR-creation cost.

2. **Identify cost drivers.** For Full track, read the checkpoint table:
   - "green on attempt N" where N > 1 → fix cycles were expensive
   - Large 5→8 gap → evaluator found many issues or diagnostics needed multiple rounds
   - Large 8→9 gap → review returned blockers that needed rework

   For Light track, check the git log and session history:

   | Driver | How to detect | Typical impact |
   |--------|--------------|----------------|
   | Context compaction | Session summary starts "This session is being continued..." | High — re-summarising inflates cache-write tokens |
   | Fix cycles (RED→fix rounds) | Count commits before the first green run | Medium — each test run adds tokens |
   | Agent spawns | Count Agent calls in the session | Medium — each spawn re-sends the full diff |
   | LLD quality gaps | pr-review found design-contract violations → extra fix commit | Medium — avoidable with better LLD signatures upfront |

3. **Improvement actions:** For each driver, record a concrete change for next time:
   - "Step 4cF→5: 3 fix cycles (58% of tokens) → test-author missed edge case X; add to contract properties checklist"
   - "LLD private-helper signatures were wrong → validate signatures in a quick typecheck pass before writing tests"
   - "Context compaction hit → keep PRs under 200 lines; break large features into two issues"

### Step 3: Commit remaining changes

1. Run `git status` to check for uncommitted changes (session log, review fixes, etc.).
2. If there are changes to commit:
   ```bash
   git add <specific-files>
   git commit -m "docs: session log and final fixes #<issue-number>"
   ```
3. Push to remote: `git push`.

### Step 3.5: Rebase onto latest base branch

With multiple agents working in parallel, the base branch may have advanced since this branch was cut.
Rebase before merging so CI validates the integrated code and the merge is conflict-free.

```bash
BASE=$(gh pr view --json baseRefName --jq .baseRefName)
git fetch origin "$BASE"
git merge-base --is-ancestor "origin/$BASE" HEAD \
  && echo "ALREADY_UP_TO_DATE" \
  || (git rebase "origin/$BASE" && git push --force-with-lease && echo "REBASED_AND_PUSHED")
```

- **Already up to date** (`ALREADY_UP_TO_DATE`) → proceed directly to Step 4.
- **Rebased cleanly** (`REBASED_AND_PUSHED`) → proceed to Step 4. CI will re-run on the rebased commit; wait for it to pass before merging (use `gh run watch`).
- **Rebase conflict** (non-zero exit from `git rebase`) → run `git rebase --abort`, stop, and report the conflicting files to the user. Do not attempt to resolve conflicts automatically.

### Step 3.7: Switch CWD to main repo (worktree mode only)

**If running inside a linked worktree** (`IS_WORKTREE = "yes"` from Step 5+6 detection), switch the shell's working directory to the main repo **now, before the merge**, in a dedicated Bash call:

```bash
MAIN_REPO=$(dirname "$(git rev-parse --git-common-dir)")
cd "$MAIN_REPO"
```

This must be a **separate** Bash call. The Bash tool retains CWD between calls, so all subsequent calls will start from the main repo. This prevents every post-merge Bash call from failing with "path does not exist" when git auto-prunes the worktree after the remote branch is deleted on squash-merge.

Skip this step if already in the main repo (`IS_WORKTREE = "no"`).

### Step 4: Merge the PR

First check whether the PR is already merged (user may have merged via GitHub UI):
```bash
gh pr view <number> --json state
```
Parse the `state` field from the raw JSON output. If `"state":"MERGED"`, skip the merge command and proceed directly to Step 5.

Otherwise merge immediately — **no user prompt**. Invoking `/feature-end` is itself the approval:

```bash
gh pr merge <number> --squash 2>&1 || true
# Do NOT pass --delete-branch here — deleting the local branch ref while inside the worktree
# makes the worktree prunable; if git worktree prune runs (hook or concurrent process) the
# directory disappears and all subsequent Bash calls fail. Branch deletion is handled in Step 5+6
# after cd-ing to the main repo. Verify the merge succeeded:
gh pr view <number> --json state --jq .state
```

If the state is `MERGED`, proceed. If it is still `OPEN` (merge genuinely failed), stop and report per the Blocker policy.

**All steps must run automatically without user approval — only stop for a real blocker.**
### Step 5 + 6: Clean up, sync, and update project board

Read the issue state from the earlier `gh pr view` output (merged PRs close the issue automatically).
Chain **all** of cleanup + board update into a **single Bash call** to minimise approval prompts:

**Worktree detection:** If running inside a linked worktree (parallel mode), the cleanup must
happen from the main repo — you cannot remove a worktree from within itself. Detect and handle:

```bash
WORKTREE_PATH=$(pwd)
MAIN_REPO=$(dirname "$(git rev-parse --git-common-dir)")
IS_WORKTREE=$([ "$WORKTREE_PATH" != "$MAIN_REPO" ] && echo "yes" || echo "no")
```

Then chain all cleanup in a **single Bash call**:

```bash
# If in a worktree: cd to main repo first, then clean up worktree + branch
# If in main repo: standard cleanup (git branch -d works directly)

cd "$MAIN_REPO" && git pull --rebase \
  && { [ "$IS_WORKTREE" = "yes" ] && git worktree remove "$WORKTREE_PATH" --force 2>&1 || true; } \
  && { git branch -d <feature-branch> 2>&1 || true; } \
  && { bash ${CLAUDE_PLUGIN_ROOT}/bin/gh-project-status.sh <issue-number> done 2>&1 || true; } \
  && { gh issue close <issue-number> 2>&1 || true; }
```

The `|| true` inside `{ }` groups ensures:
- Not in a worktree — `git worktree remove` skipped cleanly.
- A missing local branch does not abort the chain.
- A board item already at Done (script exits 0 with no-op) continues cleanly.
- An already-closed issue (`gh issue close` 422) is silently ignored.
- If `cd` or `git pull` fails, the chain **stops** rather than running from the wrong directory.

**Do not run separate Bash calls** for branch delete, board update, and issue close — they must be one call.

### Step 6.4: Update coverage manifest (per ADR-0026)

If the parent epic has a coverage manifest (at `docs/design/v*/coverage-<epic-slug>.yaml` per
ADR-0036 or `docs/design/coverage-<epic-slug>.yaml` legacy flat), populate the entries that
this feature implemented.

1. Determine the epic slug and locate the manifest:
   ```bash
   EPIC_SLUG=$(gh issue view <issue-number> --json body --jq '.body' | bash ${CLAUDE_PLUGIN_ROOT}/hooks/run-python.sh ${CLAUDE_PLUGIN_ROOT}/bin/update-coverage-manifest.py --extract-epic-slug)
   # Search version-foldered first (ADR-0036), then legacy flat
   MANIFEST=$(ls docs/design/v*/coverage-${EPIC_SLUG}.yaml docs/design/coverage-${EPIC_SLUG}.yaml 2>/dev/null | head -1)
   ```

2. If `$MANIFEST` does not exist, skip this step silently — the feature predates Stage 2 or the
   epic is not a pilot epic.

3. If it exists, find the manifest entries whose `lld:` anchor lives in the LLD file(s) that
   this PR implements (read the `LLD reference` from the issue body or from `lld-sync` output).
   For each matching entry:
   - Set `issue:` to the current issue number (integer, e.g. `394`).
   - Append every merged source file path (from `git diff --name-only origin/main...HEAD -- 'src/**'`,
     captured **before** the rebase in Step 3.5) to `files:`.
   - Flip `status` from `Approved` (or `Revised`) to `Implemented`.
   - Leave `status` at `Revised` if `edf:lld-sync` already flipped it — `Revised` outranks
     `Implemented` until the next feature confirms the new shape; in that case still set
     `issue:` and append to `files:` but keep `status: Revised`.

4. Verify the manifest entries point at anchors that resolve:
   ```bash
   bash ${CLAUDE_PLUGIN_ROOT}/hooks/run-python.sh ${CLAUDE_PLUGIN_ROOT}/bin/update-coverage-manifest.py --verify-anchors "$MANIFEST"
   ```

5. Stage and amend the manifest into the existing session-log commit (Step 3) if it has not been
   pushed yet, otherwise create a follow-up commit:
   ```bash
   git add "$MANIFEST"
   git commit -m "docs: coverage manifest — mark <issue-number> implemented"
   git push
   ```

If the diff between `Approved → Implemented` would not be picked up before merge (manifest lives
on the feature branch), commit it on the **base branch** post-merge instead:

```bash
git checkout "$BASE"
git pull --rebase
# edit manifest, then:
git add "$MANIFEST"
git commit -m "docs: coverage manifest — mark <issue-number> implemented"
git push
```

Choose whichever path keeps the manifest atomically updated with the code it documents.

### Step 6.5: Tick the parent epic checklist

If the closed issue has a parent epic, tick its checkbox in the epic body.

1. Find the parent epic and tick its checkbox:
   ```bash
   gh issue view <issue-number> --json body --jq '.body' | bash ${CLAUDE_PLUGIN_ROOT}/hooks/run-python.sh ${CLAUDE_PLUGIN_ROOT}/bin/check-epic-checkbox.py --issue <issue-number>
   ```

2. If no `## Parent epic` section exists (chore or standalone task), skip silently.

### Step 7: Report

Summarise what was done:
- PR merged (link)
- Issue closed
- Now on branch `<base-branch>`, up to date with remote
- Suggested next item: run `gh issue list --label kind:task --state open --limit 3` and print the results. This is the only additional query allowed here.


## Blocker policy

**Pause and report** if:

- No open PR exists for the current branch
- PR has not been approved / has requested changes
- Merge conflicts prevent merging
- Push fails

**Do NOT pause for:**

- Missing session log (create one)
- Minor uncommitted changes (commit them)
- Issue already closed by GitHub on merge (skip close step)
- Board item already moved to Done by GitHub on merge (skip board update)
- Local feature branch already deleted (skip `git branch -d`)
