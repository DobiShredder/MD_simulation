#!/usr/bin/env bash
set -euo pipefail

dry_run=0

while [[ $# -gt 0 ]]; do
    case "$1" in
    --dry-run)
        dry_run=1
        ;;
    *)
        echo "Usage: $0 [--dry-run]" >&2
        exit 2
        ;;
    esac
    shift
done

die() {
    echo "Error: $*" >&2
    exit 1
}

run_stage() {
    local stage=$1
    shift

    if (( dry_run )); then
        printf '+'
        printf ' %q' "$@"
        printf '\n'
        return
    fi

    echo "Running: $stage ($engine)"

    if ! "$@"; then
        die "$stage stage failed. Check: $work_dir"
    fi
}

# User settings and input/output paths
engine=${AMBER_ENGINE:-pmemd.cuda}

system_dir=${SYSTEM_DIR:-../work}
work_dir=${WORK_DIR:-work}

source_topology="$system_dir/system.parm7"
source_coordinates="$system_dir/system.rst7"

# Input and dependency checks
if (( ! dry_run )); then
    if ! command -v "$engine" >/dev/null 2>&1; then
        die "AMBER engine not found: $engine"
    fi

    if [[ ! -s "$source_topology" ]]; then
        die "shared topology not found: $source_topology" \
            "Run ./prepare.sh from the parent directory first."
    fi

    if [[ ! -s "$source_coordinates" ]]; then
        die "shared restart file not found: $source_coordinates" \
            "Run ./prepare.sh from the parent directory first."
    fi
fi

# Place the PLUMED input in the working directory under a fixed name.
if (( dry_run )); then
    printf '+ mkdir -p %q\n' "$work_dir"
    printf '+ cp %q %q\n' "$source_topology" "$work_dir/system.parm7"
    printf '+ cp %q %q\n' "$source_coordinates" "$work_dir/system.rst7"
    printf '+ cp inputs/\*.in %q\n' "$work_dir/inputs/"
    printf '+ cp inputs/plumed.dat %q\n' "$work_dir/plumed.dat"
    printf '+ cd %q\n' "$work_dir"
else
    mkdir -p "$work_dir"
    mkdir -p "$work_dir/inputs"
    cp "$source_topology" "$work_dir/system.parm7"
    cp "$source_coordinates" "$work_dir/system.rst7"
    cp inputs/*.in "$work_dir/inputs/"
    cp inputs/plumed.dat "$work_dir/plumed.dat"
    cd "$work_dir"
    echo "Running ratchet MD with: $engine"
fi

# Main workflow
run_stage 'solvent minimization' \
    "$engine" \
    -O \
    -i inputs/min-solvent.in \
    -o min-solvent.out \
    -p system.parm7 \
    -c system.rst7 \
    -r min-solvent.rst7 \
    -ref system.rst7

run_stage 'Whole-system minimization' \
    "$engine" \
    -O \
    -i inputs/min-all.in \
    -o min-all.out \
    -p system.parm7 \
    -c min-solvent.rst7 \
    -r min-all.rst7

run_stage 'NVT heating' \
    "$engine" \
    -O \
    -i inputs/heat.in \
    -o heat.out \
    -p system.parm7 \
    -c min-all.rst7 \
    -r heat.rst7 \
    -x heat.nc \
    -inf heat.info \
    -ref min-all.rst7

run_stage 'NPT equilibration' \
    "$engine" \
    -O \
    -i inputs/equil.in \
    -o equil.out \
    -p system.parm7 \
    -c heat.rst7 \
    -r equil.rst7 \
    -x equil.nc \
    -inf equil.info \
    -ref heat.rst7

if (( ! dry_run )); then
    final_density=$(awk '
        /A V E R A G E S/ { exit }
        /Density/ { density = $3 }
        END { print density }
    ' equil.out)

    if [[ -z "$final_density" ]]; then
        die "Could not read the final density from equil.out: $work_dir/equil.out"
    fi

    if ! awk \
        -v density="$final_density" \
        'BEGIN { exit !(density >= 0.90 && density <= 1.10) }'; then
        die "Density after NPT is outside the validation range: " \
            "${final_density} g/cm^3. Ratchet MD will not start."
    fi

    echo "NPT final density: ${final_density} g/cm^3"
fi

run_stage '1 ns ratchet MD' \
    "$engine" \
    -O \
    -i inputs/ratchet.in \
    -o ratchet.out \
    -p system.parm7 \
    -c equil.rst7 \
    -r ratchet.rst7 \
    -x ratchet.nc \
    -inf ratchet.info

if (( ! dry_run )); then
    echo "Ratchet MD trajectory: ratchet.nc"
fi
