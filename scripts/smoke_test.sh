#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

cd "$PROJECT_DIR"

echo "[smoke] checking required files"
test -f README.md
test -f config/.env.example
test -f src/pancake_followup.py
test -f docs/sample-scan-output.json

echo "[smoke] python syntax check"
python3 -m py_compile src/pancake_followup.py

echo "[smoke] checking env example uses placeholders"
grep -q '^PANCAKE_PAGE_ID=YOUR_PAGE_ID$' config/.env.example
grep -q '^PANCAKE_PAGE_ACCESS_TOKEN=YOUR_PAGE_ACCESS_TOKEN$' config/.env.example
grep -q '^PANCAKE_PAGE_URL=https://pancake.vn/YOUR_PAGE_SLUG$' config/.env.example

echo "[smoke] checking data dir has no tracked runtime JSON"
if find data -maxdepth 1 -type f \( -name '*.json' -o -name '*.log' \) | grep -q .; then
  echo "runtime files detected in data/; clean them before publishing"
  exit 1
fi

echo "[smoke] PASS"
