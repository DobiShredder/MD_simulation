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

# User settings and input/output paths
engine=${AMBER_ENGINE:-pmemd.cuda}
work_dir=${WORK_DIR:-work}
window_root="$work_dir"
processed_window_count=0
skipped_window_count=0

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

run_stage() {
    local window_dir=$1
    local stage=$2
    local stage_label=$3
    local input_file=$4
    local input_restart=$5
    shift 5
    local stage_type=preproduction
    local reference_restart=""
    local write_trajectory=0

    while [[ $# -gt 0 ]]; do
        case "$1" in
            --production)
                stage_type=production
                shift
                ;;
            --trajectory)
                write_trajectory=1
                shift
                ;;
            --reference)
                reference_restart=$2
                shift 2
                ;;
            *)
                die "Unsupported run_stage option: $1"
                ;;
        esac
    done

    local prefix="$window_dir/$stage"
    local completion_marker="$window_dir/.$stage.complete"
    local required=("$prefix.out" "$prefix.rst7")
    local command=(
        "$engine" -O
        -i "../inputs/$input_file"
        -o "$stage.out"
        -p system.parm7
        -c "$input_restart"
        -r "$stage.rst7"
    )
    if (( write_trajectory )); then
        required+=("$prefix.info" "$prefix.nc")
        command+=(-x "$stage.nc" -inf "$stage.info")
    fi
    if [[ -n "$reference_restart" ]]; then
        command+=(-ref "$reference_restart")
    fi

    if (( ! dry_run )); then
        local state
        state=$(stage_state "$completion_marker" "${required[@]}")
        if [[ "$state" == complete ]]; then
            return
        fi
        if [[ "$state" == partial ]]; then
            if [[ "$stage_type" == production ]]; then
                die "Partial production output detected: $prefix"
            fi
            echo "Warning: removing partial $stage_label output and restarting the stage: $prefix" >&2
            rm -f -- "$completion_marker" "${required[@]}"
        fi
    fi

    echo "Running: US window ${window_dir##*/} - $stage_label"
    if ! (
        cd "$window_dir"
        run_command "${command[@]}"
    ); then
        die "${window_dir##*/} window $stage_label failed: $prefix.out"
    fi

    if (( ! dry_run )); then
        local output
        for output in "${required[@]}"; do
            if [[ ! -s "$output" ]]; then
                die "${window_dir##*/} window $stage_label output is incomplete: $output"
            fi
        done
        touch "$completion_marker"
    fi
}

run_window() {
    local window_dir=$1
    local window_id=${window_dir##*/}
    local required_file
    local production_state=missing

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

    run_stage "$window_dir" min minimization min.in seed.rst7
    run_stage "$window_dir" heat heating heat.in min.rst7 \
        --trajectory --reference min.rst7
    run_stage "$window_dir" equil equilibration equil.in heat.rst7 \
        --trajectory
    run_stage "$window_dir" production production production.in equil.rst7 \
        --trajectory --production

    processed_window_count=$((processed_window_count + 1))
}

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
