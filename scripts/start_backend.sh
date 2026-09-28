#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

if [[ -f "${ROOT_DIR}/.venv/bin/activate" ]]; then
  source "${ROOT_DIR}/.venv/bin/activate"
elif [[ -f "${ROOT_DIR}/../.venv/bin/activate" ]]; then
  source "${ROOT_DIR}/../.venv/bin/activate"
fi

export PYTHONPATH="${ROOT_DIR}/src:${PYTHONPATH:-}"

is_tailscale_ipv4() {
  local ip="$1"
  local o1 o2 o3 o4
  [[ "${ip}" =~ ^([0-9]{1,3})\.([0-9]{1,3})\.([0-9]{1,3})\.([0-9]{1,3})$ ]] || return 1
  o1="${BASH_REMATCH[1]}"
  o2="${BASH_REMATCH[2]}"
  o3="${BASH_REMATCH[3]}"
  o4="${BASH_REMATCH[4]}"
  if ((10#${o1} > 255 || 10#${o2} > 255 || 10#${o3} > 255 || 10#${o4} > 255)); then
    return 1
  fi
  if ((10#${o1} == 100 && 10#${o2} >= 64 && 10#${o2} <= 127)); then
    return 0
  fi
  return 1
}

first_tailscale_ipv4() {
  local ts_out line
  if ! ts_out="$(tailscale ip -4 2>/dev/null)"; then
    return 1
  fi
  while IFS= read -r line || [[ -n "${line}" ]]; do
    line="${line%$'\r'}"
    if is_tailscale_ipv4 "${line}"; then
      printf '%s' "${line}"
      return 0
    fi
  done <<< "${ts_out}"
  return 1
}

host_matches_tailscale_ipv4() {
  local want="$1"
  local ts_out line
  is_tailscale_ipv4 "${want}" || return 1
  if ! ts_out="$(tailscale ip -4 2>/dev/null)"; then
    return 1
  fi
  while IFS= read -r line || [[ -n "${line}" ]]; do
    line="${line%$'\r'}"
    if [[ "${line}" == "${want}" ]]; then
      return 0
    fi
  done <<< "${ts_out}"
  return 1
}

REQUESTED_HOST="${HEALTH_QUANT_SERVER_HOST-}"
PORT="${HEALTH_QUANT_SERVER_PORT:-7996}"

if [[ -z "${REQUESTED_HOST}" || "${REQUESTED_HOST}" == "0.0.0.0" ]]; then
  if ! HOST="$(first_tailscale_ipv4)"; then
    echo "health_quant_backend: refusing to start; Tailscale IPv4 unavailable" >&2
    exit 1
  fi
  if [[ -z "${HOST}" ]]; then
    echo "health_quant_backend: refusing to start; Tailscale IPv4 unavailable" >&2
    exit 1
  fi
elif [[ "${REQUESTED_HOST}" == "127.0.0.1" ]]; then
  HOST="127.0.0.1"
else
  if ! host_matches_tailscale_ipv4 "${REQUESTED_HOST}"; then
    echo "health_quant_backend: refusing to start; bind host must be 127.0.0.1 or this machine's Tailscale IPv4" >&2
    exit 1
  fi
  HOST="${REQUESTED_HOST}"
fi

UVICORN_BIN="${HEALTH_QUANT_UVICORN_BIN:-uvicorn}"
exec "${UVICORN_BIN}" health_quantification.server:app --host "${HOST}" --port "${PORT}"
