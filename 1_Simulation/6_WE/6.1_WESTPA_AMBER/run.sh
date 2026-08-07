#!/usr/bin/env bash
set -euo pipefail

source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/env.sh"
cd "$WEST_SIM_ROOT"
w_run --work-manager processes "$@" 2>&1 | tee west.log
