#!/usr/bin/env bash
# Universal markdown linter — same command for both languages.
# Usage: ${EDF_SCRIPTS}/run-markdown-lint.sh <ts|p|all>
# The language parameter is accepted for consistency but ignored internally.
set -uo pipefail

exec npx markdownlint-cli2 "**/*.md"
