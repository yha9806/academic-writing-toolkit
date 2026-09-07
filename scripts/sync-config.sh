#!/usr/bin/env bash
# Compatibility entrypoint; native Windows and Unix share the same implementation.
set -euo pipefail
SCRIPT_DIR="$(cd -- "${BASH_SOURCE[0]%/*}" && pwd)"
exec node "$SCRIPT_DIR/setup.mjs" sync "$@"
