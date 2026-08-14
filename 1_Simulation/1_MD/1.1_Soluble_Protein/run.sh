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
    local stage_name=$1
    local stage_type=$2
    local stage_label=$3
    shift 3
    local completion_marker=".$stage_name.complete"
    local required=()
    local option_index

    # AMBER output options define which files must exist before the stage is marked complete.
    for ((option_index = 1; option_index <= $#; option_index++)); do
        case "${!option_index}" in
            -o|-r|-x|-inf)
                option_index=$((option_index + 1))
                required+=("${!option_index}")
                ;;
        esac
    done

    if (( dry_run )); then
        printf '+'
        printf ' %q' "$@"
        printf '\n'
        return
    fi

    local existing=0
    local output
    for output in "${required[@]}"; do
        if [[ -s "$output" ]]; then
            existing=$((existing + 1))
        fi
    done
    if [[ -f "$completion_marker" && "$existing" -eq "${#required[@]}" ]]; then
        return
    fi
    if [[ -f "$completion_marker" || "$existing" -ne 0 ]]; then
        if [[ "$stage_type" == production ]]; then
            die "Partial production output detected: $stage_name"
        fi
        echo "Warning: removing partial $stage_name output and restarting the stage." >&2
        rm -f -- "$completion_marker" "${required[@]}"
    fi

    echo "Running: $stage_label ($engine)"

    if ! "$@"; then
        die "$stage_label stage failed. Check: $work_dir"
    fi
    for output in "${required[@]}"; do
        if [[ ! -s "$output" ]]; then
            die "$stage_label output was not created: $work_dir/$output"
        fi
    done
    touch "$completion_marker"
}

# User settings and output paths
engine=${AMBER_ENGINE:-pmemd.cuda}

work_dir=${WORK_DIR:-work}
topology="$work_dir/system.parm7"
coordinates="$work_dir/system.rst7"

# Input and dependency checks
if (( ! dry_run )); then
    if ! command -v "$engine" >/dev/null 2>&1; then
        die "AMBER engine not found: $engine"
    fi

    if [[ ! -s "$topology" ]]; then
        die "Topology not found. Run ./build.sh first."
    fi

    if [[ ! -s "$coordinates" ]]; then
        die "Restart file not found. Run ./build.sh first."
    fi
fi

# Working directory setup
if (( dry_run )); then
    printf '+ mkdir -p %q\n' "$work_dir"
    printf '+ cd %q\n' "$work_dir"
else
    mkdir -p "$work_dir"
    mkdir -p "$work_dir/inputs"
    cp inputs/*.in "$work_dir/inputs/"
    cd "$work_dir"
    echo "AMBER engine: $engine (default: pmemd.cuda)"
fi

# Main workflow
run_stage min-solvent preproduction 'solvent minimization' \
    "$engine" \
    -O \
    -i inputs/min-solvent.in \
    -o min-solvent.out \
    -p system.parm7 \
    -c system.rst7 \
    -r min-solvent.rst7 \
    -ref system.rst7

run_stage min-all preproduction 'Whole-system minimization' \
    "$engine" \
    -O \
    -i inputs/min-all.in \
    -o min-all.out \
    -p system.parm7 \
    -c min-solvent.rst7 \
    -r min-all.rst7

run_stage heat preproduction 'NVT heating' \
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

run_stage equil preproduction 'NPT equilibration' \
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

run_stage production production '1 ns production' \
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
