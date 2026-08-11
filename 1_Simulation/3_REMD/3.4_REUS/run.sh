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
amber_engine=${AMBER_ENGINE:-pmemd.cuda}
amber_mpi_engine=${AMBER_MPI_ENGINE:-pmemd.cuda.MPI}
mpi_launcher=${MPI_LAUNCHER:-mpirun}
replica_count=19
mpi_processes=${MPI_PROCESSES:-$replica_count}
production_segments=1

read -r -a mpi_options <<< "${MPI_OPTIONS:-}"
read -r -a amber_options <<< "${AMBER_OPTIONS:-}"

if [[ ! -s "$states_file" ]]; then
    die "Run build.sh first: $states_file"
fi
if [[ "$mpi_processes" -ne "$replica_count" ]]; then
    die "MPI_PROCESSES must equal the window count: $replica_count"
fi

if (( ! dry_run )); then
    for executable in "$amber_engine" "$amber_mpi_engine" "$mpi_launcher"; do
        if ! command -v "$executable" >/dev/null 2>&1; then
            die "Executable not found: $executable"
        fi
    done
fi

stage_state() {
    local stage=$1
    local marker="$work_dir/.$stage.complete"
    local existing=0
    local expected=$((replica_count * 4))
    local replica
    local suffix

    while IFS=$'\t' read -r replica _; do
        if [[ "$replica" == "replica" ]]; then
            continue
        fi
        for suffix in out rst7 info nc; do
            [[ ! -s "$work_dir/$replica/$stage.$suffix" ]] || existing=$((existing + 1))
        done
    done < "$states_file"
    if [[ -f "$marker" && "$existing" -eq "$expected" ]]; then
        echo complete
    elif [[ ! -f "$marker" && "$existing" -eq 0 ]]; then
        echo missing
    else
        echo partial
    fi
}

remove_stage_outputs() {
    local stage=$1
    local replica
    rm -f -- "$work_dir/.$stage.complete"
    while IFS=$'\t' read -r replica _; do
        [[ "$replica" != replica ]] || continue
        rm -f -- "$work_dir/$replica/$stage.out" "$work_dir/$replica/$stage.rst7" \
            "$work_dir/$replica/$stage.info" "$work_dir/$replica/$stage.nc"
    done < "$states_file"
}

mark_stage_complete() {
    local stage=$1
    local replica
    local suffix
    while IFS=$'\t' read -r replica _; do
        [[ "$replica" != replica ]] || continue
        for suffix in out rst7 info nc; do
            [[ -s "$work_dir/$replica/$stage.$suffix" ]] || \
                die "$stage output is incomplete: $work_dir/$replica/$stage.$suffix"
        done
    done < "$states_file"
    touch "$work_dir/.$stage.complete"
}

run_stage() {
    local stage=$1
    local input_restart=$2
    local replica
    local replica_dir

    echo "Running $stage stage."

    while IFS=$'\t' read -r replica _; do
        if [[ "$replica" == "replica" ]]; then
            continue
        fi
        replica_dir="$work_dir/$replica"

        if ! "$amber_engine" \
            "${amber_options[@]}" \
            -O \
            -i "$replica_dir/$stage.in" \
            -o "$replica_dir/$stage.out" \
            -p "$replica_dir/system.parm7" \
            -c "$replica_dir/$input_restart" \
            -r "$replica_dir/$stage.rst7" \
            -x "$replica_dir/$stage.nc" \
            -inf "$replica_dir/$stage.info"; then
            die "$stage Calculation failed: $replica_dir/$stage.out"
        fi
    done < "$states_file"
    mark_stage_complete "$stage"
}

run_stage_if_needed() {
    local stage=$1
    local input_restart=$2
    local state
    state=$(stage_state "$stage")
    if [[ "$state" == complete ]]; then
        return
    fi
    if [[ "$state" == partial ]]; then
        echo "Warning: removing partial $stage output from all windows and restarting the stage." >&2
        remove_stage_outputs "$stage"
    fi
    run_stage "$stage" "$input_restart"
}

write_group_file() {
    local segment=$1
    local input_restart=$2
    local group_file=$3
    local segment_name
    local replica
    local replica_dir
    local dump_file

    segment_name=$(printf 'production.%03d' "$segment")
    : > "$group_file"

    while IFS=$'\t' read -r replica _; do
        if [[ "$replica" == "replica" ]]; then
            continue
        fi
        replica_dir="$work_dir/$replica"
        dump_file="$replica_dir/restraint.$segment_name.dat"

        sed \
            -e "s|@DUMPAVE@|$dump_file|g" \
            "$replica_dir/production.template.in" \
            > "$replica_dir/$segment_name.in"

        printf '%s\n' \
            "-O -i $replica_dir/$segment_name.in -o $replica_dir/$segment_name.out -p $replica_dir/system.parm7 -c $replica_dir/$input_restart -r $replica_dir/$segment_name.rst7 -x $replica_dir/$segment_name.nc -inf $replica_dir/$segment_name.info" \
            >> "$group_file"
    done < "$states_file"
}

if (( dry_run )); then
    echo "Engine: $amber_engine"
    echo "Replica exchange engine: $amber_mpi_engine"
    echo "19 windows, 6–24 Å, 1 ps exchange interval"
    echo "200 ps heating + 100 ps equilibration + 1 ns production"
    printf '%q ' "$mpi_launcher" "${mpi_options[@]}" -np "$mpi_processes" "$amber_mpi_engine" "${amber_options[@]}" -ng "$replica_count" -groupfile "$work_dir/production.001.group" -rem 3
    printf '\n'
    exit 0
fi

run_stage_if_needed minimize system.rst7
run_stage_if_needed heat minimize.rst7
run_stage_if_needed equilibrate heat.rst7

for segment in $(seq 1 "$production_segments"); do
    segment_name=$(printf 'production.%03d' "$segment")
    state=$(stage_state "$segment_name")
    if [[ "$state" == complete ]]; then
        continue
    fi
    if [[ "$state" == partial ]]; then
        die "Partial production output detected: $segment_name"
    fi

    if [[ "$segment" -eq 1 ]]; then
        input_restart=equilibrate.rst7
    else
        input_restart=$(printf 'production.%03d.rst7' "$((segment - 1))")
    fi

    group_file="$work_dir/$segment_name.group"
    exchange_log="$work_dir/exchange.$(printf '%03d' "$segment").log"
    write_group_file "$segment" "$input_restart" "$group_file"

    echo "Running REUS production segment $segment/$production_segments."

    if ! "$mpi_launcher" \
        "${mpi_options[@]}" \
        -np "$mpi_processes" \
        "$amber_mpi_engine" \
        "${amber_options[@]}" \
        -ng "$replica_count" \
        -groupfile "$group_file" \
        -rem 3 \
        -remlog "$exchange_log"; then
        die "REUS segment $segment Run failed: $exchange_log"
    fi
    mark_stage_complete "$segment_name"
done

echo "Completed 1 ns REUS: $work_dir"
