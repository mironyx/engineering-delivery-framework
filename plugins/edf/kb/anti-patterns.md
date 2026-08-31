# Anti-Patterns

Project-specific patterns that `/pr-review` must catch. The skill reads this whole file
verbatim and passes it to review agents as `{{ANTI_PATTERNS}}`. Edit each section to
reflect the patterns *your* project has learned to flag — drop sections you don't need,
add new ones as you discover them.

Each entry should state:
- the pattern (what to grep for / how to detect)
- the severity (`block` or `warn`)
- the fix (what to do instead)
- optionally a one-line rationale

## General

- **Fallback accretion — a decision chain whose fallback branches have no reachable triggering scenario.** A command or function resolves its target through N fallback branches, each added defensively ("just in case") rather than for an input state that actually occurs. Detected by: an `else`/fallback branch whose author cannot name the concrete state that reaches it, or answers "if it somehow happens". Fix: cut the branch and let the case fail loudly with a message — a wrong-target silent resolution is worse than a stop. Severity: **warn**.

<!-- e.g.
- **DRY violation — duplicate service/query logic.** A new loader, service, or helper
  implements data-fetching or business logic that already exists in another module.
  Detected by: a new file that queries the same table(s) as an existing file without
  importing from it.
  Fix: extract the shared logic into a dedicated module and import from both contexts.
  Severity: **warn** — two diverging code paths for the same data, maintenance burden.
-->

## Framework anti-patterns

One section per framework your project uses. Populate with the patterns you've learned
to catch in code review.

<!-- e.g.
### Supabase
- `SUPABASE_ANON_KEY` (or `supabaseAnonKey`) used in any server-side file (API routes,
  server actions, middleware, `*.server.ts`). The anon key is for client-side only;
  server-side must use `SUPABASE_SERVICE_ROLE_KEY`. Severity: **block** (security —
  anon key bypasses RLS on the server).
- `.from('table')` without `.select(...)` — returns all columns, exposes schema → **warn**.
- Multiple `.from()` write calls in one function with no transaction wrapping → **warn**.
  Fix: move multi-step writes into a PostgreSQL function called via `.rpc()`.

### Next.js
- `cookies()` / `headers()` called outside an async server component or route handler → **block**.
- `"use client"` on a file that imports server-only modules → **block**.
- `process.env.NEXT_PUBLIC_*` accessed in server-only code (leaks to client bundle) → **warn**.
- `getServerSideProps` in the App Router (wrong paradigm) → **warn**.

### VS Code (edf-review extension)
- Hard-coded `'\n'` inserted into a document whose EOL is CRLF → mixed line endings (VS Code
  flags "Mixed line endings"; noisy git diff). Severity: **warn**. Fix: insert `'\r\n'` when
  `editor.document.eol === vscode.EndOfLine.CRLF`. (Finding #73 on PR #73.)
- A positional heading line index captured before a modal UI (quick-pick) and re-used after it
  with no version guard → stale-target insert or an unhandled RangeError if the heading is
  deleted while the pick is open. Severity: **warn**. Fix: re-read the document after the pick
  and fail explicitly when the heading is gone. (Finding #73 on PR #73.)
-->

## Secrets / env

<!-- e.g.
- Any hardcoded secret, API key, or token string not referencing `process.env` → **block**.
- `process.env.SOMETHING` used without a null check or fallback in production code → **warn**.
-->

## Language conventions

Compliance checks specific to the language(s) you use.

<!-- e.g.
### TypeScript
- `as unknown as X` double cast — usually hides a type error → **warn**.
- Non-null assertion `!` on values that could genuinely be null → **warn**.
- `any` type in source files → **block** (per project CLAUDE.md).
-->

## Helper reuse

Reusable helpers are functions, types, or modules in your shared codebase that serve as
the single source of truth for a given operation. They are documented in `kb/architecture.md`
(API composition pattern section). "Helper reuse" means using those helpers instead of
re-implementing them inline.

List the inline patterns that must *delegate* to a reusable helper instead.
Each entry: inline pattern → reusable helper (with import path).

<!-- e.g.
- Inline `from('user_organisations')` membership query → use `readMembershipSnapshot`.
- `createClient()` called inside a service → inject via `ApiContext`.
- Hand-rolled `await request.json()` + `schema.safeParse` → use `validateBody`.
- Hand-rolled `try/catch` returning `Response.json` for errors → use `handleApiError`.
- Locally redefined shared types (`AuthUser`, etc.) → import from the canonical module.
-->

Leave this section empty if your project has no reusable helper catalogue — `/pr-review` skips
kernel-reuse checks when neither this section nor `kb/architecture.md` is populated.
