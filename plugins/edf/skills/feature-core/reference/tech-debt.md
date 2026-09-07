# Managing Technical Debt

Reference for the `TODO` comment convention used by feature-core. Linked from the
Top-Level Skill File and from other skills that need the same convention.

## Managing technical debt

**Rule: if you knowingly leave something unfixed, leave a visible marker.**

When you defer a fix, skip a refactor, accept a rough edge, or hit a limitation that prevents
a full resolution — **leave a `TODO` comment in the code**. Tech debt that lives only in PR
comments or session logs is invisible to the next developer who reads the file. A `grep TODO`
in the source tree should surface everything that was intentionally deferred.

Each TODO must:
1. **Reference the issue or PR number** for traceability (e.g. `#42` or `PR #128`)
2. **Describe what should be done** and why it was deferred
3. **Be on its own line** so `grep -rn "TODO" src/` catches it without extra context

Pattern:
```
// TODO(#123): Refactor this cache once the shared invalidation layer lands (PR #456).
// Deferred — the fix here is correct but duplicated; consolidation is tracked separately.
```

Prefer `TODO` over `FIXME`, `HACK`, or `NOTE` — it is the single convention every editor
highlights and every grep finds. Keep them in source files (not test files, not config) so
they sit where the next developer will actually see them.

**When to leave a TODO (non-exhaustive):**
- A PR review finding was deferred (Step 9 non-blocking suggestion)
- A diagnostic finding was intentionally not fixed (Step 6 false positive or out-of-scope)
- A design deviation created a known gap that the LLD expects but was cut for scope
- A dependency or util doesn't exist yet and a stub was written instead
- A refactor opportunity was noted but is too large for the current PR

**Do NOT leave TODOs for:** things you plan to fix in the same PR, obvious typos, or
temporary debugging code (remove that before committing).