#!/usr/bin/env bash
set -euo pipefail

source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/env.sh"
[[ -s "$WEST_SIM_ROOT/bstates/basis.rst7" ]] || {
    echo "ERROR: run ./prepare.sh first." >&2
    exit 1
}

rm -rf "$WEST_SIM_ROOT/traj_segs" "$WEST_SIM_ROOT/seg_logs" \
    "$WEST_SIM_ROOT/istates" "$WEST_SIM_ROOT/ANALYSIS"
rm -f "$WEST_SIM_ROOT/west.h5" "$WEST_SIM_ROOT/west.log"
mkdir -p "$WEST_SIM_ROOT/traj_segs" "$WEST_SIM_ROOT/seg_logs" \
    "$WEST_SIM_ROOT/istates"

w_init --bstate-file "$WEST_SIM_ROOT/bstates/bstates.txt" \
    --tstate-file "$WEST_SIM_ROOT/tstate.file" --segs-per-state 4 \
    --work-manager threads "$@"
