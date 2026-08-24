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
| **No preview script injection** | `contributes` declares only `commands` (verified: `Object.keys(contributes) === ['commands']`); `media/` is absent from the extension tree and from the `.vsix` file listing. | PASS |
| **Shipped artefact matches reviewed source** | The `.vsix` carries exactly the compiled `out/src/*.js` listed below; each file is byte-identical to the `out/` the 65-test Dev-Host suite ran against (`diff -r` clean) and to the installed extension at `~/.vscode/extensions/mironyx.edf-review-0.2.0/out/src/`. | PASS |

> **Amended by Task 5 (§2.5, issue #63).** The "No preview script injection" property holds at
> the point Task 4 runs (Task 5 has not landed in execution order). Task 5 re-adds
> `contributes.markdown.previewScripts` and a `media/overlay.js`, so it **replaces this row** and
> adds the three preview-script properties it introduces. A reader after Task 5 should not find a
> "no injection" claim next to a `media/overlay.js` in the same tree.

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
