#!/usr/bin/env bash
set -euo pipefail

if [[ $# -ne 1 ]]; then
    echo "Usage: $0 INPUT.pdb" >&2
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
            \( -name '.*.complete' -o -name 'minimize.out' -o -name 'heat.out' \
               -o -name 'equilibrate.out' -o -name 'production.out' \) -print -quit)
    fi
    if [[ -n "$existing_result" ]]; then
        die "Existing simulation results were found: $existing_result. Use a new WORK_DIR or remove the previous calculation results before rebuilding."
    fi
}

work_dir=${WORK_DIR:-"work"}

refuse_existing_results "$work_dir"
tleap=${TLEAP:-tleap}
input_pdb=$1

if [[ ! -s "$input_pdb" ]]; then
    die "Input PDB not found: $input_pdb"
fi

if [[ "$work_dir" != /* ]]; then
    work_dir="$(pwd)/$work_dir"
fi

command -v "$tleap" >/dev/null 2>&1 || die "tleap not found: $tleap"
command -v python3 >/dev/null 2>&1 || die "python3 not found."
mkdir -p "$work_dir"
cp "$input_pdb" "$work_dir/input.pdb"
cp inputs/tleap.in "$work_dir/tleap.in"

if ! (
    cd "$work_dir"
    "$tleap" -f tleap.in > leap.log 2>&1
); then
    die "tleap failed: $work_dir/leap.log"
fi
for output in system.parm7 system.rst7 system.pdb; do
    [[ -s "$work_dir/$output" ]] || die "build Output not found: $work_dir/$output"
done
python3 "check_topology.py" "$work_dir/system.parm7" "$work_dir/cv_atoms.tsv"
echo "Topology build Completed: $work_dir"
