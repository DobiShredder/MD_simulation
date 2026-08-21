#!/usr/bin/env bash
set -euo pipefail

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

mkdir -p "$build_dir" "$basis_dir"

if [[ -s "$build_dir/system.parm7" && -s "$build_dir/system.rst7" ]]; then
    echo "Skipping: topology outputs already exist."
else
    if [[ -e "$build_dir/system.parm7" || -e "$build_dir/system.rst7" ]]; then
        echo "Warning: incomplete topology outputs found; rebuilding the system." >&2
    fi
    cp "$input_pdb" "$build_dir/input.pdb"
    cp "$WEST_SIM_ROOT/inputs/leap.in" "$build_dir/leap.in"

    echo "Generating the Chignolin topology."
    if ! (cd "$build_dir" && "$tleap" -f leap.in > leap.log 2>&1); then
        die "tleap failed: $build_dir/leap.log"
    fi
fi

run_basis_stage() {
    local stage=$1
    local input_restart=$2
    local output_restart=$3
    shift 3
    local output_file="$build_dir/$stage.out"

    if [[ -s "$output_file" && -s "$output_restart" ]]; then
        echo "Skipping: $stage outputs already exist."
        return
    fi
    if [[ -e "$output_file" || -e "$output_restart" ]]; then
        echo "Warning: incomplete $stage outputs found; rerunning the stage." >&2
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
    if [[ ! -s "$output_file" || ! -s "$output_restart" ]]; then
        die "Basis-state $stage outputs were not created."
    fi
}

run_basis_stage minimize "$build_dir/system.rst7" "$build_dir/minimize.rst7"
cp "$build_dir/minimize.rst7" "$build_dir/reference.rst7"
run_basis_stage heat "$build_dir/minimize.rst7" "$build_dir/heat.rst7" \
    -ref "$build_dir/minimize.rst7"
run_basis_stage equilibrate "$build_dir/heat.rst7" "$basis_dir/basis.rst7" \
    -x "$build_dir/equilibrate.nc"

echo "WESTPA basis state: $basis_dir/basis.rst7"
