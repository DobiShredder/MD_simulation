#!/usr/bin/env bash
set -euo pipefail

dry_run=0

if [[ "${1:-}" == "--dry-run" ]]; then
    dry_run=1
    shift
fi

if [[ $# -ne 1 ]]; then
    echo "Usage: $0 [--dry-run] COMPLEX.pdb" >&2
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
            \( -name '.*.complete' -o -name 'min*.out' -o -name 'heat*.out' \
               -o -name 'equil*.out' -o -name 'production*.out' \) \
            -print -quit)
    fi
    if [[ -n "$existing_result" ]]; then
        die "Existing simulation results were found: $existing_result. Use a new WORK_DIR or remove the previous calculation results before rebuilding."
    fi
}

# Inputs and user settings
complex_pdb=$1
tleap=${TLEAP:-tleap}

work_dir=${WORK_DIR:-"work"}

refuse_existing_results "$work_dir"

ligand_mol2="$work_dir/jz4.mol2"
ligand_frcmod="$work_dir/jz4.frcmod"

# Input and dependency checks
if (( ! dry_run )); then
    if [[ ! -f "$complex_pdb" ]]; then
        die "complex PDB not found: $complex_pdb"
    fi

    if [[ ! -s "$ligand_mol2" ]]; then
        die "Ligand mol2 is missing. Run ./prepare.sh first."
    fi

    if [[ ! -s "$ligand_frcmod" ]]; then
        die "Ligand frcmod is missing. Run ./prepare.sh first."
    fi

    if ! command -v "$tleap" >/dev/null 2>&1; then
        die "tleap not found: $tleap"
    fi
fi

# Dry run prints commands without creating files.
if (( dry_run )); then
    printf 'mkdir -p %q\n' "$work_dir"
    printf 'cp %q %q\n' "$complex_pdb" "$work_dir/complex.pdb"
    printf 'cp %q %q\n' "tleap.in" "$work_dir/tleap.in"
    printf 'cd %q\n' "$work_dir"
    printf '%q \\\n' "$tleap"
    printf '  -f tleap.in\n'
    exit 0
fi

# Combine the protein and ligand into one solvated system.
echo "Generating the T4 lysozyme–JZ4 system with ff19SB/GAFF2/TIP3P."

mkdir -p "$work_dir"
cp "$complex_pdb" "$work_dir/complex.pdb"
cp "tleap.in" "$work_dir/tleap.in"

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

echo "AMBER topology and restart: $work_dir"
