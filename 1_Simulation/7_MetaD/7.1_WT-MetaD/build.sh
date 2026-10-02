#!/usr/bin/env bash
set -euo pipefail

original_args=("$@")

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
            \( -name 'minimize.out' -o -name 'heat.out' \
               -o -name 'equilibrate.out' -o -name 'production.out' \) -print -quit)
    fi
    if [[ -n "$existing_result" ]]; then
        die "Existing simulation results were found: $existing_result. Remove the previous calculation results before rebuilding."
    fi
}

work_dir=work

if (( ! ${dry_run:-0} )) &&
        [[ ${original_args[0]:-} != -h && ${original_args[0]:-} != --help && ${original_args[0]:-} != --dry-run ]] &&
        [[ ${MD_WRITER_PARENT:-} != "$PPID" || ${MD_WRITER_ENTRY:-} != "$0" ]]; then
    exec "${PYTHON:-python3}" helpers/writer_guard.py \
        --registry "work" --read "$1" --read "inputs" --write "work" -- "$0" "${original_args[@]}"
fi


# A rebuild must not mix new inputs with topology/restart files from an older build.
if [[ -d "$work_dir" ]]; then
    existing_build=$(find "$work_dir" -type f \
        \( -name '*.parm7' -o -name '*.rst7' \) -print -quit)
    if [[ -n "$existing_build" ]]; then
        die "Build output already exists and was retained: $existing_build. Use a new work directory for a new build."
    fi
fi


refuse_existing_results "$work_dir"
tleap=${TLEAP:-tleap}
input_pdb=$1

if [[ ! -s "$input_pdb" ]]; then
    die "Input PDB not found: $input_pdb"
fi

command -v "$tleap" >/dev/null 2>&1 || die "tleap not found: $tleap"
command -v python3 >/dev/null 2>&1 || die "python3 not found."

mkdir -p "$work_dir"
cp "$input_pdb" "$work_dir/input.pdb"
cp inputs/tleap.in "$work_dir/tleap.in"

echo "Building AMBER topology: $work_dir/leap.log"
if ! (
    cd "$work_dir"
    "$tleap" -f tleap.in > leap.log 2>&1
); then
    die "tleap failed: $work_dir/leap.log"
fi

for output in system.parm7 system.rst7 system.pdb; do
    [[ -s "$work_dir/$output" ]] || die "build Output not found: $work_dir/$output"
done

echo "Checking topology and recording CV atoms: $work_dir/system.parm7"
python3 "check_topology.py" \
    "$work_dir/system.parm7" \
    "$work_dir/cv_atoms.tsv"

echo "Topology build Completed: $work_dir"
