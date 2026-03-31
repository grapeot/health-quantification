#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
APP_BUNDLE="${ROOT_DIR}/native/apple_health_exporter_app/build/AppleHealthExporterApp.app"

if [[ ! -d "${APP_BUNDLE}" ]]; then
  "${ROOT_DIR}/scripts/build_native_exporter_app.sh"
fi

open "${APP_BUNDLE}"
