#!/usr/bin/env bash
# Universal E2E runner — dispatch to language-specific implementation.
# Usage: ${EDF_SCRIPTS}/run-e2e.sh <ts|p|all>
set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

if [ $# -eq 0 ]; then
    echo "Usage: run-e2e.sh <ts|p|all>" >&2
    echo "  ts  — TypeScript (playwright test)" >&2
    echo "  p   — Python (no-op by default)" >&2
    echo "  all — run both" >&2
    exit 2
fi

LANG="$1"; shift

case "$LANG" in
    ts) exec "$SCRIPT_DIR/typescript/run-e2e.sh" "$@" ;;
    p)  exec "$SCRIPT_DIR/python/run-e2e.sh" "$@" ;;
    all)
        echo "=== TypeScript E2E ==="
        "$SCRIPT_DIR/typescript/run-e2e.sh" "$@"; ts_rc=$?
        echo ""
        echo "=== Python E2E ==="
        "$SCRIPT_DIR/python/run-e2e.sh" "$@"; py_rc=$?
        exit $(( ts_rc + py_rc ))
        ;;
    *)
        echo "Unknown language: $LANG. Use ts (TypeScript), p (Python), or all." >&2
        exit 1
        ;;
esac
