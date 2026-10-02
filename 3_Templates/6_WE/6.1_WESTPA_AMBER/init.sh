#!/usr/bin/env bash
set -euo pipefail

original_args=("$@")

show_help() {
    cat <<'EOF'
Usage: ./init.sh

Initialize the WESTPA steady-state simulation from the generated basis state.

Options:
  -h, --help     Show this help message and exit.
EOF
}

case "${1:-}" in
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
case "$WEST_SIM_ROOT" in
    /*) ;;
    *) WEST_SIM_ROOT="$PWD/$WEST_SIM_ROOT" ;;
esac
export WORK_DIR=${WORK_DIR:-$WEST_SIM_ROOT/work}
# WESTPA callbacks change directory; resolve their shared root at this boundary.
case "$WORK_DIR" in
    /*) ;;
    *) WORK_DIR="$WEST_SIM_ROOT/$WORK_DIR" ;;
esac
export AMBER_ENGINE=${AMBER_ENGINE:-pmemd.cuda}
export CPPTRAJ=${CPPTRAJ:-cpptraj}
if (( ! ${dry_run:-0} )) && [[ ${MD_WRITER_PARENT:-} != "$PPID" || ${MD_WRITER_ENTRY:-} != "$0" ]]; then
    exec "${PYTHON:-python3}" helpers/writer_guard.py \
        --registry "$WORK_DIR" --write "$WORK_DIR" -- "$0" "${original_args[@]}"
fi

for required in "$WORK_DIR/bstates/basis.rst7" "$WORK_DIR/bstates/bstates.txt" "$WORK_DIR/tstate.file" "$WORK_DIR/configs/west.001.cfg" "$WORK_DIR/initial_walkers.txt" "$WORK_DIR/basis_pcoord.txt"; do
    if [[ ! -s "$required" ]]; then
        die "WE build output not found. Run ./build.sh first: $required"
    fi
done
if ! command -v w_init >/dev/null 2>&1; then
    die "w_init not found. Activate the WESTPA 2 environment."
fi

if [[ -e "$WORK_DIR/west.h5" ]]; then
    die "Existing WESTPA state retained: $WORK_DIR/west.h5. Choose a new WORK_DIR to initialize another run."
fi

"${PYTHON:-python3}" helpers/input_identity.py --westpa-records "$WORK_DIR"
"${PYTHON:-python3}" helpers/input_identity.py \
    --record "$WORK_DIR/.we-input.identity.json" --stage "WESTPA immutable inputs" \
    --input "$WORK_DIR/common_files/system.parm7" --input "$WORK_DIR/common_files/reference.rst7" \
    --input "$WORK_DIR/bstates/basis.rst7" --input "$WORK_DIR/bstates/bstates.txt" \
    --input "$WORK_DIR/tstate.file" --input "$WORK_DIR/initial_walkers.txt" \
    --input "$WORK_DIR/basis_pcoord.txt" --input "$WORK_DIR/progress_coordinate.mask" \
    --input "$WEST_SIM_ROOT/westpa_scripts/runseg.sh" \
    --input "$WEST_SIM_ROOT/westpa_scripts/get_pcoord.sh" --input "$WEST_SIM_ROOT/westpa_scripts/calc_pcoord.sh" \
    --input "$WORK_DIR/inputs/segment.in.template" --input "$WORK_DIR/configs/west.001.cfg" \
    --output "$WORK_DIR/west.h5" --output "$WORK_DIR/west.init.log"

mkdir -p "$WORK_DIR/traj_segs" "$WORK_DIR/seg_logs" "$WORK_DIR/istates"
initial_walkers=$(<"$WORK_DIR/initial_walkers.txt")
echo "Initializing WESTPA state; log: $WORK_DIR/west.init.log"
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

if [[ ! -s "$WORK_DIR/west.h5" ]]; then
    die "WESTPA initialization did not create state: $WORK_DIR/west.h5"
fi

echo "WESTPA state: $WORK_DIR/west.h5"
