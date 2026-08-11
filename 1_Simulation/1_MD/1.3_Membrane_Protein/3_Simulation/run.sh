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

topology=${TOPOLOGY:-../2_Topology_Build/work/system.parm7}
coordinates=${COORDINATES:-../2_Topology_Build/work/system.rst7}
work_dir=${WORK_DIR:-work}

# Input and dependency checks
if (( ! dry_run )); then
    if ! command -v "$engine" >/dev/null 2>&1; then
        die "AMBER engine not found: $engine"
    fi

    if [[ ! -s "$topology" ]]; then
        die "topology not found: $topology"
    fi

    if [[ ! -s "$coordinates" ]]; then
        die "restart file not found: $coordinates"
    fi

fi

# Working directory setup
if (( dry_run )); then
    printf '+ mkdir -p %q\n' "$work_dir"
    printf '+ cd %q\n' "$work_dir"
else
    mkdir -p "$work_dir"
    mkdir -p "$work_dir/inputs"
    cp "$topology" "$work_dir/system.parm7"
    cp "$coordinates" "$work_dir/system.rst7"
    cp inputs/*.in "$work_dir/inputs/"
    cd "$work_dir"
    echo "AMBER engine: $engine (default: pmemd.cuda)"
fi

# Main workflow
run_stage 'environment minimization' \
    "$engine" \
    -O \
    -i inputs/min-environment.in \
    -o min-environment.out \
    -p system.parm7 \
    -c system.rst7 \
    -r min-environment.rst7 \
    -ref system.rst7

run_stage 'Whole-system minimization' \
    "$engine" \
    -O \
    -i inputs/min-all.in \
    -o min-all.out \
    -p system.parm7 \
    -c min-environment.rst7 \
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

run_stage '1 ns production' \
    "$engine" \
    -O \
    -i inputs/production.in \
    -o production.out \
    -p system.parm7 \
    -c equil.rst7 \
    -r production.rst7 \
    -x production.nc \
    -inf production.info

if (( ! dry_run )); then
    echo "Production trajectory: production.nc"
fi
