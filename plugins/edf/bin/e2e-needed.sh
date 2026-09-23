#!/usr/bin/env bash
# Decide whether feature-core Step 5 runs E2E, from the paths this branch changed.
# Usage: e2e-needed.sh [base-ref]   (default: origin's default branch, else main)
#
# Prints one line starting with "run" or "skip", always exit 0.
# Reads from kb/conventions.md:
#   e2e-dir            — no dir or empty dir → skip
#   e2e-trigger-paths  — comma-separated globs (e.g. `src/app/**`, `src/components/**`).
#                        Unset → run (conservative default). Set → run only when a
#                        changed file (committed, staged, unstaged or untracked) matches.
set -uo pipefail

ROOT="$(git rev-parse --show-toplevel)"
cd "$ROOT"

conv() {
    [ -f kb/conventions.md ] || return 0
    grep "^| *$1 *|" kb/conventions.md | head -n 1 \
        | sed -n "s/^| *$1 *| *\(.*\) *|$/\1/p" \
        | sed 's/<!--.*-->//g; s/`//g; s/^ *//; s/ *$//'
}

E2E_DIR="$(conv e2e-dir)"
if [ -z "$E2E_DIR" ] || [ -z "$(ls -A "$E2E_DIR" 2>/dev/null)" ]; then
    echo "skip — no E2E tests (e2e-dir unset or empty)"
    exit 0
fi

TRIGGERS="$(conv e2e-trigger-paths)"
if [ -z "$TRIGGERS" ]; then
    echo "run — e2e-trigger-paths not set in kb/conventions.md (conservative default)"
    exit 0
fi

BASE="${1:-}"
if [ -z "$BASE" ]; then
    BASE="$(git symbolic-ref -q --short refs/remotes/origin/HEAD 2>/dev/null || echo main)"
fi
MERGE_BASE="$(git merge-base HEAD "$BASE" 2>/dev/null || echo "$BASE")"

CHANGED="$( { git diff --name-only "$MERGE_BASE"; git ls-files --others --exclude-standard; } | sort -u)"

IFS=',' read -r -a GLOBS <<< "$TRIGGERS"
while IFS= read -r f; do
    [ -n "$f" ] || continue
    for g in "${GLOBS[@]}"; do
        g="$(echo "$g" | sed 's/^ *//; s/ *$//; s/\*\*/*/g')"
        [ -n "$g" ] || continue
        # shellcheck disable=SC2254  # unquoted on purpose: $g is a glob
        case "$f" in $g)
            echo "run — $f matches e2e-trigger-paths ($g)"
            exit 0 ;;
        esac
    done
done <<< "$CHANGED"

echo "skip — no changed path matches e2e-trigger-paths ($TRIGGERS)"
exit 0
