# EDF Review

A VS Code extension that inserts `[Review]` markers into markdown documents below the line
selected in the preview, and makes diagram `click` links in markdown previews navigate to
their source files.

## Install

A pre-built `.vsix` ships inside the EDF plugin package, so installing the plugin puts it in
the plugin cache:

```bash
code --install-extension ~/.claude/plugins/cache/mironyx/edf/<plugin-version>/artifacts/edf-review-0.2.12.vsix
```

(On Windows the path is `%USERPROFILE%\.claude\plugins\cache\mironyx\edf\<plugin-version>\artifacts\edf-review-0.2.12.vsix`.)

The artifact is also committed in the repo at `plugins/edf/artifacts/edf-review-0.2.12.vsix`.

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

Open a markdown document and its preview. Run `EDF: Insert Review Comment` from the command
palette: a `> **[Review]:** ` marker is inserted below the line being reviewed, the cursor
lands right after the marker, and the source editor is focused so you can type your note.

Two flows, discriminated by which editor holds focus:

- **Source editor focused (reliable):** the marker goes below the cursor line.
- **Preview focused (known defect):** the marker goes below the preview's top-visible line.
  A single preview click does **not** scroll the source editor to the clicked line in this
  build, so the marker can land at the end of the file. For reliable placement, click the
  line in the **source editor** first, then run the command. See ADR-0040.

Clicking a diagram `click` link inside a preview opens the linked source file beside the
preview (native VS Code preview handling + the workspace `markdown.preview.openMarkdownLinks`
/ `markdown.links.openLocation` settings).
