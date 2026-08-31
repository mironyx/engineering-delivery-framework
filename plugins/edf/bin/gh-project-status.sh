#!/usr/bin/env bash
# Manage GitHub project board items.
#
# Usage:
#   ./bin/gh-project-status.sh <issue-number> <status>
#   ./bin/gh-project-status.sh add <issue-number> [status]
#   ./bin/gh-project-status.sh remove <issue-number>
#
# Commands:
#   <issue-number> <status>        — Update status of an existing board item
#   add <issue-number> [status]    — Add issue to board and optionally set status (default: todo)
#   remove <issue-number>          — Remove an issue from the board
#
# Status values: todo | blocked | "in progress" | done (case-insensitive)
#
# Configuration:
#   Reads from .github/project.env in the repo root. This file must define:
#     REPO=owner/name
#     PROJECT_NUMBER=N
#     PROJECT_ID=PVT_...
#     FIELD_ID=PVTSSF_...
#     STATUS_TODO=...
#     STATUS_BLOCKED=...
#     STATUS_IN_PROGRESS=...
#     STATUS_DONE=...
#
#   To set up a new repo:
#     1. Create the project board in GitHub
#     2. Run: gh project field-list <number> --owner <owner>
#     3. Copy the field ID and option IDs into .github/project.env

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# Resolve the user's project root from git, not the script location. When installed
# as a plugin the script lives under ~/.claude/plugins/..., so $SCRIPT_DIR/.. is the
# plugin directory, not the user's repo.
REPO_ROOT="$(git rev-parse --show-toplevel 2>/dev/null || true)"
if [[ -z "$REPO_ROOT" ]]; then
  echo "Error: not inside a git repository — run from your project directory" >&2
  exit 1
fi
CONFIG_FILE="$REPO_ROOT/.github/project.env"

# --- Load configuration ---
if [[ ! -f "$CONFIG_FILE" ]]; then
  echo "Error: config file not found: $CONFIG_FILE" >&2
  echo "Create it with REPO, PROJECT_NUMBER, PROJECT_ID, FIELD_ID, and STATUS_* values." >&2
  echo "See this script's header for the format." >&2
  exit 1
fi

# Source config (only allows simple KEY=VALUE lines)
while IFS='=' read -r key value; do
  # Strip whitespace first — also strips \r from CRLF line endings, so a CRLF
  # blank line reads as empty rather than as a key of "\r".
  key=$(echo "$key" | xargs)
  value=$(echo "$value" | xargs)
  # Skip comments and blank lines
  [[ "$key" =~ ^[[:space:]]*# ]] && continue
  [[ -z "$key" ]] && continue
  export "$key=$value"
done < "$CONFIG_FILE"

# Validate required config
for var in REPO PROJECT_NUMBER PROJECT_ID FIELD_ID STATUS_TODO STATUS_BLOCKED STATUS_IN_PROGRESS STATUS_DONE; do
  if [[ -z "${!var:-}" ]]; then
    echo "Error: $var not set in $CONFIG_FILE" >&2
    exit 1
  fi
done

OWNER="${REPO%%/*}"
REPO_NAME="${REPO#*/}"

declare -A STATUS_IDS=(
  [todo]="$STATUS_TODO"
  [blocked]="$STATUS_BLOCKED"
  [in progress]="$STATUS_IN_PROGRESS"
  [done]="$STATUS_DONE"
)

# Find a real Python, skipping the Windows Store stub in WindowsApps.
find_python() {
  for candidate in python3 python; do
    local p
    p=$(command -v "$candidate" 2>/dev/null) || continue
    [[ "$p" == */WindowsApps/* ]] && continue
    "$p" --version &>/dev/null && echo "$p" && return 0
  done
  return 1
}

PYTHON=$(find_python)
if [[ -z "$PYTHON" ]]; then
  echo "Error: python not found (tried python3 and python, skipped WindowsApps stubs)"
  exit 1
fi

# Resolve a status name to its option ID. Exits on invalid status.
resolve_status() {
  local status_name="$(echo "$1" | tr '[:upper:]' '[:lower:]')"
  local option_id="${STATUS_IDS[$status_name]:-}"
  if [[ -z "$option_id" ]]; then
    echo "Error: unknown status '$1'. Use: todo | blocked | \"in progress\" | done" >&2
    exit 1
  fi
  echo "$option_id"
}

# Set a board item's status field.
set_item_status() {
  local item_id="$1"
  local option_id="$2"
  gh project item-edit \
    --project-id "$PROJECT_ID" \
    --id "$item_id" \
    --field-id "$FIELD_ID" \
    --single-select-option-id "$option_id"
}

# Find the project item ID for an issue number already on the board.
find_item_id() {
  local issue_number="$1"
  gh api graphql -f query="
    query {
      repository(owner: \"${OWNER}\", name: \"${REPO_NAME}\") {
        issue(number: ${issue_number}) {
          projectItems(first: 10) {
            nodes {
              id
              project { id }
            }
          }
        }
      }
    }
  " | "$PYTHON" "$SCRIPT_DIR/parse-project-item-id.py" "$PROJECT_ID"
}

# --- Command: add ---
if [[ "${1:-}" == "add" ]]; then
  if [[ $# -lt 2 ]]; then
    echo "Usage: $0 add <issue-number> [status]"
    exit 1
  fi
  ISSUE_NUMBER="$2"
  STATUS="${3:-todo}"
  OPTION_ID=$(resolve_status "$STATUS")

  ITEM_ID=$(gh project item-add "$PROJECT_NUMBER" --owner "$OWNER" \
    --url "https://github.com/${REPO}/issues/${ISSUE_NUMBER}" \
    --format json | "$PYTHON" -c "import json,sys; print(json.load(sys.stdin)['id'])")

  if [[ -z "$ITEM_ID" ]]; then
    echo "Error: failed to add issue #$ISSUE_NUMBER to the project board"
    exit 1
  fi

  set_item_status "$ITEM_ID" "$OPTION_ID"
  echo "Issue #$ISSUE_NUMBER → added → $STATUS"
  exit 0
fi

# --- Command: remove ---
if [[ "${1:-}" == "remove" ]]; then
  if [[ $# -lt 2 ]]; then
    echo "Usage: $0 remove <issue-number>"
    exit 1
  fi
  ISSUE_NUMBER="$2"
  ITEM_ID=$(find_item_id "$ISSUE_NUMBER")

  if [[ -z "$ITEM_ID" ]]; then
    echo "Error: issue #$ISSUE_NUMBER not found on the project board"
    exit 1
  fi

  gh project item-delete "$PROJECT_NUMBER" --owner "$OWNER" --id "$ITEM_ID"
  echo "Issue #$ISSUE_NUMBER → removed"
  exit 0
fi

# --- Command: set status ---
if [[ $# -lt 2 ]]; then
  echo "Usage: $0 <issue-number> <status>"
  echo "       $0 add <issue-number> [status]"
  echo "       $0 remove <issue-number>"
  echo "Status: todo | blocked | \"in progress\" | done"
  exit 1
fi

ISSUE_NUMBER="$1"
OPTION_ID=$(resolve_status "$2")

ITEM_ID=$(find_item_id "$ISSUE_NUMBER")

if [[ -z "$ITEM_ID" ]]; then
  echo "Error: issue #$ISSUE_NUMBER not found on the project board"
  exit 1
fi

set_item_status "$ITEM_ID" "$OPTION_ID"
echo "Issue #$ISSUE_NUMBER → $2"
