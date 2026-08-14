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
engine=${AMBER_ENGINE:-pmemd.cuda}
random_seed=${RANDOM_SEED:-41001}
production_segments=1
topology=system.parm7
read -r -a amber_options <<< "${AMBER_OPTIONS:-}"

if [[ ! "$random_seed" =~ ^[1-9][0-9]*$ ]]; then
    die "RANDOM_SEED must be a positive integer: $random_seed"
fi

if (( ! dry_run )); then
    if ! command -v "$engine" >/dev/null 2>&1; then
        die "AMBER engine not found: $engine"
    fi
    if [[ ! -s "$work_dir/system.parm7" || ! -s "$work_dir/system.rst7" ]]; then
        die "Run build.sh first: $work_dir"
    fi

    mkdir -p "$work_dir/inputs"
    cp inputs/minimize.in "$work_dir/inputs/minimize.in"
    cp inputs/equilibrate.in "$work_dir/inputs/equilibrate.in"
    cp inputs/gamd_prepare.in "$work_dir/inputs/gamd_prepare.in"
    cp inputs/production.in "$work_dir/inputs/production.in"

    sed "s/@RANDOM_SEED@/$random_seed/g" \
        inputs/heat.in.template \
        > "$work_dir/inputs/heat.in"
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

run_command() {
    local stage=$1
    shift

    if (( dry_run )); then
        printf '+ '
        printf '%q ' "$@"
        printf '\n'
        return
    fi

    echo "Running: $stage"
    if ! "$@"; then
        die "$stage calculation failed."
    fi
}

run_md_stage() {
    local stage=$1
    local input_file=$2
    local input_restart=$3
    shift 3
    local with_trajectory=no
    local with_gamd_log=no
    local reference_restart=""
    local gamd_state_input=""

    while [[ $# -gt 0 ]]; do
        case "$1" in
            --trajectory)
                with_trajectory=yes
                shift
                ;;
            --gamd-log)
                with_gamd_log=yes
                shift
                ;;
            --reference)
                reference_restart=$2
                shift 2
                ;;
            --gamd-state)
                gamd_state_input=$2
                shift 2
                ;;
            *)
                die "Unsupported run_md_stage option: $1"
                ;;
        esac
    done
    local prefix=$stage
    local completion_marker=".$stage.complete"
    local required=("$prefix.out" "$prefix.rst7" "$prefix.info")
    local command=(
        "$engine" "${amber_options[@]}" -O
        -i "$input_file"
        -o "$prefix.out"
        -p "$topology"
        -c "$input_restart"
        -r "$prefix.rst7"
        -inf "$prefix.info"
    )

    if [[ -n "$reference_restart" ]]; then
        command+=(-ref "$reference_restart")
    fi
    if [[ "$with_trajectory" == yes ]]; then
        required+=("$prefix.nc")
        command+=(-x "$prefix.nc")
    fi
    if [[ "$with_gamd_log" == yes ]]; then
        required+=("$prefix.gamd.log" "$prefix.gamd.rst")
        command+=(-gamd "$prefix.gamd.log")
    fi

    if (( dry_run )); then
        run_command "$stage" "${command[@]}"
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
                echo "Warning: removing partial $stage output and restarting the stage." >&2
                rm -f -- "$completion_marker" "${required[@]}"
                ;;
            *)
                die "Partial production or GaMD-state output detected for $stage."
                ;;
        esac
    fi

    if [[ -n "$gamd_state_input" ]]; then
        if [[ ! -s "$gamd_state_input" ]]; then
            die "Previous GaMD state not found: $gamd_state_input"
        fi
        cp "$gamd_state_input" gamd-restart.dat
    fi

    run_command "$stage" "${command[@]}"
    if [[ "$with_gamd_log" == yes ]]; then
        if [[ ! -s gamd-restart.dat ]]; then
            die "$stage GaMD state was not created: gamd-restart.dat"
        fi
        cp gamd-restart.dat "$prefix.gamd.rst"
    fi
    for output in "${required[@]}"; do
        if [[ ! -s "$output" ]]; then
            die "$stage Output was not created: $output"
        fi
    done
    touch "$completion_marker"
}

if (( dry_run )); then
    echo "Dual-boost GaMD: 200 ps heating + 100 ps NPT + 4 ns parameter preparation + 1 ns production"
    printf '+ cd %q\n' "$work_dir"
else
    cd "$work_dir"
fi

run_md_stage minimize inputs/minimize.in system.rst7
run_md_stage heat inputs/heat.in minimize.rst7 \
    --trajectory --reference minimize.rst7
run_md_stage equilibrate inputs/equilibrate.in heat.rst7 \
    --trajectory
run_md_stage gamd_prepare inputs/gamd_prepare.in equilibrate.rst7 \
    --trajectory --gamd-log

for segment_number in $(seq 1 "$production_segments"); do
    segment=$(printf 'production.%03d' "$segment_number")
    if [[ "$segment_number" -eq 1 ]]; then
        input_restart=gamd_prepare.rst7
        gamd_state_input=gamd_prepare.gamd.rst
    else
        input_restart=$(printf 'production.%03d.rst7' "$((segment_number - 1))")
        gamd_state_input=$(printf 'production.%03d.gamd.rst' "$((segment_number - 1))")
    fi
    run_md_stage "$segment" inputs/production.in "$input_restart" \
        --trajectory --gamd-log --gamd-state "$gamd_state_input"
done

if (( ! dry_run )); then
    echo "1 ns GaMD production completed."
fi
