#!/usr/bin/env bash
# E2E tests — replace with real command or leave as no-op
# shellcheck disable=SC1091
[ -f ".env.test.local" ] && set -a && . ./.env.test.local && set +a
exec true
