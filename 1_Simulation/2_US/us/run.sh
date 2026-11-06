#!/usr/bin/env bash
set -euo pipefail

original_args=("$@")

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

show_engine_output() {
    local output=$1
    if [[ -s "$output" ]]; then
        echo "Last 20 lines of $output:" >&2
        tail -n 20 "$output" >&2
    fi
}

# Partial output is never removed or overwritten; the user moves it out of work.
die_partial() {
    local reason=$1
    local window_dir=$2
    local label=$3
    shift 3
    local window_id=${window_dir##*/}
    local leftover_files=()
    local path
    for path in "$@"; do
        if [[ -e "$path" ]]; then
            leftover_files+=("$path")
        fi
    done
    if (( ${#leftover_files[@]} == 0 )); then
        die "${reason}No $label output was written for window $window_id. Fix the cause and rerun $rerun_command."
    fi
    die "${reason}Partial $label output is retained for window $window_id: ${leftover_files[*]}. Move these files out of work (for example: mkdir -p work.failed/$window_id && mv ${leftover_files[*]} work.failed/$window_id/) and rerun $rerun_command."
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

    local window_id=${window_dir##*/}
    local stage_outputs=(
        "$window_dir/$stage.out"
        "$window_dir/$stage.rst7"
        "$window_dir/$stage.nc"
        "$window_dir/$stage.info"
    )
    "${PYTHON:-python3}" helpers/input_identity.py --verify "$window_dir"
    "${PYTHON:-python3}" helpers/input_identity.py \
        --record "$window_dir/.$stage.identity.json" --stage "$label" \
        --directory "$window_dir" --input "$window_dir/restraint.RST" -- "$@"

    # Output without completion evidence comes from a failed or interrupted run.
    if [[ ! -e "$window_dir/.$stage.success.json" ]]; then
        local output
        for output in "${stage_outputs[@]}"; do
            if [[ -e "$output" ]]; then
                die_partial "" "$window_dir" "$label" "${stage_outputs[@]}"
            fi
        done
    fi

    local completion_state
    completion_state=$("${PYTHON:-python3}" helpers/input_identity.py \
        --check-completion "$window_dir/.$stage.identity.json")
    if [[ "$completion_state" == complete ]]; then
        reused_stage_count=$((reused_stage_count + 1))
        if [[ "${#window_dirs[@]}" -eq 1 ]]; then
            echo "Skipping completed stage: US window ${window_dir##*/} - $label"
        fi
        return
    fi

    if [[ "${#window_dirs[@]}" -eq 1 ]]; then
        echo "Running: US window $window_id - $label"
    fi
    if ! (
        cd "$window_dir"
        "$@"
    ); then
        show_engine_output "$window_dir/$stage.out"
        die_partial "Window $window_id $label failed. " "$window_dir" "$label" "${stage_outputs[@]}"
    fi
    local required_output
    for required_output in "$window_dir/$stage.out" "$window_dir/$stage.rst7"; do
        if [[ ! -s "$required_output" ]]; then
            die_partial "Window $window_id $label output was not created: $required_output. " \
                "$window_dir" "$label" "${stage_outputs[@]}"
        fi
    done
    if [[ "$stage" == production && ! -s "$window_dir/production.nc" ]]; then
        die_partial "Window $window_id production trajectory was not created: $window_dir/production.nc. " \
            "$window_dir" "$label" "${stage_outputs[@]}"
    fi
    "${PYTHON:-python3}" helpers/input_identity.py \
        --finish-completion "$window_dir/.$stage.identity.json" --directory "$window_dir"

}

run_window() {
    local window_dir=$1
    local window_id=${window_dir##*/}

    # A completed window is skipped, never rerun. Manual continuation files
    # (continue.in) in that window are left alone.
    if (( ! dry_run )) && [[ -e "$window_dir/.production.success.json" ]]; then
        "${PYTHON:-python3}" helpers/input_identity.py \
            --check-completion "$window_dir/.production.identity.json" >/dev/null
        echo "Skipping completed window $window_id"
        skipped_window_count=$((skipped_window_count + 1))
        return
    fi

    run_stage "$window_dir" min minimization \
        "$engine" -O -i ../../inputs/min.in -o min.out \
        -p system.parm7 -c seed.rst7 -r min.rst7 -inf min.info

    run_stage "$window_dir" heat heating \
        "$engine" -O -i ../../inputs/heat.in -o heat.out \
        -p system.parm7 -c min.rst7 -r heat.rst7 \
        -x heat.nc -inf heat.info -ref min.rst7

    run_stage "$window_dir" equil equilibration \
        "$engine" -O -i ../../inputs/equil.in -o equil.out \
        -p system.parm7 -c heat.rst7 -r equil.rst7 \
        -x equil.nc -inf equil.info

    run_stage "$window_dir" production production \
        "$engine" -O -i ../../inputs/production.in -o production.out \
        -p system.parm7 -c equil.rst7 -r production.rst7 \
        -x production.nc -inf production.info
}

if (( dry_run )); then
    echo "Dry run: planned sampling commands; no engine execution"
fi

engine=${AMBER_ENGINE:-pmemd.cuda}

if (( ! dry_run )) && ! command -v "$engine" >/dev/null 2>&1; then
    die "AMBER engine not found: $engine"
fi
if [[ ! -d work ]]; then
    die "Run ./build.sh first."
fi

rerun_command="./run.sh"
if [[ -n "$selected_window" ]]; then
    rerun_command+=" --window $selected_window"
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

if (( ! dry_run )) && [[ ${MD_WRITER_PARENT:-} != "$PPID" || ${MD_WRITER_ENTRY:-} != "$0" ]]; then
    writer_options=()
    for window_dir in "${window_dirs[@]}"; do
        writer_options+=(--write "$window_dir")
    done
    exec "${PYTHON:-python3}" helpers/writer_guard.py \
        --registry ../work --read ../work --read inputs "${writer_options[@]}" \
        -- "$0" "${original_args[@]}"
fi

for window_dir in "${window_dirs[@]}"; do
    for required_file in system.parm7 seed.rst7 restraint.RST; do
        if [[ ! -s "$window_dir/$required_file" ]]; then
            die "Required input is missing: $window_dir/$required_file"
        fi
    done
done

reused_stage_count=0
skipped_window_count=0
if (( ! dry_run )); then
    echo "Running: ${#window_dirs[@]} umbrella-window workflows (minimization, heating, equilibration, production): work"
fi
for window_dir in "${window_dirs[@]}"; do
    run_window "$window_dir"
done

if (( ! dry_run )); then
    if (( skipped_window_count > 0 )); then
        echo "Skipped completed windows: $skipped_window_count (work)"
    fi
    if (( reused_stage_count > 0 )); then
        echo "Reused completed stages: $reused_stage_count (work)"
    fi
    echo "Completed ${#window_dirs[@]} umbrella-window run(s): work"
fi
