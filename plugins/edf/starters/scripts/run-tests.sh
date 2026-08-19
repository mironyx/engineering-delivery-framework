#!/usr/bin/env bash
# Universal test runner — dispatch to language-specific implementation.
# Usage: ${EDF_SCRIPTS}/run-tests.sh <ts|p|all> [test-file] [runner-args...]
set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

if [ $# -eq 0 ]; then
    echo "Usage: run-tests.sh <ts|p|all> [test-file] [args...]" >&2
    echo "  ts  — TypeScript (vitest)" >&2
    echo "  p   — Python (pytest)" >&2
    echo "  all — run both" >&2
    exit 2
fi

LANG="$1"; shift

case "$LANG" in
    ts) exec "$SCRIPT_DIR/typescript/run-tests.sh" "$@" ;;
    p)  exec "$SCRIPT_DIR/python/run-tests.sh" "$@" ;;
    all)
        echo "=== TypeScript tests ==="
        "$SCRIPT_DIR/typescript/run-tests.sh" "$@"; ts_rc=$?
        echo ""
        echo "=== Python tests ==="
        "$SCRIPT_DIR/python/run-tests.sh" "$@"; py_rc=$?
        if [ "$ts_rc" -ne 0 ] || [ "$py_rc" -ne 0 ]; then exit 1; fi
        exit 0
        ;;
    *)
        echo "Unknown language: $LANG. Use ts (TypeScript), p (Python), or all." >&2
        exit 1
        ;;
esac
