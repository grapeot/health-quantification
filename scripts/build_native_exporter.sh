#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
EXPORTER_DIR="${ROOT_DIR}/native/apple_health_exporter"

swift build --package-path "${EXPORTER_DIR}"
