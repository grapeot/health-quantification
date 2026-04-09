#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

if [[ -f "${ROOT_DIR}/.venv/bin/activate" ]]; then
  source "${ROOT_DIR}/.venv/bin/activate"
elif [[ -f "${ROOT_DIR}/../.venv/bin/activate" ]]; then
  source "${ROOT_DIR}/../.venv/bin/activate"
fi

export PYTHONPATH="${ROOT_DIR}/src:${PYTHONPATH:-}"

HOST="${HEALTH_QUANT_SERVER_HOST:-0.0.0.0}"
PORT="${HEALTH_QUANT_SERVER_PORT:-7996}"

exec uvicorn health_quantification.server:app --host "${HOST}" --port "${PORT}"
