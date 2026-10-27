#!/usr/bin/env bash
# Shared helpers for the scripts. Source it; do not run it.
# shellcheck shell=bash

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
export ROOT

if [ -f "${ROOT}/.env" ]; then
  set -a
  # shellcheck source=/dev/null
  source "${ROOT}/.env"
  set +a
fi
CONTROLLER_PORT="${CONTROLLER_PORT:-18481}"
GIT_PORT="${GIT_PORT:-18480}"
SINK_PORT="${SINK_PORT:-18482}"
CONTROLLER_URL="http://127.0.0.1:${CONTROLLER_PORT}"
export CONTROLLER_PORT GIT_PORT SINK_PORT CONTROLLER_URL

log() { printf '[%s] %s\n' "$(date +%H:%M:%S)" "$*" >&2; }
die() { log "error: $*"; exit 1; }

require() {
  local tool
  for tool in "$@"; do
    command -v "${tool}" >/dev/null 2>&1 || die "${tool} is not installed (see the prerequisites in README.md)"
  done
}

# wait_for <description> <timeout-seconds> <command...>: poll once a second until the command succeeds.
wait_for() {
  local description="$1" timeout="$2" waited=0
  shift 2
  until "$@" >/dev/null 2>&1; do
    if [ "${waited}" -ge "${timeout}" ]; then
      die "timed out after ${timeout}s waiting for ${description}"
    fi
    sleep 1
    waited=$((waited + 1))
  done
  log "${description}: ok (${waited}s)"
}
