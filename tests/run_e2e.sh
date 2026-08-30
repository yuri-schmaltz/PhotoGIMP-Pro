#!/usr/bin/env bash
# ==============================================================================
# GIMP + PhotoGIMP Modernization E2E Test Suite Runner Wrapper
# Ensures proper virtualenv, PYTHONPATH, XDG isolation, GLib memory tracking,
# and headless Xvfb / D-Bus session execution.
# ==============================================================================

set -eo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WORKSPACE_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

# Export testing environment variables
export PYTHONPATH="${WORKSPACE_ROOT}:${SCRIPT_DIR}:${PYTHONPATH:-}"
export G_SLICE="always-malloc"
export G_DEBUG="gc-friendly"
export G_ENABLE_DIAGNOSTIC="1"
export GIMP_TESTING_ENV="1"
export LC_ALL="C.UTF-8"
export LANG="C.UTF-8"

# Detect Python interpreter
if command -v python3 >/dev/null 2>&1; then
    PYTHON_BIN="python3"
elif command -v python >/dev/null 2>&1; then
    PYTHON_BIN="python"
else
    echo "[ERROR] Python 3 interpreter not found in PATH." >&2
    exit 1
fi

# Run the test runner
exec "${PYTHON_BIN}" "${SCRIPT_DIR}/run_e2e.py" "$@"
