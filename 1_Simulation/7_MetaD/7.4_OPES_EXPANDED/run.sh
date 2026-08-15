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
plumed=${PLUMED:-plumed}
seed_base=${RANDOM_SEED:-74000}
read -r -a amber_options <<< "${AMBER_OPTIONS:-}"

[[ "$seed_base" =~ ^[1-9][0-9]*$ ]] || die "RANDOM_SEED must be a positive integer."
topology="$work_dir/system.parm7"
initial_restart="$work_dir/system.rst7"

stage_state() {
    local marker=$1
    shift
    local present=0
    local path
    for path in "$@"; do
        [[ -s "$path" ]] && present=$((present + 1))
    done
    if [[ -f "$marker" && "$present" -eq "$#" ]]; then
        echo complete
    elif [[ ! -f "$marker" && "$present" -eq 0 ]]; then
        echo missing
    else
        echo partial
    fi
}

render_amber_input() {
    local template=$1
    local output=$2
    local seed=$3
    sed "s/@RANDOM_SEED@/$seed/g" "$template" > "$output"
}

run_command() {
    local stage=$1
    local directory=$2
    shift 2
    if (( dry_run )); then
        printf '+ (cd %q && ' "$directory"
        printf '%q ' "$@"
        printf ')\n'
        return
    fi
    echo "Running: $stage"
    if ! (
        cd "$directory"
        "$@"
    ); then
        die "$stage Calculation failed: $directory"
    fi
}

run_standard_stage() {
    local stage=$1
    local input_file=$2
    local input_restart=$3
    shift 3
    local write_trajectory=0
    local reference_restart=
    local prefix="$work_dir/$stage"
    local completion_marker="$work_dir/.$stage.complete"
    local required=("$prefix.out" "$prefix.info" "$prefix.rst7")
    local command=(
        "$engine" "${amber_options[@]}" -O
        -i "$input_file" -o "$stage.out"
        -p system.parm7 -c "$input_restart"
        -r "$stage.rst7" -inf "$stage.info"
    )
    local state

    while (( $# > 0 )); do
        case "$1" in
            --trajectory)
                write_trajectory=1
                shift
                ;;
            --reference)
                [[ $# -ge 2 ]] || die "--reference requires a restart file."
                reference_restart=$2
                shift 2
                ;;
            *)
                die "Unknown run_standard_stage option: $1"
                ;;
        esac
    done

    if (( write_trajectory )); then
        required+=("$prefix.nc")
        command+=(-x "$stage.nc")
    fi
    if [[ -n "$reference_restart" ]]; then
        command+=(-ref "$reference_restart")
    fi
    if (( ! dry_run )); then
        state=$(stage_state "$completion_marker" "${required[@]}")
        [[ "$state" != complete ]] || return 0
        if [[ "$state" == partial ]]; then
            echo "Warning: removing partial $stage output and restarting the stage." >&2
            rm -f -- "$completion_marker" "${required[@]}"
        fi
    fi
    run_command "$stage" "$work_dir" "${command[@]}"
    if (( ! dry_run )); then
        for output in "${required[@]}"; do
            [[ -s "$output" ]] || die "$stage Output not found: $output"
        done
        touch "$completion_marker"
    fi
}

render_plumed_input() {
    local output=$1
    sed \
        -e 's/@RESTART@//' \
        -e 's/@STATE_RFILE@//' \
        inputs/plumed.dat.template \
        > "$output"
}

run_production() {
    local completion_marker="$work_dir/.production.complete"
    local state
    local required=(
        "$work_dir/production.out" "$work_dir/production.info"
        "$work_dir/production.rst7" "$work_dir/production.nc"
        "$work_dir/COLVAR" "$work_dir/DELTAFS"
        "$work_dir/opes.state"
    )

    if (( ! dry_run )); then
        state=$(stage_state "$completion_marker" "${required[@]}")
        [[ "$state" != complete ]] || return 0
        [[ "$state" != partial ]] || die "production Partial output detected: $work_dir"
        render_amber_input inputs/production.in.template \
            "$work_dir/production.in" "$((seed_base + 101))"
        render_plumed_input "$work_dir/plumed.dat"
    fi

    run_command "production" "$work_dir" \
        "$engine" "${amber_options[@]}" -O \
        -i production.in -o production.out \
        -p system.parm7 -c equilibrate.rst7 \
        -r production.rst7 -x production.nc -inf production.info

    if (( ! dry_run )); then
        for output in "${required[@]}"; do
            [[ -s "$output" ]] || die "production Output not found: $output"
        done
        touch "$completion_marker"
    fi
}

if (( ! dry_run )); then
    command -v "$engine" >/dev/null 2>&1 || die "AMBER engine not found: $engine"
    command -v "$plumed" >/dev/null 2>&1 || die "PLUMED not found: $plumed"
    [[ -s "$topology" && -s "$initial_restart" ]] || die "Run build.sh first. $work_dir"
    [[ -s "$work_dir/atom_count.txt" ]] || die "atom_count.txt not found. Run build.sh again."
    mkdir -p "$work_dir"
    mkdir -p "$work_dir/inputs"
    cp inputs/minimize.in "$work_dir/inputs/minimize.in"
    render_amber_input inputs/heat.in.template "$work_dir/inputs/heat.in" "$((seed_base + 1))"
    render_amber_input inputs/equilibrate.in.template "$work_dir/inputs/equilibrate.in" "$((seed_base + 2))"
    render_plumed_input "$work_dir/plumed.parse.dat"
    atom_count=$(<"$work_dir/atom_count.txt")
    (
        cd "$work_dir"
        "$plumed" driver \
            --plumed plumed.parse.dat \
            --parse-only \
            --natoms "$atom_count"
    )
fi

run_standard_stage minimize inputs/minimize.in system.rst7
run_standard_stage heat inputs/heat.in minimize.rst7 --trajectory --reference minimize.rst7
run_standard_stage equilibrate inputs/equilibrate.in heat.rst7 --trajectory

run_production

if (( ! dry_run )); then
    echo "1 ns OPES Expanded production Completed: $work_dir"
fi
