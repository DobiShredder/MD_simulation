#!/usr/bin/env bash
set -euo pipefail

source ./env.sh

reset=0
if [[ "${1:-}" == "--reset" ]]; then
    reset=1
    shift
fi
if [[ $# -ne 0 ]]; then
    echo "Usage: $0 [--reset]" >&2
    exit 2
fi

die() {
    echo "Error: $*" >&2
    exit 1
}

if [[ ! -s "$WORK_DIR/bstates/basis.rst7" ]]; then
    die "Run build.sh first: $WORK_DIR/bstates/basis.rst7"
fi
if ! command -v w_init >/dev/null 2>&1; then
    die "w_init not found. Activate the WESTPA 2 environment."
fi

if [[ -e "$WORK_DIR/west.h5" && "$reset" -eq 0 ]]; then
    die "An existing WESTPA state was found. Use ./init.sh --reset to start over."
fi

if (( reset )); then
    if [[ -z "$WORK_DIR" || "$WORK_DIR" == / || "$WORK_DIR" == "$HOME" ]]; then
        die "Refusing to reset an unsafe WORK_DIR: $WORK_DIR"
    fi
    rm -rf \
        "$WORK_DIR/traj_segs" \
        "$WORK_DIR/seg_logs" \
        "$WORK_DIR/istates" \
        "$WORK_DIR/analysis"
    rm -f "$WORK_DIR/west.h5" "$WORK_DIR/west.log"
fi

mkdir -p "$WORK_DIR/traj_segs" "$WORK_DIR/seg_logs" "$WORK_DIR/istates"
cd "$WEST_SIM_ROOT"
w_init \
    --bstate-file "$WEST_SIM_ROOT/bstates/bstates.txt" \
    --tstate-file "$WEST_SIM_ROOT/tstate.file" \
    --segs-per-state 4 \
    --work-manager serial

echo "WESTPA state: $WORK_DIR/west.h5"
