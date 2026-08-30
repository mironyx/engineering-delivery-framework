#!/usr/bin/env bash
# Build the EDF Review VS Code extension (.vsix) from source.
# Usage: bash build-vsix.sh
set -euo pipefail
cd "$(dirname "$0")"

npm ci
npm run compile
npm run package

# Version-sort so a stale older .vsix in the dir never shadows the new build.
VSIX=$(ls edf-review-*.vsix | sort -V | tail -1)
# Ship a copy inside the plugin package so plugin installs carry the artifact
# into the plugin cache (~/.claude/plugins/cache/mironyx/edf/<version>/artifacts/).
mkdir -p ../../plugins/edf/artifacts
cp "$VSIX" ../../plugins/edf/artifacts/
echo "Built: $PWD/$VSIX"
echo "Shipped to plugin package: $PWD/../../plugins/edf/artifacts/$VSIX"
echo "Install with: code --install-extension \"$PWD/$VSIX\""
