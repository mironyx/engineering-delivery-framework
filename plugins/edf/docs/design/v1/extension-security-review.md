# EDF Review — Extension Security Review (Task 4, issue #51)

**Review scope:** the shipped `edf-review-0.2.0.vsix` (the packaged artefact, not the `src/`
tree). The review covers **what ships** — the compiled `out/src/*.js` files inside the
`.vsix`, the packaged manifest, and the artefact's file listing. Grep evidence below is run
against `out/src/` (the exact files the `.vsix` carries) unless noted.

**Date:** 2026-08-24. **Artefact:** `extensions/edf-review/edf-review-0.2.0.vsix`
(9 files, 10.2 KB).

## Guaranteed properties

One row per property, with the evidence that established it — no bare assertions.

| Property | Evidence | Verdict |
|---|---|---|
| **No file reads beyond the open document** | `grep -rnE 'workspace\.fs\|readFile' extensions/edf-review/out/src/` → no hits (exit 1). The only text the extension reads is the open document's `TextDocument` content passed into the pure modules. | PASS |
| **No network calls** | `grep -rnE 'fetch\|https?\.\|axios' extensions/edf-review/out/src/` → no hits (exit 1). | PASS |
| **No process execution** | `grep -rnE 'child_process\|exec\|spawn' extensions/edf-review/out/src/` → no hits (exit 1). | PASS |
| **Preview script injection is scoped to the overlay only** | `jq '.contributes.markdown.previewScripts' package.json` → `["./media/overlay.js"]`; `media/overlay.js` read end to end — single-purpose diagram overlay, no other injected surface. | PASS |
| **Overlay script performs no file reads, network calls, or dynamic evaluation** | `grep -rnE 'readFile\|fetch\|XMLHttpRequest\|eval\(\|new Function\|import\(' extensions/edf-review/media/overlay.js` → no hits (exit 1). The overlay only reads SVG `href` attributes and sets overlay anchor `href`s; it never reads file content, calls the network, or evaluates a string. | PASS |
| **Overlay hrefs are containment-checked before use** | read `resolveAndValidateHref` — a resolved href outside `design-root` (e.g. a `../../../..` escape from a document in `plugins/edf/docs/design/v1/`) returns `null` and no overlay is created; fragments and in-root paths pass. | PASS |
| **Shipped artefact matches reviewed source** | The `.vsix` carries exactly the compiled `out/src/*.js` listed below; each file is byte-identical to the `out/` the 65-test Dev-Host suite ran against (`diff -r` clean) and to the installed extension at `~/.vscode/extensions/mironyx.edf-review-0.2.0/out/src/`. | PASS |

> **Amended by Task 5 (§2.5, issue #63).** Task 5 re-added `contributes.markdown.previewScripts`
> and `media/overlay.js`, so the pre-Task-5 "no preview script injection" property is **replaced**
> by the three preview-script properties above. The file listing and manifest contract below
> describe the `edf-review-0.2.0.vsix` as Task 4 shipped it — a re-packaged artefact after
> Task 5 carries the overlay surface (`media/overlay.js` and the compiled `out/src/overlay-bridge.js`).

## Shipped artefact file listing

`unzip -l edf-review-0.2.0.vsix` (the reviewed surface — everything a reviewer runs):

```text
  Length      Date    Time    Name
---------  ---------- -----   ----
     1761  2026-08-24 01:07   extension.vsixmanifest
      359  2026-08-24 01:07   [Content_Types].xml
      557  2026-08-24 01:07   extension/readme.md
     1014  2026-08-24 00:44   extension/package.json
     1568  2026-08-24 01:01   extension/out/src/review-insert.js
     2093  2026-08-24 01:01   extension/out/src/log.js
     1974  2026-08-24 01:01   extension/out/src/headings.js
     6248  2026-08-24 01:01   extension/out/src/extension.js
     7271  2026-08-24 01:01   extension/out/src/editor-tracker.js
---------                     -------
    22836                     9 files
```

**Absent from the artefact:** `media/` (no preview script), `src/` (TypeScript sources),
`test/` and `out/test/` (test sources and compiled tests), `*.map` sourcemaps,
`tsconfig.json`, `.vscodeignore`, `node_modules/`. **Present:** `out/src/` — the compiled
`main` entry point (`package.json` → `./out/src/extension.js`) and its four modules.

## Manifest contract (packaged `extension/package.json`)

- `publisher`: `mironyx`, `name`: `edf-review`, `version`: `0.2.0`
- `main`: `./out/src/extension.js`; `activationEvents`: `[]` (lazy activation via the
  auto-generated `onCommand:` from `contributes.commands`)
- `contributes`: exactly one command — `edf-review.insertReviewComment` (title
  "Insert Review Comment", category "EDF")
- **No marketplace-listing metadata:** `icon`, `galleryBanner`, `categories` all absent
  (equivalent of `jq -e '.icon // .galleryBanner // .categories'` failing)
- `engines.vscode`: `^1.88.0`

## Install verification (manual, recorded per LLD §2.4)

Performed 2026-08-24 against the shipped `edf-review-0.2.0.vsix`:

1. `code --install-extension edf-review-0.2.0.vsix --force` → exit 0, "successfully installed".
2. `code --list-extensions` → `mironyx.edf-review` listed; installed at
   `~/.vscode/extensions/mironyx.edf-review-0.2.0/` containing `out/`, `package.json`, `readme.md`.
3. **Parity with the Dev-Host build:** the installed `out/src/*.js` is byte-identical
   (`diff -r` clean) to the `out/src/` the 65-test `@vscode/test-electron` suite ran against.
   A launch test with `extensionDevelopmentPath` pointed at the **installed** (packaged)
   directory confirmed the shipped artefact activates in the host, registers
   `edf-review.insertReviewComment`, and ships the same `REVIEW_MARKER` / `findReviewInsertLine`
   / `extractHeadings` logic (3/3 parity specs pass).
4. The palette command `EDF: Insert Review Comment` appears via the declared contribution and
   resolves to the registered command; behaviour parity is covered by the Dev-Host suite (65
   passing) running the same byte-identical code.

**Outcome: PASS.** No packaging-only regression: the `.vsix` installs, activates, and behaves
identically to the Dev-Host build.
