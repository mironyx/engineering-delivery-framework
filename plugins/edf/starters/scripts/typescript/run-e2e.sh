#!/usr/bin/env bash
# Source .env.test.local so E2E runs see the same env vars teammates provision
# from the main repo (e.g. NEXT_PUBLIC_SUPABASE_URL). Without this, every
# teammate/agent rediscovered the missing-var error on its first E2E attempt.
# shellcheck disable=SC1091
[ -f ".env.test.local" ] && set -a && . ./.env.test.local && set +a
exec npx playwright test
