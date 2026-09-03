#!/usr/bin/env bash
# Universal format check — dispatch to language-specific implementation.
# Usage: ${EDF_SCRIPTS}/run-format-check.sh <ts|p|all>
set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

if [ $# -eq 0 ]; then
    echo "Usage: run-format-check.sh <ts|p|all>" >&2
    echo "  ts  — TypeScript (no-op by default)" >&2
    echo "  p   — Python (ruff format --check)" >&2
    echo "  all — run both" >&2
    exit 2
fi

LANG="$1"; shift

case "$LANG" in
    ts) exec bash "$SCRIPT_DIR/typescript/run-format-check.sh" "$@" ;;
    p)  exec bash "$SCRIPT_DIR/python/run-format-check.sh" "$@" ;;
    all)
        echo "=== TypeScript format check ==="
        bash "$SCRIPT_DIR/typescript/run-format-check.sh" "$@"; ts_rc=$?
        echo ""
        echo "=== Python format check ==="
        bash "$SCRIPT_DIR/python/run-format-check.sh" "$@"; py_rc=$?
        if [ "$ts_rc" -ne 0 ] || [ "$py_rc" -ne 0 ]; then exit 1; fi
        exit 0
        ;;
    *)
        echo "Unknown language: $LANG. Use ts (TypeScript), p (Python), or all." >&2
        exit 1
        ;;
esac
