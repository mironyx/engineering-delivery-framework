#!/usr/bin/env bash
# Run the EDF plugin test suite.
#
# Usage:
#   ./tests/run-tests.sh           # Run all tests
#   ./tests/run-tests.sh -k parser # Run only parser tests
#   ./tests/run-tests.sh -v        # Run with verbose output
#
# Dependencies: pytest (install with: pip install pytest)
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Find Python (same logic as hooks/run-python.sh)
PYTHON=""
if command -v py &>/dev/null; then
  PYTHON="py"
elif command -v python3 &>/dev/null; then
  PYTHON="python3"
elif command -v python &>/dev/null; then
  PYTHON="python"
else
  echo "ERROR: No Python interpreter found"
  exit 1
fi

# Check pytest is available
if ! $PYTHON -m pytest --version &>/dev/null; then
  echo "ERROR: pytest not found. Install with: pip install pytest"
  exit 1
fi

echo "==> Running EDF test suite..."
$PYTHON -m pytest "$@" --tb=short
