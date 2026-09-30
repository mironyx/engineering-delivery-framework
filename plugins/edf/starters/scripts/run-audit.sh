#!/usr/bin/env bash
# Universal dependency security audit — dispatch to language-specific implementation.
# Usage: ${EDF_SCRIPTS}/run-audit.sh <ts|p|all> [--baseline [base-ref]]
#
# --baseline: when the audit fails but no dependency manifest or lockfile changed
# since the merge-base with base-ref (default: origin's default branch, else main),
# the findings predate this branch. Print a one-line PRE-EXISTING verdict and exit 0,
# so feature work is not blocked by — and does not re-investigate — the existing tree.
set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

if [ $# -eq 0 ]; then
    echo "Usage: run-audit.sh <ts|p|all> [--baseline [base-ref]]" >&2
    echo "  ts  — TypeScript (npm/pnpm/yarn audit)" >&2
    echo "  p   — Python (uv audit / pip-audit)" >&2
    echo "  all — run both" >&2
    exit 2
fi

LANG="$1"; shift

BASELINE=0
BASE=""
if [ "${1:-}" = "--baseline" ]; then
    BASELINE=1
    BASE="${2:-}"
fi

run_lang() {
    case "$1" in
        ts) bash "$SCRIPT_DIR/typescript/run-audit.sh" ;;
        p)  bash "$SCRIPT_DIR/python/run-audit.sh" ;;
        all)
            echo "=== TypeScript audit ==="
            bash "$SCRIPT_DIR/typescript/run-audit.sh"; ts_rc=$?
            echo ""
            echo "=== Python audit ==="
            bash "$SCRIPT_DIR/python/run-audit.sh"; py_rc=$?
            if [ "$ts_rc" -ne 0 ] || [ "$py_rc" -ne 0 ]; then return 1; fi
            return 0
            ;;
        *)
            echo "Unknown language: $1. Use ts (TypeScript), p (Python), or all." >&2
            return 1
            ;;
    esac
}

changed_dependency_files() {
    local base="$1" merge_base
    if [ -z "$base" ]; then
        base="$(git symbolic-ref -q --short refs/remotes/origin/HEAD 2>/dev/null || echo main)"
    fi
    merge_base="$(git merge-base HEAD "$base" 2>/dev/null || echo "$base")"
    { git diff --name-only "$merge_base" 2>/dev/null; git ls-files --others --exclude-standard; } \
        | sort -u \
        | grep -E '(^|/)(package\.json|package-lock\.json|pnpm-lock\.yaml|yarn\.lock|pyproject\.toml|uv\.lock|poetry\.lock|requirements[^/]*\.txt)$'
}

if [ "$BASELINE" -eq 0 ]; then
    run_lang "$LANG"
    exit $?
fi

OUTPUT="$(run_lang "$LANG" 2>&1)"
rc=$?
if [ "$rc" -eq 0 ]; then
    echo "$OUTPUT"
    exit 0
fi

DEP_CHANGES="$(changed_dependency_files "$BASE")"
if [ -n "$DEP_CHANGES" ]; then
    echo "$OUTPUT"
    echo "audit: FAIL — dependency files changed on this branch: $(echo "$DEP_CHANGES" | tr '\n' ' ')"
    exit "$rc"
fi

SUMMARY="$(echo "$OUTPUT" | grep -iE '[0-9]+ ([a-z]+ severity |known )?vulnerabilit' | head -n 2 | tr '\n' ' ')"
echo "audit: PRE-EXISTING — ${SUMMARY:-findings reported} — no dependency file changed on this branch; not introduced by this change, not blocking."
exit 0
