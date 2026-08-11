#!/usr/bin/env bash
set -euo pipefail

dry_run=0
if [[ "${1:-}" == "--dry-run" ]]; then
    dry_run=1
    shift
fi
if [[ $# -ne 1 ]]; then
    echo "Usage: $0 [--dry-run] SH3-PEPTIDE.pdb" >&2
    exit 2
fi

die() {
    echo "Error: $*" >&2
    exit 1
}

input_pdb=$1
metadata=$(dirname "$input_pdb")/system_metadata.tsv
tleap=${TLEAP:-tleap}
python=${PYTHON:-python3}
work_dir=${WORK_DIR:-"work"}

if (( dry_run )); then
    printf 'mkdir -p %q\n' "$work_dir"
    printf 'cp %q %q\n' "$input_pdb" "$work_dir/input.pdb"
    printf '%q -f %q\n' "$tleap" "inputs/tleap.in"
    printf '%q %q %q %q %q\n' "$python" "render_inputs.py" "$metadata" "inputs" "$work_dir/inputs"
    exit 0
fi

for input in "$input_pdb" "$metadata"; do
    if [[ ! -s "$input" ]]; then
        die "Build input not found: $input"
    fi
done
for executable in "$tleap" "$python"; do
    if ! command -v "$executable" >/dev/null 2>&1; then
        die "Executable not found: $executable"
    fi
done

mkdir -p "$work_dir"
cp "$input_pdb" "$work_dir/input.pdb"
cp "$metadata" "$work_dir/system_metadata.tsv"
cp inputs/tleap.in "$work_dir/tleap.in"

echo "Generating the ff19SB/TIP3P SH3-peptide topology."
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
if ! "$python" "render_inputs.py" "$metadata" "inputs" "$work_dir/inputs"; then
    die "Pep-GaMD input generation failed."
fi

echo "Pep-GaMD topology, restart, and generated inputs: $work_dir"
