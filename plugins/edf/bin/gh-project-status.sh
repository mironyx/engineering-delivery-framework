#!/usr/bin/env bash
# Deprecated shim — delegates to tracker.py (ADR-0041). Removed by E3.3.
#
# Usage:
#   ./bin/gh-project-status.sh <issue-number> <status>
#   ./bin/gh-project-status.sh add <issue-number> [status]
#
# Status values: todo | blocked | "in progress" | done (case-insensitive)
# Configuration: .github/project.env in the repo root (REPO, PROJECT_NUMBER, PROJECT_ID,
# FIELD_ID, STATUS_TODO, STATUS_BLOCKED, STATUS_IN_PROGRESS, STATUS_DONE).
# The usage text stays here so $0 prints the path the caller used.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TRACKER=(bash "$SCRIPT_DIR/../hooks/run-python.sh" "$SCRIPT_DIR/tracker.py")

usage() {
  echo "Usage: $0 <issue-number> <status>"
  echo "       $0 add <issue-number> [status]"
  echo "       $0 remove <issue-number>"
  echo "Status: todo | blocked | \"in progress\" | done"
  exit 1
}

case "${1:-}" in
  add)
    if [[ $# -lt 2 ]]; then
      echo "Usage: $0 add <issue-number> [status]"
      exit 1
    fi
    exec "${TRACKER[@]}" status "$2" "${3:-todo}" --add-to-board
    ;;
  remove)
    usage
    ;;
  *)
    [[ $# -lt 2 ]] && usage
    exec "${TRACKER[@]}" status "$1" "$2"
    ;;
esac
