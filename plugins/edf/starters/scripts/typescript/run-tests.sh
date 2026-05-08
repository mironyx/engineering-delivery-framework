#!/usr/bin/env bash
# Run vitest and emit a compact summary via the EDF summarizer.
# Usage: ./scripts/run-tests.sh [test-file] [vitest-args...]
# Exit code matches vitest.
set -uo pipefail

tmpfile=$(mktemp)
trap 'rm -f "$tmpfile"' EXIT

npx vitest run "$@" > "$tmpfile" 2>&1
vitest_exit=$?

"${CLAUDE_PLUGIN_ROOT}/hooks/run-python.sh" "${CLAUDE_PLUGIN_ROOT}/bin/parse-vitest-output.py" < "$tmpfile"
exit $vitest_exit
