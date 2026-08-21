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

refuse_existing_results() {
    local directory=$1
    local existing_result=""
    if [[ -d "$directory" ]]; then
        existing_result=$(find "$directory" -type f \
            \( -name 'minimize.out' -o -name 'heat.out' \
               -o -name 'equilibrate.out' -o -name 'gamd_prepare.out' \
               -o -name 'production*.out' \) -print -quit)
    fi
    if [[ -n "$existing_result" ]]; then
        die "Existing simulation results were found: $existing_result. Remove the previous calculation results before rebuilding."
    fi
}

input_pdb=$1
tleap=${TLEAP:-tleap}
work_dir=work

refuse_existing_results "$work_dir"

if [[ ! -s "$input_pdb" ]]; then
    die "preparation PDB not found: $input_pdb"
fi
if ! command -v "$tleap" >/dev/null 2>&1; then
    die "tleap not found: $tleap"
fi

mkdir -p "$work_dir"
cp "$input_pdb" "$work_dir/input.pdb"
cp inputs/tleap.in "$work_dir/tleap.in"

echo "Generating the ff19SB/TIP3P Chignolin topology."
if ! (
    cd "$work_dir"
    "$tleap" -f tleap.in > leap.log 2>&1
); then
    die "tleap failed: $work_dir/leap.log"
fi

for output in system.parm7 system.rst7 system.pdb; do
    if [[ ! -s "$work_dir/$output" ]]; then
        die "build Output was not created: $work_dir/$output"
    fi
done

echo "AMBER topology and restart: $work_dir"
