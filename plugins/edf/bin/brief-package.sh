#!/usr/bin/env bash
# Write a per-issue implementation brief — acceptance criteria, the single
# relevant LLD section, and the single relevant requirements section — to a
# git-ignored file, and print only that file's path.
#
# Mirrors review-package.sh's pattern: large project documents (a 1000+ line
# requirements doc, a multi-section LLD) get read once here and handed to
# test-author/feature-evaluator/pr-review agents as a path, instead of each
# agent re-reading the full documents independently.
#
# Usage:
#   ${CLAUDE_PLUGIN_ROOT}/bin/brief-package.sh --issue <number> \
#     --lld <path-or-"none"> \
#     --requirements <path> [--requirements <path> ...] \
#     [--out <file>]
#
# Section extraction:
#   - Acceptance criteria: the issue body's "## Acceptance criteria" section
#     (case-insensitive heading match). Falls back to the full issue body if
#     no such heading is found.
#   - LLD section: the anchor is read from the "#LLD-..." fragment of the
#     issue's "## Design reference" link, then that section is extracted
#     from --lld (from the anchor to the next heading at or above its
#     level). Falls back to the full LLD file if no anchor can be resolved.
#   - Requirements section: resolved via a REQ- anchor found directly in the
#     issue body, or failing that via the coverage manifest next to --lld
#     (matching its `lld:` field to the resolved LLD anchor, reading its
#     `req:` field). Falls back to the full contents of every --requirements
#     file if no REQ- anchor can be resolved either way.
#
# A fallback always includes full content rather than omitting a source —
# this is a token-efficiency tool, not a scope reduction, so an agent reading
# the brief must see everything it would have seen reading the originals.
#
# Known limitation: section boundaries are heading-based (regex over `#`
# lines) and skip fenced code blocks, but cannot distinguish a genuine
# markdown heading from other `#`-prefixed text outside a fence.
#
# Output (stdout):
#   brief: <path to the brief file>
#   sections:
#     acceptance-criteria: <resolved|fallback-full-issue-body>
#     lld: <resolved:<anchor>|none|fallback-full-file>
#     requirements: <resolved:<req-anchor>|fallback-full-files:<n>|none>
#
# Exit codes: 0 ok, 1 usage/environment error.
set -euo pipefail

usage() {
  cat >&2 <<'EOF'
usage: brief-package.sh --issue <number> --lld <path|none> \
         --requirements <path> [--requirements <path> ...] [--out <file>]
EOF
}

# --- Parse arguments ---
ISSUE=""
LLD_PATH=""
REQ_PATHS=()
OUT=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --issue)
      if [[ $# -lt 2 ]]; then usage; exit 1; fi
      ISSUE="$2"; shift 2 ;;
    --lld)
      if [[ $# -lt 2 ]]; then usage; exit 1; fi
      LLD_PATH="$2"; shift 2 ;;
    --requirements)
      if [[ $# -lt 2 ]]; then usage; exit 1; fi
      REQ_PATHS+=("$2"); shift 2 ;;
    --out)
      if [[ $# -lt 2 ]]; then usage; exit 1; fi
      OUT="$2"; shift 2 ;;
    -h|--help)
      usage; exit 0 ;;
    *)
      echo "Unknown option: $1" >&2; usage; exit 1 ;;
  esac
done

if [[ -z "$ISSUE" || -z "$LLD_PATH" ]]; then
  usage
  exit 1
fi

if [[ ! "$ISSUE" =~ ^[0-9]+$ ]]; then
  echo "--issue expects a number, got: $ISSUE" >&2
  exit 1
fi

if ! REPO_ROOT=$(git rev-parse --show-toplevel 2>/dev/null); then
  echo "brief-package.sh: not inside a git repository" >&2
  exit 1
fi

if ! ISSUE_TITLE=$(gh issue view "$ISSUE" --json title -q '.title' 2>/dev/null); then
  echo "brief-package.sh: cannot read issue #${ISSUE} (is gh authenticated?)" >&2
  exit 1
fi
if ! ISSUE_BODY=$(gh issue view "$ISSUE" --json body -q '.body' 2>/dev/null); then
  echo "brief-package.sh: cannot read issue #${ISSUE} body (is gh authenticated?)" >&2
  exit 1
fi

# --- Section extraction helpers ---

# extract_by_anchor <file> <anchor-id>
# Prints the section starting at the line containing id="<anchor-id>" through
# the line before the next heading at or above the level of the first
# heading found after the anchor. Returns 1 if the anchor is not found.
extract_by_anchor() {
  local file="$1" anchor="$2"
  [[ -f "$file" ]] || return 1
  grep -qF "id=\"${anchor}\"" "$file" || return 1
  awk -v target="id=\"${anchor}\"" '
    BEGIN { state = 0; in_code = 0 }
    {
      if ($0 ~ /^```/) { in_code = !in_code }
      if (state == 0) {
        if (index($0, target) > 0) { state = 1; print; next }
        next
      }
      if (state == 1) {
        if (!in_code && match($0, /^#{1,6}[ \t]/) > 0) {
          level = RLENGTH - 1
          state = 2
        }
        print
        next
      }
      # A subsequent stable-ID anchor (ADR-0026) always marks the start of the
      # next section, even before its heading line appears — stop here too,
      # not only on a heading of equal-or-shallower level.
      if (!in_code && $0 ~ /^<a id="/) { exit }
      if (!in_code && match($0, /^#{1,6}[ \t]/) > 0) {
        this_level = RLENGTH - 1
        if (this_level <= level) { exit }
      }
      print
    }
  ' "$file"
}

# extract_by_heading_text <file> <lowercase-substring-to-match-in-heading>
# Prints the section starting at the first heading line whose lowercased
# text contains the given substring, through the line before the next
# heading at or above that heading's level. Returns 1 if not found.
extract_by_heading_text() {
  local file="$1" needle="$2"
  [[ -f "$file" ]] || return 1
  awk -v needle="$needle" '
    BEGIN { state = 0; in_code = 0; matched = 0 }
    {
      if ($0 ~ /^```/) { in_code = !in_code }
      if (state == 0) {
        if (!in_code && match($0, /^#{1,6}[ \t]/) > 0) {
          line_lower = tolower($0)
          if (index(line_lower, needle) > 0) {
            level = RLENGTH - 1
            state = 1
            matched = 1
            next
          }
        }
        next
      }
      if (!in_code && $0 ~ /^<a id="/) { exit }
      if (!in_code && match($0, /^#{1,6}[ \t]/) > 0) {
        this_level = RLENGTH - 1
        if (this_level <= level) { exit }
      }
      print
    }
    END { if (!matched) exit 1 }
  ' "$file"
}

# --- Acceptance criteria ---
AC_STATUS="fallback-full-issue-body"
AC_TEXT=""
TMP_ISSUE_BODY=$(mktemp)
printf '%s\n' "$ISSUE_BODY" > "$TMP_ISSUE_BODY"
if AC_TEXT=$(extract_by_heading_text "$TMP_ISSUE_BODY" "acceptance criteria"); then
  AC_STATUS="resolved"
else
  AC_TEXT="$ISSUE_BODY"
fi

# --- LLD section ---
LLD_STATUS="none"
LLD_TEXT=""
LLD_ANCHOR=""
if [[ "$LLD_PATH" != "none" ]]; then
  # Resolve the anchor from the issue body's "## Design reference" link,
  # e.g. [lld-foo.md §2.1](docs/design/v1/lld-foo.md#LLD-foo-bar). Scope the
  # search to that section first, so an unrelated "#LLD-..." mention
  # elsewhere in the issue body (e.g. a Concerns/Related section) can't be
  # picked up instead; fall back to a whole-body search if the section
  # itself can't be found.
  DESIGN_REF_SECTION=$(extract_by_heading_text "$TMP_ISSUE_BODY" "design reference" || true)
  if [[ -n "$DESIGN_REF_SECTION" ]]; then
    LLD_ANCHOR=$(printf '%s\n' "$DESIGN_REF_SECTION" | grep -oE '#(LLD-[A-Za-z0-9._-]+)' | head -1 | sed 's/^#//' || true)
  fi
  if [[ -z "$LLD_ANCHOR" ]]; then
    LLD_ANCHOR=$(printf '%s\n' "$ISSUE_BODY" | grep -oE '#(LLD-[A-Za-z0-9._-]+)' | head -1 | sed 's/^#//' || true)
  fi
  if [[ -n "$LLD_ANCHOR" ]] && LLD_TEXT=$(extract_by_anchor "$LLD_PATH" "$LLD_ANCHOR"); then
    LLD_STATUS="resolved:${LLD_ANCHOR}"
  else
    LLD_STATUS="fallback-full-file"
    LLD_TEXT=$(cat "$LLD_PATH")
    LLD_ANCHOR=""
  fi
fi

# --- Requirements section ---
REQ_STATUS="none"
REQ_TEXT=""
if [[ ${#REQ_PATHS[@]} -gt 0 ]]; then
  # 1) A REQ- anchor named directly in the issue body.
  REQ_ANCHOR=$(printf '%s\n' "$ISSUE_BODY" | grep -oE 'REQ-[A-Za-z0-9._-]+' | head -1 || true)

  # 2) Failing that, resolve via the coverage manifest next to --lld: match
  #    its `lld:` field against the LLD anchor resolved above, read `req:`.
  if [[ -z "$REQ_ANCHOR" && "$LLD_PATH" != "none" && -n "$LLD_ANCHOR" ]]; then
    LLD_DIR=$(dirname "$LLD_PATH")
    LLD_BASENAME=$(basename "$LLD_PATH")
    for MANIFEST in "$LLD_DIR"/coverage-*.yaml; do
      [[ -f "$MANIFEST" ]] || continue
      if grep -qF "lld: ${LLD_BASENAME}#${LLD_ANCHOR}" "$MANIFEST"; then
        # Each manifest entry starts with its own `- req:` line, followed later
        # by its `lld:` line — track the most recent `- req:` seen so far and
        # emit it once the matching `lld:` line for this entry is reached.
        REQ_ANCHOR=$(awk -v anchor="${LLD_BASENAME}#${LLD_ANCHOR}" '
          /^[ \t]*- req:/ { cur = $0; sub(/^[ \t]*- req:[ \t]*/, "", cur); current_req = cur }
          $0 ~ ("lld:[ \t]*" anchor) { print current_req; exit }
        ' "$MANIFEST")
        [[ -n "$REQ_ANCHOR" ]] && break
      fi
    done
  fi

  RESOLVED=0
  if [[ -n "${REQ_ANCHOR:-}" ]]; then
    for RP in "${REQ_PATHS[@]}"; do
      if SECTION=$(extract_by_anchor "$RP" "$REQ_ANCHOR"); then
        REQ_TEXT+=$'\n\n---\n\n'"Source: ${RP}"$'\n\n'"$SECTION"
        RESOLVED=1
      fi
    done
  fi

  if [[ "$RESOLVED" -eq 1 ]]; then
    REQ_STATUS="resolved:${REQ_ANCHOR}"
  else
    INCLUDED=0
    for RP in "${REQ_PATHS[@]}"; do
      if [[ -f "$RP" ]]; then
        REQ_TEXT+=$'\n\n---\n\n'"Source: ${RP}"$'\n\n'"$(cat "$RP")"
        INCLUDED=$((INCLUDED + 1))
      else
        echo "brief-package.sh: warning — requirements path not found, skipping: ${RP}" >&2
      fi
    done
    REQ_STATUS="fallback-full-files:${INCLUDED}"
  fi
fi

rm -f "$TMP_ISSUE_BODY"

# --- Resolve the output path ---
if [[ -z "$OUT" ]]; then
  PKG_DIR="$REPO_ROOT/.edf"
  mkdir -p "$PKG_DIR"
  # Self-ignoring scratch directory: keeps briefs (and review packages) out
  # of `git status` without modifying the project's tracked .gitignore.
  printf '*\n' > "$PKG_DIR/.gitignore"
  OUT="$PKG_DIR/brief-${ISSUE}.md"
fi

{
  echo "# Brief — Issue #${ISSUE}: ${ISSUE_TITLE}"
  echo
  echo "## Acceptance criteria"
  echo
  echo "$AC_TEXT"
  echo
  echo "## LLD section"
  echo
  if [[ "$LLD_STATUS" == "none" ]]; then
    echo "(no LLD for this issue)"
  else
    echo "Source: ${LLD_PATH}${LLD_ANCHOR:+#$LLD_ANCHOR}"
    echo
    echo "$LLD_TEXT"
  fi
  echo
  echo "## Requirements section"
  echo
  if [[ "$REQ_STATUS" == "none" ]]; then
    echo "(no requirements paths provided)"
  else
    echo "$REQ_TEXT"
  fi
} > "$OUT"

echo "brief: $OUT"
echo "sections:"
echo "  acceptance-criteria: $AC_STATUS"
echo "  lld: $LLD_STATUS"
echo "  requirements: $REQ_STATUS"
