#!/usr/bin/env bash
# Universal dependency security audit — dispatch to language-specific implementation.
# Usage: ${EDF_SCRIPTS}/run-audit.sh <ts|p|all>
set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

if [ $# -eq 0 ]; then
    echo "Usage: run-audit.sh <ts|p|all>" >&2
    echo "  ts  — TypeScript (npm/pnpm/yarn audit)" >&2
    echo "  p   — Python (uv audit / pip-audit)" >&2
    echo "  all — run both" >&2
    exit 2
fi

LANG="$1"; shift

case "$LANG" in
    ts) exec "$SCRIPT_DIR/typescript/run-audit.sh" "$@" ;;
    p)  exec "$SCRIPT_DIR/python/run-audit.sh" "$@" ;;
    all)
        echo "=== TypeScript audit ==="
        "$SCRIPT_DIR/typescript/run-audit.sh" "$@"; ts_rc=$?
        echo ""
        echo "=== Python audit ==="
        "$SCRIPT_DIR/python/run-audit.sh" "$@"; py_rc=$?
        if [ "$ts_rc" -ne 0 ] || [ "$py_rc" -ne 0 ]; then exit 1; fi
        exit 0
        ;;
    *)
        echo "Unknown language: $LANG. Use ts (TypeScript), p (Python), or all." >&2
        exit 1
        ;;
esac
