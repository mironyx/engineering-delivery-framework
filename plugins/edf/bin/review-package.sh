#!/usr/bin/env bash
# Write a code-review package (diffstat + full diff with wide context) to a
# git-ignored file, and print only that file's path plus a per-file numstat.
#
# The diff never reaches stdout. The caller passes the printed path to its
# review agents, which read the package themselves — so a large diff stays
# out of the calling session's context and out of every agent prompt.
#
# Usage:
#   ${CLAUDE_PLUGIN_ROOT}/bin/review-package.sh --pr <number> [--out <file>]
#   ${CLAUDE_PLUGIN_ROOT}/bin/review-package.sh --local [--out <file>]
#
# Output (stdout):
#   package: <path to the package file>
#   numstat:
#   <added>	<removed>	<path>     (one row per changed file)
#
# Exit codes: 0 ok, 1 usage/environment error, 3 nothing to review.
set -euo pipefail

# Diff context width. Wide enough that a reviewer can judge a hunk without
# opening the changed file — the whole point of handing over one package.
CONTEXT=10

usage() {
  cat >&2 <<'EOF'
usage: review-package.sh --pr <number> [--out <file>]
       review-package.sh --local [--out <file>]
EOF
}

# --- Parse arguments ---
MODE=""
PR=""
OUT=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --pr)
      if [[ $# -lt 2 ]]; then usage; exit 1; fi
      MODE="pr"; PR="$2"; shift 2 ;;
    --local)
      MODE="local"; shift ;;
    --out)
      if [[ $# -lt 2 ]]; then usage; exit 1; fi
      OUT="$2"; shift 2 ;;
    -h|--help)
      usage; exit 0 ;;
    *)
      echo "Unknown option: $1" >&2; usage; exit 1 ;;
  esac
done

if [[ -z "$MODE" ]]; then
  usage
  exit 1
fi

if [[ "$MODE" == "pr" && ! "$PR" =~ ^[0-9]+$ ]]; then
  echo "--pr expects a number, got: $PR" >&2
  exit 1
fi

if ! REPO_ROOT=$(git rev-parse --show-toplevel 2>/dev/null); then
  echo "review-package.sh: not inside a git repository" >&2
  exit 1
fi

TMP_PATCH=$(mktemp)
trap 'rm -f "$TMP_PATCH"' EXIT

# --- Collect the diff ---
if [[ "$MODE" == "pr" ]]; then
  if ! PR_META=$(gh pr view "$PR" --json headRefOid,baseRefName \
                   -q '.headRefOid + " " + .baseRefName' 2>/dev/null); then
    echo "review-package.sh: cannot read PR #${PR} (is gh authenticated?)" >&2
    exit 1
  fi
  HEAD_OID="${PR_META%% *}"
  BASE_REF="${PR_META##* }"
  LABEL="PR #${PR}"

  # Prefer local git: it gives -U${CONTEXT}, which `gh pr diff` cannot. The refs
  # are present in the common case (review right after push). Fall back to gh
  # for a PR whose branch was never fetched here.
  if git rev-parse --verify --quiet "${HEAD_OID}^{commit}" >/dev/null 2>&1 \
     && MERGE_BASE=$(git merge-base "origin/${BASE_REF}" "$HEAD_OID" 2>/dev/null); then
    git diff "-U${CONTEXT}" "${MERGE_BASE}..${HEAD_OID}" > "$TMP_PATCH"
    SOURCE="git -U${CONTEXT} ${MERGE_BASE:0:7}..${HEAD_OID:0:7}"
  else
    gh pr diff "$PR" > "$TMP_PATCH"
    SOURCE="gh pr diff (3-line context — PR refs not available locally)"
  fi
else
  LABEL="local working tree"
  git diff "-U${CONTEXT}" HEAD > "$TMP_PATCH"
  SOURCE="git -U${CONTEXT} HEAD"
  if [[ ! -s "$TMP_PATCH" ]]; then
    git diff "-U${CONTEXT}" --cached > "$TMP_PATCH"
    SOURCE="git -U${CONTEXT} --cached"
  fi
fi

if [[ ! -s "$TMP_PATCH" ]]; then
  echo "review-package.sh: nothing to review — diff is empty" >&2
  exit 3
fi

# `git apply` in report mode reads the patch without touching the tree, so the
# same call works for both the git and the gh path.
STAT=$(git apply --stat "$TMP_PATCH" 2>/dev/null || true)
NUMSTAT=$(git apply --numstat "$TMP_PATCH" 2>/dev/null || true)

# --- Resolve the output path ---
if [[ -z "$OUT" ]]; then
  PKG_DIR="$REPO_ROOT/.edf/review"
  mkdir -p "$PKG_DIR"
  # Self-ignoring scratch directory: keeps packages out of `git status` without
  # modifying the project's tracked .gitignore.
  printf '*\n' > "$REPO_ROOT/.edf/.gitignore"
  if [[ "$MODE" == "pr" ]]; then
    # Named per head commit, so a re-review after pushing fixes gets a fresh file.
    OUT="$PKG_DIR/review-pr${PR}-${HEAD_OID:0:7}.diff"
  else
    OUT="$PKG_DIR/review-local-$(date -u +%Y%m%dT%H%M%SZ).diff"
  fi
fi

{
  echo "# Review package — ${LABEL}"
  echo "# Source: ${SOURCE}"
  echo
  echo "## Files changed"
  if [[ -n "$STAT" ]]; then echo "$STAT"; else echo "(diffstat unavailable)"; fi
  echo
  echo "## Diff"
  cat "$TMP_PATCH"
} > "$OUT"

echo "package: $OUT"
echo "numstat:"
if [[ -n "$NUMSTAT" ]]; then
  echo "$NUMSTAT"
else
  echo "(unavailable — compute with git diff --numstat)"
fi
