#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PYTHON_BIN="${PYTHON_BIN:-python3}"

screen -dmS notice_monitor "$PYTHON_BIN" "$SCRIPT_DIR/notice.py"
