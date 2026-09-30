#!/usr/bin/env bash
# Keep wrap-up docs off the feature branch: park them before the merge, land them on
# the base branch after it.
#
# Why: pushing a docs-only commit to the PR branch cancels the CI run in flight
# (concurrency) and, where docs/** is paths-ignored, starts no replacement — so the
# head that merges is not the head CI verified.
#
# Usage:
#   park-docs.sh park <issue>   # stash uncommitted docs/ and kb/ changes (incl. untracked)
#   park-docs.sh land <issue>   # on the up-to-date base branch: restore, commit all docs/ and kb/
#                               # changes (incl. post-merge manifest/kb edits), push
#
# The stash lives in the shared object store, so a stash parked in a /feature-team
# worktree can be landed from the main repo. Prints one line; exit 0 on success.
set -uo pipefail

MODE="${1:-}"
ISSUE="${2:-}"
if [[ -z "$MODE" || -z "$ISSUE" || ! "$ISSUE" =~ ^[0-9]+$ ]]; then
  echo "Usage: park-docs.sh <park|land> <issue-number>" >&2
  exit 2
fi
TAG="edf-docs-${ISSUE}"
PATHS=(docs kb)

find_stash() {
  git stash list --format='%gd %s' | awk -v tag="$TAG" '$0 ~ (": " tag "$") {print $1; exit}'
}

case "$MODE" in
  park)
    cd "$(git rev-parse --show-toplevel)" || exit 1
    existing=()
    for p in "${PATHS[@]}"; do [[ -e "$p" ]] && existing+=("$p"); done
    if [[ ${#existing[@]} -eq 0 ]] || [[ -z "$(git status --porcelain -- "${existing[@]}")" ]]; then
      echo "park: nothing to park (no uncommitted changes under docs/ or kb/)"
      exit 0
    fi
    n=$(git status --porcelain -- "${existing[@]}" | wc -l | tr -d ' ')
    if ! git stash push --include-untracked -m "$TAG" -- "${existing[@]}" >/dev/null; then
      echo "park: FAILED — git stash push" >&2
      exit 1
    fi
    echo "park: parked $n path(s) as $TAG"
    ;;
  land)
    cd "$(git rev-parse --show-toplevel)" || exit 1
    ref="$(find_stash)"
    if [[ -z "$ref" ]]; then
      echo "land: nothing parked for #$ISSUE ($TAG not found)"
      exit 0
    fi
    if ! git stash pop "$ref" >/dev/null; then
      echo "land: FAILED — stash $TAG did not apply cleanly; resolve the conflict, then commit docs by hand" >&2
      exit 1
    fi
    # Also picks up docs/kb edits made on the base branch after the merge (coverage manifest, kb/).
    for p in "${PATHS[@]}"; do [[ -e "$p" ]] && git add -A -- "$p"; done
    if git diff --cached --quiet; then
      echo "land: restored $TAG but nothing differs from $(git branch --show-current) — no commit"
      exit 0
    fi
    git commit -q -m "docs: session log and LLD sync #${ISSUE}" || { echo "land: FAILED — commit" >&2; exit 1; }
    # One retry after a rebase: parallel teammates land on the same base branch.
    if ! git push -q 2>/dev/null && ! { git pull --rebase -q 2>/dev/null && git push -q 2>/dev/null; }; then
      echo "land: committed $(git rev-parse --short HEAD) but push was rejected (protected branch?) — push it via a docs PR" >&2
      exit 1
    fi
    echo "land: committed and pushed $(git rev-parse --short HEAD) on $(git branch --show-current)"
    ;;
  *)
    echo "Usage: park-docs.sh <park|land> <issue-number>" >&2
    exit 2
    ;;
esac
