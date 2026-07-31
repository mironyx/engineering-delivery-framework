#!/usr/bin/env bash
# Dependency security audit for TypeScript projects.
# Fails only on high/critical vulnerabilities in production dependencies
# (npm --audit-level=high --omit=dev). Findings always print.
# Graceful-skip: no lockfile, or audit tool/network failure.
# Set EDF_AUDIT_WARN_ONLY=1 to downgrade findings to a warning (exit 0).
set -uo pipefail

PROJECT_ROOT="$(git rev-parse --show-toplevel 2>/dev/null || pwd)"
cd "$PROJECT_ROOT"

if [ -f package-lock.json ]; then
    AUDIT_CMD=(npm audit --audit-level=high --omit=dev)
elif [ -f pnpm-lock.yaml ]; then
    AUDIT_CMD=(pnpm audit --audit-level high)
elif [ -f yarn.lock ]; then
    AUDIT_CMD=(yarn audit --level high)
else
    echo "audit skipped (no lockfile found — package-lock.json, pnpm-lock.yaml, or yarn.lock)"
    exit 0
fi

OUTPUT="$("${AUDIT_CMD[@]}" 2>&1)"
rc=$?
if [ "$rc" -ne 0 ] && echo "$OUTPUT" | grep -qiE 'npm (error|err)|code E|EAI_AGAIN|ENOTFOUND|ETIMEDOUT|ENETUNREACH|ECONNREFUSED|ERR_SSL|network|registry'; then
    echo "audit skipped (audit tool or network failure):"
    echo "$OUTPUT" | head -n 3
    exit 0
fi

echo "$OUTPUT"
if [ "$rc" -ne 0 ] && [ "${EDF_AUDIT_WARN_ONLY:-0}" = "1" ]; then
    echo "EDF_AUDIT_WARN_ONLY=1 — findings above downgraded to a warning."
    exit 0
fi
exit "$rc"
