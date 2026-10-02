#!/usr/bin/env bash
set -euo pipefail

original_args=("$@")

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

if [[ ${MD_WRITER_PARENT:-} != "$PPID" || ${MD_WRITER_ENTRY:-} != "$0" ]]; then
    exec "${PYTHON:-python3}" helpers/writer_guard.py \
        --registry "$WORK_DIR" --read "inputs" --read "bstates" --read "tstate.file" --read "west.cfg" --write "$WORK_DIR" -- "$0" "${original_args[@]}"
fi

"${PYTHON:-python3}" helpers/input_identity.py --westpa-records "$WORK_DIR"
"${PYTHON:-python3}" helpers/input_identity.py \
    --record "$WORK_DIR/.we-input.identity.json" --stage "WESTPA immutable inputs" \
    --input "$WORK_DIR/common_files/system.parm7" --input "$WORK_DIR/common_files/reference.rst7" \
    --input "$WORK_DIR/bstates/basis.rst7" --input bstates/bstates.txt --input tstate.file \
    --input west.cfg --input inputs/segment.in.template \
    --input westpa_scripts/runseg.sh --input westpa_scripts/get_pcoord.sh --input westpa_scripts/calc_pcoord.sh \
    --output "$WORK_DIR/west.h5" --output "$WORK_DIR/west.log"

if [[ -e "$WORK_DIR/west.h5" && "$reset" -eq 0 ]]; then
    die "An existing WESTPA state was found: $WORK_DIR/west.h5. Use ./init.sh --reset to start over."
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
echo "Initializing WESTPA state: $WORK_DIR/west.h5"
if w_init \
    --bstate-file "$WEST_SIM_ROOT/bstates/bstates.txt" \
    --tstate-file "$WEST_SIM_ROOT/tstate.file" \
    --segs-per-state 4 \
    --work-manager serial; then
    :
else
    status=$?
    echo "Error: WESTPA initialization failed: $WORK_DIR/west.h5; inspect terminal diagnostics." >&2
    exit "$status"
fi

if [[ ! -s "$WORK_DIR/west.h5" ]]; then
    die "WESTPA initialization did not create state: $WORK_DIR/west.h5"
fi

echo "WESTPA state: $WORK_DIR/west.h5"
