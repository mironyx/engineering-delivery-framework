#!/usr/bin/env bash
# Build the EDF Review VS Code extension (.vsix) from source.
# Usage: bash build-vsix.sh
set -euo pipefail
cd "$(dirname "$0")"

npm ci
npm run compile
npm run package

VSIX=$(ls edf-review-*.vsix | head -1)
echo "Built: $PWD/$VSIX"
echo "Install with: code --install-extension \"$PWD/$VSIX\""
