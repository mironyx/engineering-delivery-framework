# EDF Review

A VS Code extension that inserts `[Review]` markers into markdown documents from a
command-palette quick-pick, and makes diagram `click` links in markdown previews navigate
to their source files.

## Install

A pre-built `.vsix` ships inside the EDF plugin package, so installing the plugin puts it in
the plugin cache:

```bash
code --install-extension ~/.claude/plugins/cache/mironyx/edf/<plugin-version>/artifacts/edf-review-0.2.2.vsix
```

(On Windows the path is `%USERPROFILE%\.claude\plugins\cache\mironyx\edf\<plugin-version>\artifacts\edf-review-0.2.2.vsix`.)

The artifact is also committed in the repo at `plugins/edf/artifacts/edf-review-0.2.2.vsix`.

Reload VS Code. `EDF: Insert Review Comment` appears in the command palette, and diagram
links in markdown previews become clickable.

## Build from source

```bash
bash extensions/edf-review/build-vsix.sh
```

This runs `npm ci`, compiles, and packages `edf-review-<version>.vsix`. Bump the `version`
field in `package.json` before rebuilding so the new artifact is distinguishable from the
shipped one, then commit the replacement.

## Usage

Open a markdown document and its preview, focus the preview, then run
`EDF: Insert Review Comment` from the command palette and pick the section to review.
Clicking a diagram `click` link inside a preview opens the linked source file.
