#!/usr/bin/env bash
set -euo pipefail

original_args=("$@")

if [[ $# -ne 1 ]]; then
    echo "Usage: $0 CHIGNOLIN.pdb" >&2
    exit 2
fi

die() {
    echo "Error: $*" >&2
    exit 1
}

source ./env.sh
input_pdb=$1
tleap=${TLEAP:-tleap}
build_dir="$WORK_DIR/common_files"
basis_dir="$WORK_DIR/bstates"

if [[ ${MD_WRITER_PARENT:-} != "$PPID" || ${MD_WRITER_ENTRY:-} != "$0" ]]; then
    exec "${PYTHON:-python3}" helpers/writer_guard.py \
        --registry "$WORK_DIR" --read "$input_pdb" --read "inputs" --read "bstates" --read "tstate.file" --read "west.cfg" --write "$WORK_DIR" -- "$0" "${original_args[@]}"
fi

if [[ -d "$WORK_DIR" ]]; then
    existing_result=$(find "$WORK_DIR" -type f \
        \( -name 'west.h5' -o -name 'segment.out' \) -print -quit)
    if [[ -n "$existing_result" ]]; then
        die "Existing WESTPA results were found: $existing_result"
    fi
fi

if [[ ! -s "$input_pdb" ]]; then
    die "Chignolin PDB not found: $input_pdb"
fi
for executable in "$tleap" "$AMBER_ENGINE" "$CPPTRAJ"; do
    if ! command -v "$executable" >/dev/null 2>&1; then
        die "Executable not found: $executable"
    fi
done

"${PYTHON:-python3}" helpers/input_identity.py --verify "$build_dir"
"${PYTHON:-python3}" helpers/input_identity.py \
    --record "$WORK_DIR/.basis-source.identity.json" --stage "WE basis source inputs" \
    --input "$input_pdb" --input inputs/leap.in --input inputs/minimize.in \
    --input inputs/heat.in --input inputs/equilibrate.in --value="$AMBER_ENGINE" --value="$tleap"
"${PYTHON:-python3}" helpers/input_identity.py \
    --record "$WORK_DIR/.topology.identity.json" --stage "WE topology build" \
    --input "$input_pdb" --input inputs/leap.in \
    --output "$build_dir/system.parm7" --output "$build_dir/system.rst7" \
    --output "$build_dir/input.pdb" --output "$build_dir/leap.in" --output "$build_dir/leap.log"

mkdir -p "$build_dir" "$basis_dir"

topology_status=$("${PYTHON:-python3}" helpers/input_identity.py \
    --check-completion "$WORK_DIR/.topology.identity.json")
if [[ "$topology_status" == complete ]]; then
    echo "Skipping: topology outputs already exist."
else
    cp "$input_pdb" "$build_dir/input.pdb"
    cp "$WEST_SIM_ROOT/inputs/leap.in" "$build_dir/leap.in"

    echo "Generating the Chignolin topology."
    if ! (cd "$build_dir" && "$tleap" -f leap.in > leap.log 2>&1); then
        die "tleap failed: $build_dir/leap.log"
    fi
    for output in system.parm7 system.rst7; do
        if [[ ! -s "$build_dir/$output" ]]; then
            die "Topology build output was not created: $build_dir/$output; log: $build_dir/leap.log"
        fi
    done
    "${PYTHON:-python3}" helpers/input_identity.py \
        --finish-completion "$WORK_DIR/.topology.identity.json" \
        --required-output "$build_dir/system.parm7" --required-output "$build_dir/system.rst7"
    echo "Completed: WE topology build ($build_dir)"
fi

run_basis_stage() {
    local stage=$1
    local input_restart=$2
    local output_restart=$3
    shift 3
    local output_file="$build_dir/$stage.out"

    "${PYTHON:-python3}" helpers/input_identity.py \
        --record "$build_dir/.$stage.identity.json" --stage "WE basis $stage" -- "$AMBER_ENGINE" \
        -O -i "$WEST_SIM_ROOT/inputs/$stage.in" -o "$output_file" \
        -p "$build_dir/system.parm7" -c "$input_restart" -r "$output_restart" \
        -inf "$build_dir/$stage.info" "$@"
    local completion_state
    completion_state=$("${PYTHON:-python3}" helpers/input_identity.py \
        --check-completion "$build_dir/.$stage.identity.json")
    if [[ "$completion_state" == complete ]]; then
        echo "Skipping: $stage outputs already exist."
        return
    fi

    echo "Running: $stage"
    if ! "$AMBER_ENGINE" \
        -O \
        -i "$WEST_SIM_ROOT/inputs/$stage.in" \
        -o "$output_file" \
        -p "$build_dir/system.parm7" \
        -c "$input_restart" \
        -r "$output_restart" \
        -inf "$build_dir/$stage.info" \
        "$@"; then
        die "Basis-state $stage failed: $output_file"
    fi
    local output
    for output in "$output_file" "$output_restart"; do
        if [[ ! -s "$output" ]]; then
            die "Basis-state $stage output was not created: $output"
        fi
    done
    "${PYTHON:-python3}" helpers/input_identity.py \
        --finish-completion "$build_dir/.$stage.identity.json"
    echo "Completed: WE basis-state $stage ($output_restart)"
}

run_basis_stage minimize "$build_dir/system.rst7" "$build_dir/minimize.rst7"
cp "$build_dir/minimize.rst7" "$build_dir/reference.rst7"
run_basis_stage heat "$build_dir/minimize.rst7" "$build_dir/heat.rst7" \
    -ref "$build_dir/minimize.rst7"
run_basis_stage equilibrate "$build_dir/heat.rst7" "$basis_dir/basis.rst7" \
    -x "$build_dir/equilibrate.nc"

echo "WESTPA basis state: $basis_dir/basis.rst7"
