#!/usr/bin/env bash
# Universal typecheck — dispatch to language-specific implementation.
# Usage: ${EDF_SCRIPTS}/run-typecheck.sh <ts|p|all>
set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

if [ $# -eq 0 ]; then
    echo "Usage: run-typecheck.sh <ts|p|all>" >&2
    echo "  ts  — TypeScript (tsc --noEmit)" >&2
    echo "  p   — Python (pyright)" >&2
    echo "  all — run both" >&2
    exit 2
fi

LANG="$1"; shift

case "$LANG" in
    ts) exec "$SCRIPT_DIR/typescript/run-typecheck.sh" "$@" ;;
    p)  exec "$SCRIPT_DIR/python/run-typecheck.sh" "$@" ;;
    all)
        echo "=== TypeScript typecheck ==="
        "$SCRIPT_DIR/typescript/run-typecheck.sh" "$@"; ts_rc=$?
        echo ""
        echo "=== Python typecheck ==="
        "$SCRIPT_DIR/python/run-typecheck.sh" "$@"; py_rc=$?
        if [ "$ts_rc" -ne 0 ] || [ "$py_rc" -ne 0 ]; then exit 1; fi
        exit 0
        ;;
    *)
        echo "Unknown language: $LANG. Use ts (TypeScript), p (Python), or all." >&2
        exit 1
        ;;
esac
