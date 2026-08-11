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

work_dir=${WORK_DIR:-work}
states_file="$work_dir/states.tsv"
engine=${AMBER_ENGINE:-pmemd.cuda}
read -r -a amber_options <<< "${AMBER_OPTIONS:-}"

if [[ ! -s "$states_file" ]]; then
    die "Run build.sh first: $states_file"
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
    echo "ABFE: 65 restraint/charge/LJ windows, 1 ns production per window"
fi

while IFS=$'\t' read -r method_stage environment window lambda seed directory; do
    if [[ "$method_stage" == stage ]]; then
        continue
    fi
    interaction=${method_stage##*_}
    calculation="ABFE $interaction/$environment window $window (lambda=$lambda)"
    run_stage "$directory" minimize system.rst7 no "$calculation"
    run_stage "$directory" heat minimize.rst7 yes "$calculation"
    run_stage "$directory" equilibrate heat.rst7 yes "$calculation"
    run_stage "$directory" production.001 equilibrate.rst7 yes "$calculation"
done < "$states_file"

if (( ! dry_run )); then
    echo "ABFE production completed: $work_dir/restraint, $work_dir/charge, $work_dir/vdw"
fi
