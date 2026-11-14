#!/usr/bin/env bash
set -euo pipefail

base_url="${OPSPILOT_URL:-http://127.0.0.1:8000}"

for endpoint in healthz readyz; do
  curl --fail --silent --show-error "${base_url}/${endpoint}" >/dev/null
  printf '%s: OK\n' "$endpoint"
done
