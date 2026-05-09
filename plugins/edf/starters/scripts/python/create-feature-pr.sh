#!/usr/bin/env bash
# Create a feature PR with cost tracking and session ID embedding.
#
# Usage:
#   ${EDF_SCRIPTS}/create-feature-pr.sh \
#     --issue <number> \
#     --title "<short title>" \
#     --summary "<1-3 bullet points>" \
#     --design-ref "<path to design doc section>" \
#     --tests-added <N> \
#     --tests-total "<N (M test files)>"
#
# Output:
#   Prints the PR URL on success, exits non-zero on error.
set -euo pipefail

# --- Parse arguments ---
ISSUE=""
TITLE=""
SUMMARY=""
DESIGN_REF=""
TESTS_ADDED=""
TESTS_TOTAL=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --issue)       ISSUE="$2";       shift 2 ;;
    --title)       TITLE="$2";       shift 2 ;;
    --summary)     SUMMARY="$2";     shift 2 ;;
    --design-ref)  DESIGN_REF="$2";  shift 2 ;;
    --tests-added) TESTS_ADDED="$2"; shift 2 ;;
    --tests-total) TESTS_TOTAL="$2"; shift 2 ;;
    *) echo "Unknown option: $1" >&2; exit 1 ;;
  esac
done

# --- Validate required arguments ---
for var in ISSUE TITLE SUMMARY TESTS_ADDED TESTS_TOTAL; do
  if [[ -z "${!var}" ]]; then
    echo "Missing required argument: --$(echo "$var" | tr '[:upper:]' '[:lower:]' | tr '_' '-')" >&2
    exit 1
  fi
done

DESIGN_REF="${DESIGN_REF:-N/A}"

# --- Derive feature ID ---
FEATURE_PREFIX="${EDF_FEATURE_PREFIX:-}"
if [[ -z "$FEATURE_PREFIX" ]]; then
  REPO=$(gh repo view --json name -q '.name' 2>/dev/null || basename "$(git rev-parse --show-toplevel)")
  FEATURE_PREFIX=$(echo "$REPO" | tr '[:lower:]' '[:upper:]' | tr '-' '_' | tr -c '[:upper:][:digit:]_' ' ' | awk '{for(i=1;i<=NF;i++) printf substr($i,1,1); print ""}')
fi
FEATURE_ID="${FEATURE_PREFIX}-${ISSUE}"

# --- Create PR with placeholder Usage section ---
PR_BODY="$(cat <<EOF
## Summary
${SUMMARY}

## Issue
Closes #${ISSUE}

## Design reference
${DESIGN_REF}

## Test plan
- [ ] All tests pass
- [ ] Type check clean
- [ ] Lint clean

## Verification
- **Tests added:** ${TESTS_ADDED}
- **Total tests:** ${TESTS_TOTAL}

## Usage
- **Cost:** TBD
- **Tokens:** TBD
- **Time to PR:** TBD

<!-- claude-session-id: TBD -->
EOF
)"

PR_URL=$(gh pr create --title "$TITLE" --base main --body "$PR_BODY")
PR_NUMBER=$(echo "$PR_URL" | grep -o '[0-9]*$')

# --- Cost tracking (best-effort) ---
COST_OUTPUT=$("${CLAUDE_PLUGIN_ROOT}/hooks/run-python.sh" "${CLAUDE_PLUGIN_ROOT}/bin/query-feature-cost.py" \
  "$FEATURE_ID" --issue "$ISSUE" --pr "$PR_NUMBER" --stage pr 2>/dev/null) || true

COST_LINE=$(echo "$COST_OUTPUT" | grep '^\- \*\*Cost:' || echo "- **Cost:** unavailable")
TOKEN_LINE=$(echo "$COST_OUTPUT" | grep '^\- \*\*Tokens:' || echo "- **Tokens:** unavailable")
TIME_LINE=$(echo "$COST_OUTPUT" | grep '^\- \*\*Time to PR:' || echo "- **Time to PR:** unavailable")

# --- Resolve session ID (best-effort) ---
SESSION_ID=$("${CLAUDE_PLUGIN_ROOT}/hooks/run-python.sh" "${CLAUDE_PLUGIN_ROOT}/bin/get-session-id.py" 2>/dev/null) || SESSION_ID="unknown"

# --- Patch the PR body with actual cost figures ---
CURRENT_BODY=$(gh pr view "$PR_NUMBER" --json body -q '.body')
UPDATED_BODY=$(echo "$CURRENT_BODY" | "${CLAUDE_PLUGIN_ROOT}/hooks/run-python.sh" -c "
import sys
cost_line = '''$COST_LINE'''
token_line = '''$TOKEN_LINE'''
time_line = '''$TIME_LINE'''
session_id = '''$SESSION_ID'''
body = sys.stdin.read()
body = body.replace('- **Cost:** TBD', cost_line)
body = body.replace('- **Tokens:** TBD', token_line)
body = body.replace('- **Time to PR:** TBD', time_line)
body = body.replace('<!-- claude-session-id: TBD -->', f'<!-- claude-session-id: {session_id} -->')
print(body, end='')
")

gh api "repos/{owner}/{repo}/pulls/$PR_NUMBER" --method PATCH -f body="$UPDATED_BODY" > /dev/null

echo "$PR_URL"
