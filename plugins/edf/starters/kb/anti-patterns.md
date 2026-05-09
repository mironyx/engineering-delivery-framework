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

## Kernel reuse

If your project maintains a kb doc (canonical reusable helpers, e.g.
`kb/architecture.md`), list the inline patterns that must *delegate* to a canonical
helper instead. Each entry: inline pattern → kb symbol that should be used.

<!-- e.g.
- Inline `from('user_organisations')` membership query → use `readMembershipSnapshot`.
- `createClient()` called inside a service → inject via `ApiContext`.
- Hand-rolled `await request.json()` + `schema.safeParse` → use `validateBody`.
- Hand-rolled `try/catch` returning `Response.json` for errors → use `handleApiError`.
- Locally redefined canonical types (`AuthUser`, etc.) → import from canonical module.
-->

Leave this section empty if your project has no kb doc — `/pr-review` skips
kernel-reuse checks when neither this section nor `kb/architecture.md` is populated.
