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

    "${PYTHON:-python3}" helpers/input_identity.py --verify "$window_dir"
    "${PYTHON:-python3}" helpers/input_identity.py \
        --record "$window_dir/.$stage.identity.json" --stage "$label" \
        --directory "$window_dir" --input "$window_dir/restraint.RST" -- "$@"

    if [[ -s "$window_dir/$stage.out" && -s "$window_dir/$stage.rst7" ]]; then
        reused_stage_count=$((reused_stage_count + 1))
        if [[ "${#window_dirs[@]}" -eq 1 ]]; then
            echo "Skipping completed stage: US window ${window_dir##*/} - $label"
        fi
        return
    fi
    if [[ -e "$window_dir/$stage.out" || -e "$window_dir/$stage.rst7" ]]; then
        echo "Warning: restarting incomplete stage: US window ${window_dir##*/} - $label" >&2
    fi

    if [[ "${#window_dirs[@]}" -eq 1 ]]; then
        echo "Running: US window ${window_dir##*/} - $label"
    fi
    if ! (
        cd "$window_dir"
        "$@"
    ); then
        die "Window ${window_dir##*/} $label failed. Expected output (if created): $window_dir/$stage.out"
    fi
    local output
    for output in "$window_dir/$stage.out" "$window_dir/$stage.rst7"; do
        if [[ ! -s "$output" ]]; then
            die "Window ${window_dir##*/} $label output was not created: $output"
        fi
    done
    if [[ "$stage" == production && ! -s "$window_dir/production.nc" ]]; then
        die "Window ${window_dir##*/} production trajectory was not created: $window_dir/production.nc"
    fi
}

run_window() {
    local window_dir=$1

    run_stage "$window_dir" min minimization \
        "$engine" -O -i ../../inputs/min.in -o min.out \
        -p system.parm7 -c seed.rst7 -r min.rst7

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
    if (( ! dry_run )) && [[ -e "$window_dir/production.out" ]]; then
        die "Production output already exists: $window_dir/production.out"
    fi
done

reused_stage_count=0
if (( ! dry_run )); then
    echo "Running: ${#window_dirs[@]} umbrella-window workflows (minimization, heating, equilibration, production): work"
fi
for window_dir in "${window_dirs[@]}"; do
    run_window "$window_dir"
done

if (( ! dry_run )); then
    if (( reused_stage_count > 0 )); then
        echo "Reused completed stages: $reused_stage_count (work)"
    fi
    echo "Completed ${#window_dirs[@]} umbrella-window run(s): work"
fi
