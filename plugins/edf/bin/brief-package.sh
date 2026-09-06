#!/usr/bin/env bash
# Write a per-issue implementation brief — the full issue body, the story's
# LLD context (Part A rationale + Part B implementation detail for every
# section the issue references), and the matching requirements section(s) —
# to a git-ignored file, and print only that file's path.
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
#   - Issue: the full issue body, verbatim, always — it is already scoped to
#     one task and typically 50-150 lines, so there is no token-efficiency
#     reason to trim it further, and trimming it (an earlier version of this
#     script extracted only "## Acceptance criteria") silently dropped
#     sibling sections a reader needs just as much: BDD specs, Files to
#     create/modify, Depends on, Design/HLD references.
#   - LLD: every LLD-<anchor> found in the issue's "## Design reference"
#     section (falling back to a whole-body search only if that section
#     can't be found) is treated as story-relevant. For each anchor, Part B
#     (the implementation detail the anchor is placed on) is extracted, and
#     — since a design-conforming LLD (ADR-0026) mirrors every Part B
#     section with a same-numbered Part A section carrying the human-
#     readable rationale for the *same* story — its Part A counterpart is
#     extracted too and placed first. A story's implementation detail read
#     without the "why" behind it (constraints, rejected alternatives, open
#     defects) is exactly the kind of thing a heading-scoped LLD extract can
#     silently be missing. Falls back to the full LLD file if no anchor can
#     be resolved at all.
#   - Requirements: resolved via every REQ- anchor found directly in the
#     issue body, unioned with whatever the coverage manifest next to --lld
#     maps each resolved LLD anchor to (matching the manifest's `lld:` field,
#     reading its `req:` field). Falls back to the full contents of every
#     --requirements file if no REQ- anchor can be resolved either way.
#
# A fallback always includes full content rather than omitting a source —
# this is a token-efficiency tool, not a scope reduction, so an agent reading
# the brief must see everything it would have seen reading the originals.
# Deliberately out of scope: the HLD and any ADRs the issue references. Those
# are large, project-wide documents in their own right — pulling them in
# would reopen the exact re-reading cost this script exists to close. An LLD
# section is expected to already carry whatever HLD/ADR context a story
# needs; an agent that still needs more can fetch those directly.
#
# Known limitation: section boundaries are heading-based (regex over `#`
# lines) and skip fenced code blocks, but cannot distinguish a genuine
# markdown heading from other `#`-prefixed text outside a fence. The Part A
# pairing relies on the ADR-0026 convention of matching section numbers
# ("## 2.3 Foo" in Part A, "## 2.3 Foo — Implementation" in Part B) — an LLD
# not following that convention just gets Part B alone, not an error.
#
# Output (stdout):
#   brief: <path to the brief file>
#   sections:
#     lld: <resolved:<anchor>[,<anchor>...]|none|fallback-full-file>
#     requirements: <resolved:<req-anchor>[,<req-anchor>...]|fallback-full-files:<n>|none>
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

TMP_ISSUE_BODY=$(mktemp)
TMP_PART_A=$(mktemp)
trap 'rm -f "$TMP_ISSUE_BODY" "$TMP_PART_A"' EXIT
printf '%s\n' "$ISSUE_BODY" > "$TMP_ISSUE_BODY"

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

# extract_part_a_region <file>
# Prints everything between a "# Part A" H1 heading and the next H1 heading
# (exclusive of both). Prints nothing (not an error) if the file has no
# "# Part A" heading — projects that predate, or don't use, the Part A/B
# convention just don't get a Part A pairing.
extract_part_a_region() {
  local file="$1"
  [[ -f "$file" ]] || return 0
  awk '
    /^# Part A/ { region = 1; next }
    region && /^# / { exit }
    region { print }
  ' "$file"
}

# extract_by_heading_number <file> <task-number, e.g. 2.3>
# Prints the section whose heading starts with the given task number
# (token-bounded, so "2.1" does not also match "2.10"), through the line
# before the next heading at or above that heading's level. Returns 1 if
# not found.
extract_by_heading_number() {
  local file="$1" tasknum="$2"
  [[ -f "$file" ]] || return 1
  # Plain string comparison (no dynamic regex) so a literal "." in tasknum
  # never needs escaping through a shell -> awk -v -> ERE round trip.
  awk -v tasknum="$tasknum" '
    BEGIN { state = 0; in_code = 0; matched = 0; tlen = length(tasknum) }
    {
      if ($0 ~ /^```/) { in_code = !in_code }
      if (state == 0) {
        if (!in_code && match($0, /^#{1,6}[ \t]/) > 0) {
          rest = substr($0, RLENGTH + 1)
          boundary_ok = (length(rest) == tlen) || (substr(rest, tlen + 1, 1) !~ /[0-9.]/)
          if (substr(rest, 1, tlen) == tasknum && boundary_ok) {
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

# task_number_of <section-text>
# Extracts the leading "N.M" task number from a section's first heading
# line (as produced by extract_by_anchor), or nothing if there isn't one.
task_number_of() {
  printf '%s\n' "$1" | grep -m1 -oE '^#{1,6}[ \t]+[0-9]+\.[0-9]+' | grep -oE '[0-9]+\.[0-9]+' || true
}

# --- LLD section(s) ---
LLD_STATUS="none"
LLD_TEXT=""
declare -a LLD_ANCHORS_RESOLVED=()
if [[ "$LLD_PATH" != "none" ]]; then
  # Resolve every "#LLD-..." anchor referenced in the issue's "## Design
  # reference" section (a task can legitimately touch more than one
  # section). Scope the search to that section first, so an unrelated
  # "#LLD-..." mention elsewhere in the issue body (e.g. a Concerns/Related
  # section) can't be picked up instead; fall back to a whole-body search
  # only if the section itself can't be found.
  declare -a LLD_ANCHOR_CANDIDATES=()
  DESIGN_REF_SECTION=$(extract_by_heading_text "$TMP_ISSUE_BODY" "design reference" || true)
  if [[ -n "$DESIGN_REF_SECTION" ]]; then
    mapfile -t LLD_ANCHOR_CANDIDATES < <(printf '%s\n' "$DESIGN_REF_SECTION" | grep -oE '#(LLD-[A-Za-z0-9._-]+)' | sed 's/^#//' | sort -u)
  fi
  if [[ "${#LLD_ANCHOR_CANDIDATES[@]}" -eq 0 ]]; then
    mapfile -t LLD_ANCHOR_CANDIDATES < <(printf '%s\n' "$ISSUE_BODY" | grep -oE '#(LLD-[A-Za-z0-9._-]+)' | sed 's/^#//' | sort -u)
  fi

  extract_part_a_region "$LLD_PATH" > "$TMP_PART_A"

  for ANCHOR in "${LLD_ANCHOR_CANDIDATES[@]}"; do
    [[ -z "$ANCHOR" ]] && continue
    if PART_B=$(extract_by_anchor "$LLD_PATH" "$ANCHOR"); then
      LLD_ANCHORS_RESOLVED+=("$ANCHOR")
      TASK_NUM=$(task_number_of "$PART_B")
      PART_A=""
      if [[ -n "$TASK_NUM" && -s "$TMP_PART_A" ]]; then
        PART_A=$(extract_by_heading_number "$TMP_PART_A" "$TASK_NUM" || true)
      fi
      LLD_TEXT+=$'\n\n---\n\n'"### ${ANCHOR}"$'\n'
      if [[ -n "$PART_A" ]]; then
        LLD_TEXT+=$'\n#### Part A — Design rationale (§'"${TASK_NUM}"$')\n\n'"$PART_A"$'\n'
      fi
      LLD_TEXT+=$'\n#### Part B — Implementation\n\n'"$PART_B"
    else
      echo "brief-package.sh: warning — LLD anchor not found, skipping: ${ANCHOR}" >&2
    fi
  done

  if [[ "${#LLD_ANCHORS_RESOLVED[@]}" -gt 0 ]]; then
    LLD_STATUS="resolved:$(IFS=,; echo "${LLD_ANCHORS_RESOLVED[*]}")"
  else
    LLD_STATUS="fallback-full-file"
    LLD_TEXT=$(cat "$LLD_PATH")
  fi
fi

# --- Requirements section(s) ---
REQ_STATUS="none"
REQ_TEXT=""
if [[ ${#REQ_PATHS[@]} -gt 0 ]]; then
  declare -a REQ_ANCHORS_WANTED=()

  # 1) Every REQ- anchor named directly in the issue body.
  mapfile -t DIRECT_REQ_ANCHORS < <(printf '%s\n' "$ISSUE_BODY" | grep -oE 'REQ-[A-Za-z0-9._-]+' | sort -u)
  REQ_ANCHORS_WANTED+=("${DIRECT_REQ_ANCHORS[@]:-}")

  # 2) Every REQ- anchor the coverage manifest next to --lld maps each
  #    resolved LLD anchor to (matching the manifest's `lld:` field).
  if [[ "$LLD_PATH" != "none" && "${#LLD_ANCHORS_RESOLVED[@]}" -gt 0 ]]; then
    LLD_DIR=$(dirname "$LLD_PATH")
    LLD_BASENAME=$(basename "$LLD_PATH")
    for MANIFEST in "$LLD_DIR"/coverage-*.yaml; do
      [[ -f "$MANIFEST" ]] || continue
      for ANCHOR in "${LLD_ANCHORS_RESOLVED[@]}"; do
        if grep -qF "lld: ${LLD_BASENAME}#${ANCHOR}" "$MANIFEST"; then
          # Each manifest entry starts with its own `- req:` line, followed
          # later by its `lld:` line — track the most recent `- req:` seen
          # so far and emit it once the matching `lld:` line is reached.
          FOUND_REQ=$(awk -v anchor="${LLD_BASENAME}#${ANCHOR}" '
            /^[ \t]*- req:/ { cur = $0; sub(/^[ \t]*- req:[ \t]*/, "", cur); current_req = cur }
            $0 ~ ("lld:[ \t]*" anchor) { print current_req; exit }
          ' "$MANIFEST")
          if [[ -n "$FOUND_REQ" ]]; then
            REQ_ANCHORS_WANTED+=("$FOUND_REQ")
          else
            echo "brief-package.sh: warning — manifest entry for ${ANCHOR} has no req: field before its lld: line, skipping" >&2
          fi
        fi
      done
    done
  fi

  mapfile -t REQ_ANCHORS_WANTED < <(printf '%s\n' "${REQ_ANCHORS_WANTED[@]:-}" | sed '/^$/d' | sort -u)

  declare -a REQ_ANCHORS_RESOLVED=()
  for ANCHOR in "${REQ_ANCHORS_WANTED[@]:-}"; do
    [[ -z "$ANCHOR" ]] && continue
    FOUND=0
    for RP in "${REQ_PATHS[@]}"; do
      if SECTION=$(extract_by_anchor "$RP" "$ANCHOR"); then
        REQ_TEXT+=$'\n\n---\n\n'"Source: ${RP}#${ANCHOR}"$'\n\n'"$SECTION"
        REQ_ANCHORS_RESOLVED+=("$ANCHOR")
        FOUND=1
        break
      fi
    done
    if [[ "$FOUND" -eq 0 ]]; then
      echo "brief-package.sh: warning — requirements anchor not found in any --requirements file, skipping: ${ANCHOR}" >&2
    fi
  done

  if [[ "${#REQ_ANCHORS_RESOLVED[@]}" -gt 0 ]]; then
    REQ_STATUS="resolved:$(IFS=,; echo "${REQ_ANCHORS_RESOLVED[*]}")"
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
  echo "## Issue"
  echo
  echo "$ISSUE_BODY"
  echo
  echo "## LLD context"
  echo
  if [[ "$LLD_STATUS" == "none" ]]; then
    echo "(no LLD for this issue)"
  else
    echo "Source: ${LLD_PATH}"
    echo "$LLD_TEXT"
  fi
  echo
  echo "## Requirements section(s)"
  echo
  if [[ "$REQ_STATUS" == "none" ]]; then
    echo "(no requirements paths provided)"
  else
    echo "$REQ_TEXT"
  fi
} > "$OUT"

echo "brief: $OUT"
echo "sections:"
echo "  lld: $LLD_STATUS"
echo "  requirements: $REQ_STATUS"
