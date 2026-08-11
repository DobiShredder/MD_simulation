#!/usr/bin/env bash
set -euo pipefail

dry_run=0

if [[ "${1:-}" == "--dry-run" ]]; then
    dry_run=1
    shift
fi

if [[ $# -ne 0 ]]; then
    echo "Usage: $0 [--dry-run]" >&2
    exit 2
fi

die() {
    echo "Error: $*" >&2
    exit 1
}

# User settings and input/output paths
tleap=${TLEAP:-tleap}

input_pdb=${INPUT_PDB:-"structure/chignolin.pdb"}
work_dir=${WORK_DIR:-"work"}

# Input and dependency checks
if (( ! dry_run )); then
    if [[ ! -s "$input_pdb" ]]; then
        die "Input PDB not found: $input_pdb"
    fi

    if ! command -v "$tleap" >/dev/null 2>&1; then
        die "tleap not found: $tleap"
    fi
fi

# Dry run prints commands without creating files.
if (( dry_run )); then
    printf 'mkdir -p %q\n' "$work_dir"
    printf 'cp %q %q\n' "$input_pdb" "$work_dir/input.pdb"
    printf 'cd %q\n' "$work_dir"
    printf '%q \\\n' "$tleap"
    printf '  -f %q\n' "inputs/tleap.in"
    exit 0
fi

# Build the system shared by ratchet MD and all umbrella windows.
echo "Generating the ff19SB/TIP3P system shared by ratchet MD and US."

mkdir -p "$work_dir"
cp "$input_pdb" "$work_dir/input.pdb"
cp inputs/tleap.in "$work_dir/tleap.in"

if ! (
    cd "$work_dir"
    "$tleap" \
        -f tleap.in \
        > leap.log 2>&1
); then
    die "tleap failed. See log: $work_dir/leap.log"
fi

if [[ ! -s "$work_dir/system.parm7" ]]; then
    die "Topology was not created. See log: $work_dir/leap.log"
fi

if [[ ! -s "$work_dir/system.rst7" ]]; then
    die "Restart file was not created. See log: $work_dir/leap.log"
fi

echo "Shared AMBER topology and restart: $work_dir"
