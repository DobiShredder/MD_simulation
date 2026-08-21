#!/usr/bin/env bash
set -euo pipefail

dry_run=0
preparation_only=0
production_only=0
segment_range=""

show_help() {
    cat <<'EOF'
Usage: ./run.sh [--preparation-only | --production-only] [--segments START-END] [--dry-run]

Run minimization, heating, equilibration, and configured production segments.

Options:
  --preparation-only  Run through equilibration and stop before production.
  --production-only   Run only production from completed preparation output.
  --segments RANGE    Run the inclusive 1-based production segment range.
  --dry-run      Print engine commands without running them.
  -h, --help     Show this help message and exit.
EOF
}

while [[ $# -gt 0 ]]; do
    case "$1" in
        --preparation-only) preparation_only=1; shift ;;
        --production-only) production_only=1; shift ;;
        --segments)
            if [[ $# -lt 2 ]]; then
                echo "Error: --segments requires START-END." >&2
                exit 2
            fi
            segment_range=$2
            shift 2
            ;;
        --dry-run) dry_run=1; shift ;;
        -h|--help) show_help; exit 0 ;;
        *) show_help >&2; exit 2 ;;
    esac
done
if (( preparation_only && production_only )); then
    echo "Error: --preparation-only and --production-only cannot be used together." >&2
    exit 2
fi

die() {
    echo "Error: $*" >&2
    exit 1
}

run_stage() {
    local stage=$1
    local stage_type=$2
    local label=$3
    local directory=$4
    shift 4
    local marker="$directory/.$stage.complete"
    local required=()
    local index

    for ((index = 1; index <= $#; index++)); do
        case "${!index}" in
            -o|-r|-x|-inf)
                index=$((index + 1))
                required+=("${!index}")
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
    if [[ -f "$marker" && "$existing" -eq "${#required[@]}" ]]; then
        return
    fi
    if [[ -f "$marker" || "$existing" -ne 0 ]]; then
        if [[ "$stage_type" == production ]]; then
            die "Partial production output detected: $directory"
        fi
        echo "Warning: removing partial $stage output and restarting the stage." >&2
        rm -f -- "$marker" "${required[@]}"
    fi

    echo "Running: $label"
    if ! "$@"; then
        die "$label failed"
    fi
    for output in "${required[@]}"; do
        if [[ ! -s "$output" ]]; then
            die "$label output was not created: $output"
        fi
    done
    touch "$marker"
}

work_dir=${WORK_DIR:-work}
topology="$work_dir/system.parm7"
coordinates="$work_dir/system.rst7"
resolved="$work_dir/resolved_config.toml"

if (( ! dry_run )); then
    if [[ ! -s "$topology" ]]; then
        die "Topology not found. Run ./build.sh first."
    fi
    if [[ ! -s "$coordinates" ]]; then
        die "Restart not found. Run ./build.sh first."
    fi
    if [[ ! -s "$resolved" ]]; then
        die "Resolved config not found. Run ./build.sh first."
    fi
fi

engine=${AMBER_ENGINE:-$(awk -F' = ' '$1=="engine" {gsub(/"/, "", $2); print $2}' "$resolved" 2>/dev/null || true)}
engine=${engine:-pmemd.cuda}
segments=$(awk -F' = ' '$1=="production_segments" {print $2}' "$resolved" 2>/dev/null || true)
segments=${segments:-10}
segment_start=1
segment_end=$segments
if [[ -n "$segment_range" ]]; then
    if [[ ! "$segment_range" =~ ^([1-9][0-9]*)-([1-9][0-9]*)$ ]]; then
        die "--segments must use START-END with 1-based indices: $segment_range"
    fi
    segment_start=${BASH_REMATCH[1]}
    segment_end=${BASH_REMATCH[2]}
    if (( segment_start > segment_end || segment_end > segments )); then
        die "Segment range is outside 1-$segments: $segment_range"
    fi
fi

if (( ! dry_run )); then
    if ! command -v "$engine" >/dev/null 2>&1; then
        die "AMBER engine not found: $engine"
    fi
fi

if (( ! production_only )); then
run_stage min-solvent preproduction "solvent minimization" "$work_dir" \
    "$engine" -O -i "$work_dir/inputs/min-solvent.in" \
    -o "$work_dir/min-solvent.out" -p "$topology" -c "$coordinates" \
    -r "$work_dir/min-solvent.rst7" -ref "$coordinates"

run_stage min-all preproduction "whole-system minimization" "$work_dir" \
    "$engine" -O -i "$work_dir/inputs/min-all.in" \
    -o "$work_dir/min-all.out" -p "$topology" -c "$work_dir/min-solvent.rst7" \
    -r "$work_dir/min-all.rst7"

run_stage heat preproduction "NVT heating" "$work_dir" \
    "$engine" -O -i "$work_dir/inputs/heat.in" \
    -o "$work_dir/heat.out" -p "$topology" -c "$work_dir/min-all.rst7" \
    -r "$work_dir/heat.rst7" -x "$work_dir/heat.nc" -inf "$work_dir/heat.info" \
    -ref "$work_dir/min-all.rst7"

run_stage equilibrate preproduction "NPT equilibration" "$work_dir" \
    "$engine" -O -i "$work_dir/inputs/equilibrate.in" \
    -o "$work_dir/equilibrate.out" -p "$topology" -c "$work_dir/heat.rst7" \
    -r "$work_dir/equilibrate.rst7" -x "$work_dir/equilibrate.nc" \
    -inf "$work_dir/equilibrate.info"
fi

if (( preparation_only )); then
    exit 0
fi
if (( ! dry_run )) && [[ ! -s "$work_dir/equilibrate.rst7" || ! -f "$work_dir/.equilibrate.complete" ]]; then
    die "Completed equilibration output is required for production: $work_dir/equilibrate.rst7"
fi

previous_restart="$work_dir/equilibrate.rst7"
if (( segment_start > 1 )); then
    printf -v previous_id '%03d' "$((segment_start - 1))"
    previous_restart="$work_dir/$previous_id/production.rst7"
    if (( ! dry_run )) && [[ ! -s "$previous_restart" || ! -f "$work_dir/$previous_id/.production.complete" ]]; then
        die "Previous production segment is incomplete: $work_dir/$previous_id"
    fi
fi
for ((segment_number = segment_start; segment_number <= segment_end; segment_number++)); do
    if (( segments == 1 )); then
        segment_dir=$work_dir
    else
        printf -v segment_id '%03d' "$segment_number"
        segment_dir="$work_dir/$segment_id"
    fi
    if (( ! dry_run )); then
        mkdir -p "$segment_dir"
    fi
    run_stage production production \
        "production segment $segment_number/$segments" "$segment_dir" \
        "$engine" -O -i "$work_dir/inputs/production.in" \
        -o "$segment_dir/production.out" -p "$topology" -c "$previous_restart" \
        -r "$segment_dir/production.rst7" -x "$segment_dir/production.nc" \
        -inf "$segment_dir/production.info"
    previous_restart="$segment_dir/production.rst7"
done

if (( ! dry_run )); then
    if (( segments == 1 )); then
        echo "Production output: $work_dir/production.out"
    else
        echo "Production segments: $work_dir/001 through $work_dir/$(printf '%03d' "$segments")"
    fi
fi
