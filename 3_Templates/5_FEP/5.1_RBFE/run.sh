#!/usr/bin/env bash
set -euo pipefail

dry_run=0
preparation_only=0
production_only=0
selected_system=""
selected_stage=""
window_range=""
while [[ $# -gt 0 ]]; do
case "$1" in
    --dry-run) dry_run=1; shift ;;
    --preparation-only) preparation_only=1; shift ;;
    --production-only) production_only=1; shift ;;
    --system|--stage|--windows)
        option=$1
        if [[ $# -lt 2 ]]; then
            echo "Error: $option requires a value." >&2
            exit 2
        fi
        case "$option" in
            --system) selected_system=$2 ;;
            --stage) selected_stage=$2 ;;
            --windows) window_range=$2 ;;
        esac
        shift 2
        ;;
    -h|--help)
        echo "Usage: ./run.sh [--preparation-only | --production-only] [--system complex|solvent] [--stage charge|vdw] [--windows START-END] [--dry-run]"
        echo
        echo "Run every RBFE environment and lambda window."
        echo
        echo "Options:"
        echo "  --preparation-only  Run through equilibration without production."
        echo "  --production-only   Run production from completed equilibration."
        echo "  --system NAME        Select complex or solvent."
        echo "  --stage NAME         Reserved for separated paths; this coupled RBFE protocol rejects it."
        echo "  --windows RANGE      Select an inclusive 0-based window range."
        echo "  --dry-run      Print engine commands without running them."
        echo "  -h, --help     Show this help message and exit."
        exit 0
        ;;
    *) echo "Error: unknown option: $1" >&2; exit 2 ;;
esac
done

die() {
    echo "Error: $*" >&2
    exit 1
}

if (( preparation_only && production_only )); then
    die "--preparation-only and --production-only cannot be used together"
fi
if [[ -n "$selected_system" && "$selected_system" != complex && "$selected_system" != solvent ]]; then
    die "--system must be complex or solvent"
fi
if [[ -n "$selected_stage" ]]; then
    die "The coupled RBFE protocol has no separate charge or vdw stage; --stage is available for ABFE."
fi
window_start=""; window_end=""
if [[ -n "$window_range" ]]; then
    if [[ ! "$window_range" =~ ^([0-9]+)-([0-9]+)$ ]]; then
        die "--windows must use START-END"
    fi
    window_start=$((10#${BASH_REMATCH[1]}))
    window_end=$((10#${BASH_REMATCH[2]}))
    if (( window_start > window_end )); then
        die "Window range start exceeds its end"
    fi
fi

work_dir=${WORK_DIR:-work}
states_file="$work_dir/states.tsv"
engine=${AMBER_ENGINE:-pmemd.cuda}
read -r -a amber_options <<< "${AMBER_OPTIONS:-}"

if [[ ! -s "$states_file" ]]; then
    die "Run build.sh first: $states_file"
fi
if [[ -n "$window_range" ]]; then
    maximum_window=$(awk -F '\t' -v system="$selected_system" '
        NR > 1 && (system == "" || $1 == system) {
            window = $2 + 0
            if (!found || window > maximum) maximum = window
            found = 1
        }
        END {if (found) print maximum}
    ' "$states_file")
    if [[ -z "$maximum_window" || "$window_end" -gt "$maximum_window" ]]; then
        die "Window range exceeds the selected RBFE state range: 0-${maximum_window:-none}"
    fi
fi
if (( ! dry_run )); then
    if ! command -v "$engine" >/dev/null 2>&1; then
        die "AMBER engine not found: $engine"
    fi
    if [[ "$(basename "$engine")" != "pmemd.cuda" ]]; then
        die "ACES26 soft-core inputs must run with pmemd.cuda: $engine"
    fi
fi

stage_state() {
    local marker=$1
    shift
    local existing=0
    local path
    for path in "$@"; do
        if [[ -s "$path" ]]; then
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
    local directory=$1
    local stage=$2
    local input_restart=$3
    local trajectory=$4
    local calculation=$5
    local prefix="$directory/$stage"
    local completion_marker="$directory/.$stage.complete"
    local required=("$prefix.out" "$prefix.rst7" "$prefix.info")
    local command=(
        "$engine" "${amber_options[@]}" -O
        -i "${stage%%.*}.in"
        -o "$stage.out"
        -p system.parm7
        -c "$input_restart"
        -r "$stage.rst7"
        -inf "$stage.info"
    )
    if [[ "$trajectory" == yes ]]; then
        required+=("$prefix.nc")
        command+=(-x "$stage.nc")
    fi

    if (( dry_run )); then
        printf '+ (cd %q && ' "$directory"
        printf '%q ' "${command[@]}"
        printf ')\n'
        return
    fi

    local state
    state=$(stage_state "$completion_marker" "${required[@]}")
    if [[ "$state" == complete ]]; then
        return
    fi
    if [[ "$state" == partial ]]; then
        case "$stage" in
            minimize|heat|equilibrate)
                echo "Warning: removing partial $stage output and restarting the stage: $prefix" >&2
                rm -f -- "$completion_marker" "${required[@]}"
                ;;
            *)
                die "Partial production output detected: $prefix"
                ;;
        esac
    fi
    echo "Running: $calculation - $stage"
    if ! (
        cd "$directory"
        "${command[@]}"
    ); then
        die "$stage calculation failed: $prefix.out"
    fi
    for output in "${required[@]}"; do
        if [[ ! -s "$output" ]]; then
            die "$stage output was not created: $output"
        fi
    done
    touch "$completion_marker"
}

if (( dry_run )); then
    window_count=$(awk 'NR > 1 {count++} END {print count + 0}' "$states_file")
    production_steps=$(awk -F' = ' '$1 == "production_steps_per_window" {print $2}' "$work_dir/resolved_config.toml")
    echo "RBFE: $window_count environment/window states, $production_steps production steps per window"
fi

selected_state_count=0
while IFS=$'\t' read -r environment window lambda seed directory; do
    if [[ "$environment" == environment ]]; then
        continue
    fi
    calculation="RBFE $environment window $window (lambda=$lambda)"
    if [[ -n "$selected_system" && "$environment" != "$selected_system" ]]; then
        continue
    fi
    window_index=$((10#$window))
    if [[ -n "$window_start" ]] && (( window_index < window_start || window_index > window_end )); then
        continue
    fi
    selected_state_count=$((selected_state_count + 1))
    if (( ! production_only )); then
        run_stage "$directory" minimize system.rst7 no "$calculation"
        run_stage "$directory" heat minimize.rst7 yes "$calculation"
        run_stage "$directory" equilibrate heat.rst7 yes "$calculation"
    fi
    if (( ! preparation_only )); then
        if (( ! dry_run )) && [[ ! -s "$directory/equilibrate.rst7" || ! -f "$directory/.equilibrate.complete" ]]; then
            die "Completed equilibration output is required: $directory"
        fi
        run_stage "$directory" production.001 equilibrate.rst7 yes "$calculation"
    fi
done < "$states_file"

if (( selected_state_count == 0 )); then
    die "No RBFE state matches the selected system and window range"
fi

if (( ! dry_run )); then
    echo "RBFE production completed: $work_dir/complex, $work_dir/solvent"
fi
