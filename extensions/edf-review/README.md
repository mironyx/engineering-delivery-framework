# EDF Review

Insert `[Review]` markers into markdown documents from a command-palette quick-pick.

## Install

1. Build the package: `npm install && npm run package`
2. Install the resulting `edf-review-<version>.vsix`:

   ```bash
   code --install-extension edf-review-<version>.vsix
   ```

3. Reload VS Code. The command `EDF: Insert Review Comment` appears in the
   command palette.

## Usage

Open a markdown document and its preview, focus the preview, then run
`EDF: Insert Review Comment` from the command palette and pick the section to
review.
