#!/bin/bash
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

bash "$SCRIPT_DIR/tools_management/1_uninstall.sh" "$@" || EXIT_CODE=$?

find "$SCRIPT_DIR/stow-packages" -name '.DS_Store' -delete 2>/dev/null || true

exit ${EXIT_CODE:-0}
