#!/usr/bin/env bash
# Deprecated shim — delegates to tracker.py (ADR-0041). Removed by E3.3.
#
# Usage: ./bin/gh-create-issue.sh --title T --body MD [--labels a,b] [--type task|epic]
#        [--parent REF] [--add-to-board] [--board-status S] [--dry-run]
# Output: "created:<number>" | "exists:<number>"; errors on stderr, exit non-zero.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
exec bash "$SCRIPT_DIR/../hooks/run-python.sh" "$SCRIPT_DIR/tracker.py" create "$@"
