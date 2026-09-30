#!/usr/bin/env bash
set -euo pipefail

if [[ $# -ne 1 ]]; then
    echo "Usage: $0 SH3-PEPTIDE.pdb" >&2
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
metadata=$(dirname "$input_pdb")/system_metadata.tsv
tleap=${TLEAP:-tleap}
python=${PYTHON:-python3}
work_dir=work

# A rebuild must not mix new inputs with topology/restart files from an older build.
if [[ -d "$work_dir" ]]; then
    existing_build=$(find "$work_dir" -type f \
        \( -name '*.parm7' -o -name '*.rst7' \) -print -quit)
    if [[ -n "$existing_build" ]]; then
        die "Build output already exists and was retained: $existing_build. Use a new work directory for a new build."
    fi
fi


refuse_existing_results "$work_dir"

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

echo "Generating the ff19SB/OPC SH3-peptide topology."
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
echo "Generating Pep-GaMD inputs: $metadata -> $work_dir/inputs"
if ! "$python" "render_inputs.py" "$metadata" "inputs" "$work_dir/inputs"; then
    die "Pep-GaMD input generation failed: $metadata -> $work_dir/inputs"
fi

for generated_input in gamd_prepare.in production.in; do
    if [[ ! -s "$work_dir/inputs/$generated_input" ]]; then
        die "GaMD input generation did not create: $work_dir/inputs/$generated_input"
    fi
done

echo "Pep-GaMD topology, restart, and generated inputs: $work_dir"
