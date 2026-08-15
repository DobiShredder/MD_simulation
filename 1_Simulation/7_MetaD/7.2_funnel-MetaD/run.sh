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
seed_base=${RANDOM_SEED:-72000}
read -r -a amber_options <<< "${AMBER_OPTIONS:-}"

if [[ ! "$seed_base" =~ ^[1-9][0-9]*$ ]]; then
    die "RANDOM_SEED must be a positive integer."
fi

topology="$work_dir/system.parm7"
initial_restart="$work_dir/system.rst7"
funnel_grid="$work_dir/FUNNEL_GRID"

stage_state() {
    local marker=$1
    shift
    local present=0
    local path

    for path in "$@"; do
        if [[ -s "$path" ]]; then
            present=$((present + 1))
        fi
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

check_plumed_action() {
    local action=$1

    if ! "$plumed" manual --action "$action" >/dev/null 2>&1; then
        die "PLUMED action $action is unavailable. Rebuild PLUMED 2.10 with ./configure --enable-modules=funnel and ensure that the AMBER engine uses that PLUMED kernel."
    fi
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
        -i "$input_file"
        -o "$stage.out"
        -p system.parm7
        -c "$input_restart"
        -r "$stage.rst7"
        -inf "$stage.info"
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
        if [[ "$state" == complete ]]; then
            return 0
        fi
        if [[ "$state" == partial ]]; then
            echo "Warning: removing partial $stage output and restarting the stage." >&2
            rm -f -- "$completion_marker" "${required[@]}"
        fi
    fi

    run_command "$stage" "$work_dir" "${command[@]}"

    if (( ! dry_run )); then
        for output in "${required[@]}"; do
            if [[ ! -s "$output" ]]; then
                die "$stage Output not found: $output"
            fi
        done
        touch "$completion_marker"
    fi
}

run_production() {
    local completion_marker="$work_dir/.production.complete"
    local state
    local required=(
        "$work_dir/production.out"
        "$work_dir/production.info"
        "$work_dir/production.rst7"
        "$work_dir/production.nc"
        "$work_dir/COLVAR"
        "$work_dir/HILLS"
    )

    if (( ! dry_run )); then
        state=$(stage_state "$completion_marker" "${required[@]}")
        if [[ "$state" == complete ]]; then
            return 0
        fi
        if [[ "$state" == partial ]]; then
            die "production Partial output detected: $work_dir"
        fi

        render_amber_input \
            inputs/production.in.template \
            "$work_dir/production.in" \
            "$((seed_base + 101))"
    fi

    run_command "production" "$work_dir" \
        "$engine" "${amber_options[@]}" -O \
        -i production.in \
        -o production.out \
        -p system.parm7 \
        -c equilibrate.rst7 \
        -r production.rst7 \
        -x production.nc \
        -inf production.info

    if (( ! dry_run )); then
        for output in "${required[@]}"; do
            if [[ ! -s "$output" ]]; then
                die "production Output not found: $output"
            fi
        done
        touch "$completion_marker"
    fi
}

if (( ! dry_run )); then
    for executable in "$engine" "$plumed"; do
        if ! command -v "$executable" >/dev/null 2>&1; then
            die "Executable not found: $executable"
        fi
    done

    check_plumed_action FUNNEL_PS
    check_plumed_action FUNNEL

    for input in \
        "$topology" \
        "$initial_restart" \
        "$work_dir/funnel-reference.pdb" \
        "$work_dir/plumed.dat" \
        "$work_dir/atom_count.txt"; do
        if [[ ! -s "$input" ]]; then
            die "Run build.sh first. $input"
        fi
    done

    mkdir -p "$work_dir/inputs"
    cp inputs/minimize-solvent.in "$work_dir/inputs/minimize-solvent.in"
    cp inputs/minimize-all.in "$work_dir/inputs/minimize-all.in"
    render_amber_input inputs/heat.in.template "$work_dir/inputs/heat.in" "$((seed_base + 1))"
    render_amber_input inputs/equilibrate.in.template "$work_dir/inputs/equilibrate.in" "$((seed_base + 2))"

    atom_count=$(<"$work_dir/atom_count.txt")
    (
        cd "$work_dir"
        "$plumed" driver \
            --plumed plumed.dat \
            --parse-only \
            --natoms "$atom_count"
    )
    if [[ ! -s "$funnel_grid" ]]; then
        die "PLUMED setup did not create the funnel grid: $funnel_grid"
    fi
fi

run_standard_stage minimize-solvent inputs/minimize-solvent.in system.rst7 --reference system.rst7
run_standard_stage minimize-all inputs/minimize-all.in minimize-solvent.rst7
run_standard_stage heat inputs/heat.in minimize-all.rst7 --trajectory --reference minimize-all.rst7
run_standard_stage equilibrate inputs/equilibrate.in heat.rst7 --trajectory --reference heat.rst7

run_production

if (( ! dry_run )); then
    echo "1 ns Funnel MetaD production Completed: $work_dir"
fi
