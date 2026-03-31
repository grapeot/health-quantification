#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
APP_DIR="${ROOT_DIR}/native/apple_health_exporter_app"
BUILD_DIR="${APP_DIR}/build"
APP_NAME="AppleHealthExporterApp"
APP_BUNDLE="${BUILD_DIR}/${APP_NAME}.app"
MACOS_DIR="${APP_BUNDLE}/Contents/MacOS"
RESOURCES_DIR="${APP_BUNDLE}/Contents/Resources"
SIGN_IDENTITY="${APPLE_CODESIGN_IDENTITY:-}"

if [[ -z "${SIGN_IDENTITY}" ]]; then
  SIGN_IDENTITY="$(security find-identity -v -p codesigning | grep 'Apple Development:' | head -n 1 | awk '{print $2}' || true)"
fi

if [[ -z "${SIGN_IDENTITY}" ]]; then
  SIGN_IDENTITY='-'
fi

mkdir -p "${MACOS_DIR}" "${RESOURCES_DIR}"
cp "${APP_DIR}/Info.plist" "${APP_BUNDLE}/Contents/Info.plist"

swiftc \
  -framework AppKit \
  -framework HealthKit \
  "${APP_DIR}/Sources/main.swift" \
  -o "${MACOS_DIR}/${APP_NAME}"

codesign \
  --force \
  --deep \
  --timestamp=none \
  --sign "${SIGN_IDENTITY}" \
  --entitlements "${APP_DIR}/apple_health_exporter_app.entitlements" \
  "${APP_BUNDLE}"

printf '%s\n' "Built ${APP_BUNDLE}"
printf '%s\n' "Signed with ${SIGN_IDENTITY}"
