#!/usr/bin/env bash
set -euo pipefail

reset=0
show_help() {
    cat <<'EOF'
Usage: ./init.sh [--reset]

Initialize the WESTPA steady-state simulation from the generated basis state.

Options:
  --reset        Remove the existing WESTPA state before initialization.
  -h, --help     Show this help message and exit.
EOF
}

case "${1:-}" in
    --reset) reset=1; shift ;;
    -h|--help) show_help; exit 0 ;;
esac
if [[ $# -ne 0 ]]; then
    show_help >&2
    exit 2
fi

die() {
    echo "Error: $*" >&2
    exit 1
}

export WEST_SIM_ROOT=${WEST_SIM_ROOT:-$PWD}
export WORK_DIR=${WORK_DIR:-$WEST_SIM_ROOT/work}
export AMBER_ENGINE=${AMBER_ENGINE:-pmemd.cuda}
export CPPTRAJ=${CPPTRAJ:-cpptraj}

for required in "$WORK_DIR/bstates/basis.rst7" "$WORK_DIR/bstates/bstates.txt" "$WORK_DIR/tstate.file" "$WORK_DIR/configs/west.001.cfg" "$WORK_DIR/initial_walkers.txt" "$WORK_DIR/basis_pcoord.txt"; do
    if [[ ! -s "$required" ]]; then
        die "WE build output not found. Run ./build.sh first: $required"
    fi
done
if ! command -v w_init >/dev/null 2>&1; then
    die "w_init not found. Activate the WESTPA 2 environment."
fi

if [[ -e "$WORK_DIR/west.h5" && "$reset" -eq 0 ]]; then
    die "An existing WESTPA state was found. Use ./init.sh --reset to start over."
fi
if (( reset )); then
    case "$WORK_DIR" in
        ""|/|"$HOME") die "Refusing to reset an unsafe WORK_DIR: $WORK_DIR" ;;
    esac
    for directory in "$WORK_DIR/traj_segs" "$WORK_DIR/seg_logs" "$WORK_DIR/istates" "$WORK_DIR/analysis"; do
        if [[ -d "$directory" ]]; then
            find "$directory" -depth -delete
        fi
    done
    find "$WORK_DIR" -maxdepth 1 -type f -name '.block.*.complete' -delete
    rm -f -- "$WORK_DIR/west.h5" "$WORK_DIR/west.log" "$WORK_DIR/west.init.log" "$WORK_DIR/get_pcoord.log"
fi

mkdir -p "$WORK_DIR/traj_segs" "$WORK_DIR/seg_logs" "$WORK_DIR/istates"
initial_walkers=$(<"$WORK_DIR/initial_walkers.txt")
if ! w_init \
    -r "$WORK_DIR/configs/west.001.cfg" \
    --bstate-file "$WORK_DIR/bstates/bstates.txt" \
    --tstate-file "$WORK_DIR/tstate.file" \
    --segs-per-state "$initial_walkers" \
    --work-manager serial > "$WORK_DIR/west.init.log" 2>&1; then
    die "WESTPA initialization failed: $WORK_DIR/west.init.log"
fi
if grep -q -- '-- ERROR' "$WORK_DIR/west.init.log"; then
    die "WESTPA initialization reported an error: $WORK_DIR/west.init.log"
fi

echo "WESTPA state: $WORK_DIR/west.h5"
