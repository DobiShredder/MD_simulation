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

input=$1
work_dir=work

if [[ ! -f "$input" ]]; then
    die "Input PDB not found: $input"
fi
if ! command -v tleap >/dev/null 2>&1; then
    die "tleap not found."
fi
if find "$work_dir" -type f \
    \( -name 'min*.out' -o -name 'heat*.out' -o -name 'equil*.out' \
       -o -name 'production*.out' \) -print -quit 2>/dev/null | grep -q .; then
    die "Simulation output already exists in $work_dir. Remove it before rebuilding."
fi

# AMBER system build
echo "Generating a Chignolin system with ff19SB/TIP3P."

mkdir -p "$work_dir"
cp "$input" "$work_dir/input.pdb"
cp tleap.in "$work_dir/tleap.in"

if ! (
    cd "$work_dir"
    tleap \
        -f "tleap.in" \
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

echo "AMBER topology and restart: $work_dir"
