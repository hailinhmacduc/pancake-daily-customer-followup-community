#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
ENV_FILE="${PANCAKE_ENV_FILE:-$PROJECT_DIR/.env}"

if [ -f "$ENV_FILE" ]; then
  set -a
  # shellcheck disable=SC1090
  source "$ENV_FILE"
  set +a
fi

: "${PANCAKE_WORKSPACE_DIR:=$PROJECT_DIR}"
: "${PANCAKE_CHROMIUM_PROFILE:=$HOME/Library/Application Support/pancake-community-followup}"
: "${PANCAKE_CHROMIUM_CDP_PORT:=9239}"
: "${PANCAKE_CHROMIUM_CDP_URL:=http://127.0.0.1:${PANCAKE_CHROMIUM_CDP_PORT}}"
: "${PANCAKE_CHROMIUM_APP:=/Applications/Chromium.app}"
: "${PANCAKE_CHROMIUM_BIN:=$PANCAKE_CHROMIUM_APP/Contents/MacOS/Chromium}"
: "${PANCAKE_PYTHON_BIN:=python3}"
: "${PANCAKE_MAX_SEND_PER_RUN:=5}"
: "${PANCAKE_FOLLOWUP_RUNNER_LOG:=/tmp/pancake-followup-runner.log}"

mkdir -p "$(dirname "$PANCAKE_FOLLOWUP_RUNNER_LOG")" "$PANCAKE_CHROMIUM_PROFILE"
exec > >(tee -a "$PANCAKE_FOLLOWUP_RUNNER_LOG") 2>&1

echo "[$(date '+%Y-%m-%d %H:%M:%S')] runner_start"
echo "profile=$PANCAKE_CHROMIUM_PROFILE"
echo "cdp_port=$PANCAKE_CHROMIUM_CDP_PORT"
echo "cdp_url=$PANCAKE_CHROMIUM_CDP_URL"
echo "max_send=$PANCAKE_MAX_SEND_PER_RUN"

ensure_cdp() {
  if curl -fsS "$PANCAKE_CHROMIUM_CDP_URL/json/version" >/dev/null 2>&1; then
    echo "cdp_already_ready"
    return 0
  fi

  echo "cdp_not_ready_starting_chromium"
  pkill -f "$PANCAKE_CHROMIUM_PROFILE" >/dev/null 2>&1 || true
  sleep 1
  rm -f "$PANCAKE_CHROMIUM_PROFILE/SingletonLock" "$PANCAKE_CHROMIUM_PROFILE/SingletonCookie" "$PANCAKE_CHROMIUM_PROFILE/SingletonSocket" || true
  nohup "$PANCAKE_CHROMIUM_BIN" \
    --user-data-dir="$PANCAKE_CHROMIUM_PROFILE" \
    --remote-debugging-port="$PANCAKE_CHROMIUM_CDP_PORT" \
    --no-first-run \
    --no-default-browser-check \
    >/tmp/pancake-community-followup-chromium.log 2>&1 &

  for _ in $(seq 1 80); do
    if curl -fsS "$PANCAKE_CHROMIUM_CDP_URL/json/version" >/dev/null 2>&1; then
      echo "cdp_ready"
      return 0
    fi
    sleep 0.25
  done

  echo "cdp_boot_failed"
  tail -n 80 /tmp/pancake-community-followup-chromium.log || true
  return 1
}

ensure_cdp

export PANCAKE_WORKSPACE_DIR
export PANCAKE_CHROMIUM_PROFILE
export PANCAKE_CHROMIUM_CDP_PORT
export PANCAKE_CHROMIUM_CDP_URL
export PANCAKE_MAX_SEND_PER_RUN

echo "running_followup_script"
"$PANCAKE_PYTHON_BIN" "$PROJECT_DIR/src/pancake_followup.py" send
EXIT_CODE=$?
echo "runner_exit_code=$EXIT_CODE"
exit $EXIT_CODE
