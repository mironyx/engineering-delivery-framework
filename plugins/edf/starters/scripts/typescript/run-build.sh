#!/usr/bin/env bash
# Source .env.test.local so the build sees the same env vars E2E runs get
# (e.g. NEXT_PUBLIC_SUPABASE_URL) — frameworks that inline NEXT_PUBLIC_*-style
# vars at build time fail without this, and every teammate/agent rediscovered
# the missing-var error on its first build attempt.
# shellcheck disable=SC1091
[ -f ".env.test.local" ] && set -a && . ./.env.test.local && set +a
exec npm run build
