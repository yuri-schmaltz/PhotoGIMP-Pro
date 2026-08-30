#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
chmod +x "$SCRIPT_DIR/integrate_photogimp.py"
python3 "$SCRIPT_DIR/integrate_photogimp.py" "$@"
