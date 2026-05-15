#!/usr/bin/env bash
# Run pytest and emit a compact summary via the EDF summarizer.
# Usage: ${EDF_SCRIPTS}/run-tests.sh [test-file] [pytest-args...]
# Exit code matches pytest.
set -uo pipefail

# Derive plugin root from the script location. CLAUDE_PLUGIN_ROOT is only resolved
# by Claude Code in hooks.json and skill markdown — it is not exported into the
# Bash environment of tool-invoked commands, so the script cannot rely on it.
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PLUGIN_ROOT="$(cd "$SCRIPT_DIR/../../.." && pwd)"

tmpfile=$(mktemp)
trap 'rm -f "$tmpfile"' EXIT

uv run pytest "$@" > "$tmpfile" 2>&1
pytest_exit=$?

"${PLUGIN_ROOT}/hooks/run-python.sh" "${PLUGIN_ROOT}/bin/parse-pytest-output.py" < "$tmpfile"
exit $pytest_exit
