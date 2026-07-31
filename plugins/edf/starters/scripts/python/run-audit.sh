#!/usr/bin/env bash
# Dependency security audit for Python projects.
# Blocks on known vulnerabilities in declared dependencies. pip-audit has no
# severity-threshold flag, so any finding blocks unless EDF_AUDIT_WARN_ONLY=1.
# Graceful-skip: no audit tool, no manifest, or audit tool/network failure.
set -uo pipefail

PROJECT_ROOT="$(git rev-parse --show-toplevel 2>/dev/null || pwd)"
cd "$PROJECT_ROOT"

if [ -f uv.lock ] && command -v uv >/dev/null 2>&1; then
    AUDIT_CMD=(uv audit)
elif command -v pip-audit >/dev/null 2>&1; then
    if compgen -G "requirements*.txt" >/dev/null; then
        AUDIT_CMD=(pip-audit -r requirements.txt)
    elif [ -f pyproject.toml ]; then
        AUDIT_CMD=(pip-audit)
    else
        echo "audit skipped (no requirements*.txt or pyproject.toml to audit)"
        exit 0
    fi
else
    echo "audit skipped (neither uv nor pip-audit installed — install pip-audit or use uv to enable the dependency gate)"
    exit 0
fi

OUTPUT="$("${AUDIT_CMD[@]}" 2>&1)"
rc=$?
if [ "$rc" -ne 0 ] && echo "$OUTPUT" | grep -qiE 'ConnectionError|connection reset|Network error|failed to (resolve|fetch)|InsecureRequestWarning|too many requests'; then
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
