#!/usr/bin/env bash
# Run vitest and emit a compact summary via the EDF summarizer.
# Usage: ${EDF_SCRIPTS}/run-tests.sh [test-file] [vitest-args...]
# Exit code matches vitest.
set -uo pipefail

# Derive plugin root from the script location. CLAUDE_PLUGIN_ROOT is only resolved
# by Claude Code in hooks.json and skill markdown — it is not exported into the
# Bash environment of tool-invoked commands, so the script cannot rely on it.
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PLUGIN_ROOT="$(cd "$SCRIPT_DIR/../../.." && pwd)"

tmpfile=$(mktemp)
trap 'rm -f "$tmpfile"' EXIT

npx vitest run "$@" > "$tmpfile" 2>&1
vitest_exit=$?

"${PLUGIN_ROOT}/hooks/run-python.sh" "${PLUGIN_ROOT}/bin/parse-vitest-output.py" < "$tmpfile"
exit $vitest_exit
