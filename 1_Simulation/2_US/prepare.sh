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

input_pdb=$1
tleap=${TLEAP:-tleap}

if [[ ! -s "$input_pdb" ]]; then
    die "Input PDB not found: $input_pdb"
fi
if ! command -v "$tleap" >/dev/null 2>&1; then
    die "tleap not found: $tleap"
fi
if compgen -G 'work/*.out' >/dev/null; then
    die "Simulation output already exists in work. Remove it before rebuilding."
fi

echo "Generating the ff19SB/TIP3P system shared by ratchet MD and US."
mkdir -p work
cp "$input_pdb" work/input.pdb
cp inputs/tleap.in work/tleap.in

if ! (
    cd work
    "$tleap" -f tleap.in > leap.log 2>&1
); then
    die "tleap failed. See log: work/leap.log"
fi

if [[ ! -s work/system.parm7 || ! -s work/system.rst7 ]]; then
    die "Topology or restart was not created. See log: work/leap.log"
fi

echo "Shared AMBER topology and restart: work"
