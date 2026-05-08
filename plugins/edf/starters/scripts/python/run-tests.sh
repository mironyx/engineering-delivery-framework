#!/usr/bin/env bash
# Run pytest and emit a compact summary via the EDF summarizer.
# Usage: ./scripts/run-tests.sh [test-file] [pytest-args...]
# Exit code matches pytest.
set -uo pipefail

tmpfile=$(mktemp)
trap 'rm -f "$tmpfile"' EXIT

uv run pytest "$@" > "$tmpfile" 2>&1
pytest_exit=$?

"${CLAUDE_PLUGIN_ROOT}/hooks/run-python.sh" "${CLAUDE_PLUGIN_ROOT}/bin/parse-pytest-output.py" < "$tmpfile"
exit $pytest_exit
