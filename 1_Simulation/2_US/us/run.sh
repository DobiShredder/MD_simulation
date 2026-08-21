#!/usr/bin/env bash
set -euo pipefail

selected_window=""
dry_run=0
while (( $# > 0 )); do
    case "$1" in
        --dry-run)
            dry_run=1
            shift
            ;;
        --window)
            if [[ $# -lt 2 ]]; then
                echo "Usage: $0 [--dry-run] [--window N]" >&2
                exit 2
            fi
            selected_window=$2
            shift 2
            ;;
        *)
            echo "Usage: $0 [--dry-run] [--window N]" >&2
            exit 2
            ;;
    esac
done

die() {
    echo "Error: $*" >&2
    exit 1
}

run_stage() {
    local window_dir=$1
    local stage=$2
    local label=$3
    shift 3

    if (( dry_run )); then
        printf '+ (cd %q && ' "$window_dir"
        printf '%q ' "$@"
        printf ')\n'
        return
    fi

    if [[ -s "$window_dir/$stage.out" && -s "$window_dir/$stage.rst7" ]]; then
        echo "Skipping completed stage: US window ${window_dir##*/} - $label"
        return
    fi
    if [[ -e "$window_dir/$stage.out" || -e "$window_dir/$stage.rst7" ]]; then
        echo "Warning: restarting incomplete stage: US window ${window_dir##*/} - $label" >&2
    fi

    echo "Running: US window ${window_dir##*/} - $label"
    if ! (
        cd "$window_dir"
        "$@"
    ); then
        die "Window ${window_dir##*/} $label failed."
    fi
}

run_window() {
    local window_dir=$1

    run_stage "$window_dir" min minimization \
        "$engine" -O -i ../inputs/min.in -o min.out \
        -p system.parm7 -c seed.rst7 -r min.rst7

    run_stage "$window_dir" heat heating \
        "$engine" -O -i ../inputs/heat.in -o heat.out \
        -p system.parm7 -c min.rst7 -r heat.rst7 \
        -x heat.nc -inf heat.info -ref min.rst7

    run_stage "$window_dir" equil equilibration \
        "$engine" -O -i ../inputs/equil.in -o equil.out \
        -p system.parm7 -c heat.rst7 -r equil.rst7 \
        -x equil.nc -inf equil.info

    run_stage "$window_dir" production production \
        "$engine" -O -i ../inputs/production.in -o production.out \
        -p system.parm7 -c equil.rst7 -r production.rst7 \
        -x production.nc -inf production.info
}

engine=${AMBER_ENGINE:-pmemd.cuda}

if (( ! dry_run )) && ! command -v "$engine" >/dev/null 2>&1; then
    die "AMBER engine not found: $engine"
fi
if [[ ! -d work ]]; then
    die "Run ./build.sh first."
fi

window_dirs=()
if [[ -n "$selected_window" ]]; then
    if [[ ! "$selected_window" =~ ^[1-9][0-9]*$ ]]; then
        die "Window index must be a positive integer: $selected_window"
    fi
    printf -v window_id '%03d' "$((10#$selected_window))"
    window_dirs+=("work/$window_id")
else
    for window_dir in work/[0-9][0-9][0-9]; do
        if [[ -d "$window_dir" ]]; then
            window_dirs+=("$window_dir")
        fi
    done
fi

if (( ${#window_dirs[@]} == 0 )); then
    die "No umbrella windows were found in work."
fi

for window_dir in "${window_dirs[@]}"; do
    for required_file in system.parm7 seed.rst7 restraint.RST; do
        if [[ ! -s "$window_dir/$required_file" ]]; then
            die "Required input is missing: $window_dir/$required_file"
        fi
    done
    if (( ! dry_run )) && [[ -e "$window_dir/production.out" ]]; then
        die "Production output already exists: $window_dir/production.out"
    fi
done

if (( ! dry_run )); then
    mkdir -p work/inputs
    cp inputs/*.in work/inputs/
fi

for window_dir in "${window_dirs[@]}"; do
    run_window "$window_dir"
done

echo "Completed ${#window_dirs[@]} umbrella-window run(s): work"
