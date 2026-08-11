#!/usr/bin/env bash
set -euo pipefail

dry_run=0
selected_window=""

while [[ $# -gt 0 ]]; do
    case "$1" in
        --dry-run)
            dry_run=1
            shift
            ;;
        --window)
            if [[ $# -lt 2 ]]; then
                echo "Error: --window requires an index." >&2
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

run_command() {
    if (( dry_run )); then
        printf '+'
        printf ' %q' "$@"
        printf '\n'
        return
    fi

    "$@"
}

stage_state() {
    local marker=$1
    shift
    local existing=0
    local output
    for output in "$@"; do
        if [[ -s "$output" ]]; then
            existing=$((existing + 1))
        fi
    done
    if [[ -f "$marker" && "$existing" -eq "$#" ]]; then
        echo complete
    elif [[ ! -f "$marker" && "$existing" -eq 0 ]]; then
        echo missing
    else
        echo partial
    fi
}

run_window() {
    local window_dir=$1
    local window_id=${window_dir##*/}
    local required_file
    local production_state=missing
    local min_state
    local heat_state
    local equil_state

    for required_file in system.parm7 seed.rst7 restraint.RST; do
        if [[ ! -s "$window_dir/$required_file" ]]; then
            die "Required input is missing for $window_id: $required_file"
        fi
    done

    if (( ! dry_run )); then
        production_state=$(stage_state \
            "$window_dir/.production.complete" \
            "$window_dir/production.out" \
            "$window_dir/production.rst7" \
            "$window_dir/production.info" \
            "$window_dir/production.nc")
        if [[ "$production_state" == complete ]]; then
            skipped_window_count=$((skipped_window_count + 1))
            return
        fi
        if [[ "$production_state" == partial ]]; then
            die "Partial production output detected: $window_dir/production"
        fi
    fi

    # Minimization
    min_state=$(stage_state \
        "$window_dir/.min.complete" \
        "$window_dir/min.out" \
        "$window_dir/min.rst7")
    if [[ "$min_state" != complete ]] || (( dry_run )); then
        if [[ "$min_state" == partial ]] && (( ! dry_run )); then
            echo "Warning: removing partial minimization output and restarting the stage: $window_dir/min" >&2
            rm -f -- "$window_dir/.min.complete" "$window_dir/min.out" "$window_dir/min.rst7"
        fi
        if ! (
            cd "$window_dir"
            run_command \
                "$engine" \
                -O \
                -i ../inputs/min.in \
                -o min.out \
                -p system.parm7 \
                -c seed.rst7 \
                -r min.rst7
        ); then
            die "$window_id window minimization failed: $window_dir/min.out"
        fi

        if (( ! dry_run )); then
            if [[ ! -s "$window_dir/min.out" || ! -s "$window_dir/min.rst7" ]]; then
                die "$window_id window minimization output is incomplete: $window_dir/min"
            fi
            touch "$window_dir/.min.complete"
        fi
    fi

    # Heating
    heat_state=$(stage_state \
        "$window_dir/.heat.complete" \
        "$window_dir/heat.out" \
        "$window_dir/heat.rst7" \
        "$window_dir/heat.info" \
        "$window_dir/heat.nc")
    if [[ "$heat_state" != complete ]] || (( dry_run )); then
        if [[ "$heat_state" == partial ]] && (( ! dry_run )); then
            echo "Warning: removing partial heating output and restarting the stage: $window_dir/heat" >&2
            rm -f -- "$window_dir/.heat.complete" "$window_dir/heat.out" \
                "$window_dir/heat.rst7" "$window_dir/heat.info" "$window_dir/heat.nc"
        fi
        if ! (
            cd "$window_dir"
            run_command \
                "$engine" \
                -O \
                -i ../inputs/heat.in \
                -o heat.out \
                -p system.parm7 \
                -c min.rst7 \
                -r heat.rst7 \
                -x heat.nc \
                -inf heat.info \
                -ref min.rst7
        ); then
            die "$window_id window heating failed: $window_dir/heat.out"
        fi

        if (( ! dry_run )); then
            if [[ ! -s "$window_dir/heat.out" || ! -s "$window_dir/heat.rst7" ||
                  ! -s "$window_dir/heat.info" || ! -s "$window_dir/heat.nc" ]]; then
                die "$window_id window heating output is incomplete: $window_dir/heat"
            fi
            touch "$window_dir/.heat.complete"
        fi
    fi

    # Equilibration
    equil_state=$(stage_state \
        "$window_dir/.equil.complete" \
        "$window_dir/equil.out" \
        "$window_dir/equil.rst7" \
        "$window_dir/equil.info" \
        "$window_dir/equil.nc")
    if [[ "$equil_state" != complete ]] || (( dry_run )); then
        if [[ "$equil_state" == partial ]] && (( ! dry_run )); then
            echo "Warning: removing partial equilibration output and restarting the stage: $window_dir/equil" >&2
            rm -f -- "$window_dir/.equil.complete" "$window_dir/equil.out" \
                "$window_dir/equil.rst7" "$window_dir/equil.info" "$window_dir/equil.nc"
        fi
        if ! (
            cd "$window_dir"
            run_command \
                "$engine" \
                -O \
                -i ../inputs/equil.in \
                -o equil.out \
                -p system.parm7 \
                -c heat.rst7 \
                -r equil.rst7 \
                -x equil.nc \
                -inf equil.info
        ); then
            die "$window_id window equilibration failed: $window_dir/equil.out"
        fi

        if (( ! dry_run )); then
            if [[ ! -s "$window_dir/equil.out" || ! -s "$window_dir/equil.rst7" ||
                  ! -s "$window_dir/equil.info" || ! -s "$window_dir/equil.nc" ]]; then
                die "$window_id window equilibration output is incomplete: $window_dir/equil"
            fi
            touch "$window_dir/.equil.complete"
        fi
    fi

    # Production
    if [[ "$production_state" != complete ]] || (( dry_run )); then
        if ! (
            cd "$window_dir"
            run_command \
                "$engine" \
                -O \
                -i ../inputs/production.in \
                -o production.out \
                -p system.parm7 \
                -c equil.rst7 \
                -r production.rst7 \
                -x production.nc \
                -inf production.info
        ); then
            die "$window_id window production failed: $window_dir/production.out"
        fi

        if (( ! dry_run )); then
            if [[ ! -s "$window_dir/production.out" || ! -s "$window_dir/production.rst7" ||
                  ! -s "$window_dir/production.info" || ! -s "$window_dir/production.nc" ]]; then
                die "$window_id window production output is incomplete: $window_dir/production"
            fi
            touch "$window_dir/.production.complete"
        fi
    fi

    processed_window_count=$((processed_window_count + 1))
}

# User settings and input/output paths
engine=${AMBER_ENGINE:-pmemd.cuda}

work_dir=${WORK_DIR:-work}
window_root="$work_dir"

processed_window_count=0
skipped_window_count=0

# Input and dependency checks
if (( ! dry_run )); then
    if ! command -v "$engine" >/dev/null 2>&1; then
        die "AMBER engine not found: $engine"
    fi
fi

if [[ ! -d "$window_root" ]]; then
    die "generated window is missing. Run ./build.sh first."
fi

if (( ! dry_run )); then
    mkdir -p "$work_dir/inputs"
    cp inputs/*.in "$work_dir/inputs/"
fi

# Run the selected window or all windows
if [[ -n "$selected_window" ]]; then
    if [[ ! "$selected_window" =~ ^[0-9]+$ ]]; then
        die "Window index must be a positive integer: $selected_window"
    fi

    if (( 10#$selected_window == 0 )); then
        die "Window index must be at least 1: $selected_window"
    fi

    printf -v selected_window_id '%03d' "$((10#$selected_window))"
    selected_window_dir="$window_root/$selected_window_id"

    if [[ ! -d "$selected_window_dir" ]]; then
        die "window not found: $selected_window_id"
    fi

    run_window "$selected_window_dir"
else
    found_window_count=0

    for window_dir in "$window_root"/[0-9][0-9][0-9]; do
        if [[ ! -d "$window_dir" ]]; then
            continue
        fi

        found_window_count=$((found_window_count + 1))
        run_window "$window_dir"
    done

    if (( found_window_count == 0 )); then
        die "No runnable windows were found in ${window_root}."
    fi
fi

if (( ! dry_run )); then
    echo "Completed umbrella-window runs: ${processed_window_count} run," \
        "${skipped_window_count} already completed ($window_root)"
fi
