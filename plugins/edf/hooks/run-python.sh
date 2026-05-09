#!/bin/bash
# Cross-platform Python wrapper.
# Tries py (Windows), python3 (Unix), python (fallback) in order.
# Skips the Windows Store stub (WindowsApps) which pops the Store instead of running.
# Passes all arguments to the first Python interpreter found.

if command -v py &>/dev/null; then
    py "$@"
elif command -v python3 &>/dev/null; then
    p=$(command -v python3)
    if [[ "$p" != */WindowsApps/* ]]; then
        python3 "$@"
    elif command -v python &>/dev/null; then
        p2=$(command -v python)
        [[ "$p2" != */WindowsApps/* ]] && python "$@" || { echo "ERROR: No Python interpreter found (tried py, python3, python — WindowsApps stubs skipped)" >&2; exit 1; }
    else
        echo "ERROR: No Python interpreter found (tried py, python3 — WindowsApps stub skipped)" >&2
        exit 1
    fi
elif command -v python &>/dev/null; then
    p=$(command -v python)
    if [[ "$p" != */WindowsApps/* ]]; then
        python "$@"
    else
        echo "ERROR: No Python interpreter found (tried py, python — WindowsApps stub skipped)" >&2
        exit 1
    fi
else
    echo "ERROR: No Python interpreter found (tried py, python3, python)" >&2
    exit 1
fi
