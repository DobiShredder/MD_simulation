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

input_pdb=$1

if (( ! ${dry_run:-0} )) &&
        [[ ${original_args[0]:-} != -h && ${original_args[0]:-} != --help && ${original_args[0]:-} != --dry-run ]] &&
        [[ ${MD_WRITER_PARENT:-} != "$PPID" || ${MD_WRITER_ENTRY:-} != "$0" ]]; then
    exec "${PYTHON:-python3}" helpers/writer_guard.py \
        --registry "work" --read "$input_pdb" --read "inputs" --write "work" -- "$0" "${original_args[@]}"
fi

if [[ -e work/system.parm7 || -e work/system.rst7 ]]; then
    die "Build output already exists and was retained: work. Start from a separate tutorial directory."
fi

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

echo "Generating the ff19SB/OPC system shared by ratchet MD and US."
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
