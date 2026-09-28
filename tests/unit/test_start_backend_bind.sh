#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
SCRIPT="${ROOT_DIR}/scripts/start_backend.sh"
TMP_DIR="$(mktemp -d "${TMPDIR:-/tmp}/hq-bind.XXXXXX")"
trap 'rm -rf "${TMP_DIR}"' EXIT

MOCK_BIN="${TMP_DIR}/bin"
ARGS_FILE="${TMP_DIR}/uvicorn.args"
TOUCH_FILE="${TMP_DIR}/tailscale.called"
STDOUT_FILE="${TMP_DIR}/stdout"
STDERR_FILE="${TMP_DIR}/stderr"
mkdir -p "${MOCK_BIN}"

cat > "${MOCK_BIN}/tailscale" << 'EOF'
#!/usr/bin/env bash
set -euo pipefail
if [[ "${1:-}" != "ip" || "${2:-}" != "-4" ]]; then
  exit 2
fi
if [[ -n "${MOCK_TAILSCALE_TOUCH:-}" ]]; then
  : > "${MOCK_TAILSCALE_TOUCH}"
fi
if [[ -n "${MOCK_TAILSCALE_STATUS:-}" ]]; then
  printf '%s' "${MOCK_TAILSCALE_STDOUT-}"
  exit "${MOCK_TAILSCALE_STATUS}"
fi
printf '%s' "${MOCK_TAILSCALE_STDOUT-}"
exit 0
EOF

cat > "${MOCK_BIN}/uvicorn" << 'EOF'
#!/usr/bin/env bash
set -euo pipefail
printf '%s\n' "$@" > "${MOCK_UVICORN_ARGS:?}"
exit 0
EOF
chmod 755 "${MOCK_BIN}/tailscale" "${MOCK_BIN}/uvicorn"

fail() {
  echo "FAIL: $1" >&2
  if [[ -s "${STDERR_FILE}" ]]; then
    echo "stderr:" >&2
    cat "${STDERR_FILE}" >&2
  fi
  exit 1
}

assert_no_address_leak() {
  local label="$1"
  shift
  local forbidden
  for forbidden in "$@"; do
    if [[ -n "${forbidden}" ]] && grep -F -q -- "${forbidden}" "${STDOUT_FILE}" "${STDERR_FILE}"; then
      fail "${label} leaked a bind address"
    fi
  done
}

run_script() {
  local rc=0
  : > "${STDOUT_FILE}"
  : > "${STDERR_FILE}"
  rm -f "${ARGS_FILE}" "${TOUCH_FILE}"
  set +e
  env \
    -u HEALTH_QUANT_SERVER_HOST \
    PATH="${MOCK_BIN}:/usr/bin:/bin" \
    HEALTH_QUANT_UVICORN_BIN="${MOCK_BIN}/uvicorn" \
    MOCK_UVICORN_ARGS="${ARGS_FILE}" \
    MOCK_TAILSCALE_TOUCH="${TOUCH_FILE}" \
    "$@" \
    "${SCRIPT}" > "${STDOUT_FILE}" 2> "${STDERR_FILE}"
  rc=$?
  set -e
  printf '%s' "${rc}"
}

assert_bound() {
  local label="$1"
  local host="$2"
  local port="$3"
  local rc
  shift 3
  rc="$(run_script "$@")"
  [[ "${rc}" == "0" ]] || fail "${label} exit ${rc}"
  [[ -f "${ARGS_FILE}" ]] || fail "${label} did not exec uvicorn"
  local got_host got_port
  got_host="$(awk 'NR==3 { print; exit }' "${ARGS_FILE}")"
  got_port="$(awk 'NR==5 { print; exit }' "${ARGS_FILE}")"
  [[ "${got_host}" == "${host}" ]] || fail "${label} host mismatch"
  [[ "${got_port}" == "${port}" ]] || fail "${label} port mismatch"
  [[ "$(awk 'NR==1 { print; exit }' "${ARGS_FILE}")" == "health_quantification.server:app" ]] || fail "${label} app mismatch"
  [[ "$(awk 'NR==2 { print; exit }' "${ARGS_FILE}")" == "--host" ]] || fail "${label} missing --host"
  [[ "$(awk 'NR==4 { print; exit }' "${ARGS_FILE}")" == "--port" ]] || fail "${label} missing --port"
  if grep -F -q -- "0.0.0.0" "${ARGS_FILE}"; then
    fail "${label} still requested all interfaces"
  fi
  assert_no_address_leak "${label}" "${host}" "${TAIL_A}" "${TAIL_B}" "192.168.1.50" "100.64.9.9" "8.8.8.8"
}

assert_refused() {
  local label="$1"
  local rc
  shift
  rc="$(run_script "$@")"
  [[ "${rc}" != "0" ]] || fail "${label} should fail closed"
  [[ ! -f "${ARGS_FILE}" ]] || fail "${label} started uvicorn"
  assert_no_address_leak "${label}" "${TAIL_A}" "${TAIL_B}" "192.168.1.50" "100.64.9.9" "8.8.8.8" "::1"
}

TAIL_A="100.64.1.2"
TAIL_B="100.65.3.4"

assert_bound "unset maps to tailscale" "${TAIL_A}" "7996" \
  MOCK_TAILSCALE_STDOUT="${TAIL_A}"$'\n'
[[ -f "${TOUCH_FILE}" ]] || fail "unset should query tailscale"

assert_bound "empty maps to tailscale" "${TAIL_A}" "7996" \
  HEALTH_QUANT_SERVER_HOST="" \
  MOCK_TAILSCALE_STDOUT="${TAIL_A}"$'\n'

assert_bound "explicit wildcard maps to tailscale" "${TAIL_A}" "7996" \
  HEALTH_QUANT_SERVER_HOST="0.0.0.0" \
  MOCK_TAILSCALE_STDOUT="${TAIL_A}"$'\n'

assert_bound "wildcard uses first tailscale ipv4" "${TAIL_A}" "7996" \
  HEALTH_QUANT_SERVER_HOST="0.0.0.0" \
  MOCK_TAILSCALE_STDOUT=$'not-an-address\n'"${TAIL_A}"$'\n'"${TAIL_B}"$'\n'

assert_bound "explicit tailscale ipv4 allowed" "${TAIL_B}" "7996" \
  HEALTH_QUANT_SERVER_HOST="${TAIL_B}" \
  MOCK_TAILSCALE_STDOUT="${TAIL_A}"$'\n'"${TAIL_B}"$'\n'

assert_bound "loopback skips tailscale" "127.0.0.1" "7996" \
  HEALTH_QUANT_SERVER_HOST="127.0.0.1" \
  MOCK_TAILSCALE_STATUS="1"
[[ ! -f "${TOUCH_FILE}" ]] || fail "loopback should not query tailscale"

assert_bound "custom port preserved" "${TAIL_A}" "18080" \
  HEALTH_QUANT_SERVER_HOST="0.0.0.0" \
  HEALTH_QUANT_SERVER_PORT="18080" \
  MOCK_TAILSCALE_STDOUT="${TAIL_A}"$'\n'

assert_refused "wildcard without tailscale" \
  PATH="/usr/bin:/bin" \
  HEALTH_QUANT_SERVER_HOST="0.0.0.0"

assert_refused "wildcard when tailscale fails" \
  HEALTH_QUANT_SERVER_HOST="0.0.0.0" \
  MOCK_TAILSCALE_STATUS="1" \
  MOCK_TAILSCALE_STDOUT="${TAIL_A}"$'\n'

assert_refused "wildcard when output empty" \
  HEALTH_QUANT_SERVER_HOST="0.0.0.0" \
  MOCK_TAILSCALE_STDOUT=""

assert_refused "wildcard when output is not tailscale ipv4" \
  HEALTH_QUANT_SERVER_HOST="0.0.0.0" \
  MOCK_TAILSCALE_STDOUT=$'8.8.8.8\n0.0.0.0\n'

assert_refused "lan address rejected" \
  HEALTH_QUANT_SERVER_HOST="192.168.1.50" \
  MOCK_TAILSCALE_STDOUT="${TAIL_A}"$'\n'

assert_refused "other cgnat address rejected" \
  HEALTH_QUANT_SERVER_HOST="100.64.9.9" \
  MOCK_TAILSCALE_STDOUT="${TAIL_A}"$'\n'

assert_refused "localhost rejected" \
  HEALTH_QUANT_SERVER_HOST="localhost" \
  MOCK_TAILSCALE_STDOUT="${TAIL_A}"$'\n'

assert_refused "other loopback rejected" \
  HEALTH_QUANT_SERVER_HOST="127.0.0.2" \
  MOCK_TAILSCALE_STDOUT="${TAIL_A}"$'\n'

assert_refused "ipv6 rejected" \
  HEALTH_QUANT_SERVER_HOST="::1" \
  MOCK_TAILSCALE_STDOUT="${TAIL_A}"$'\n'

echo "ok"
