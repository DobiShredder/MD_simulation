#!/usr/bin/env bash
set -euo pipefail

dry_run=0
allow_unverified=0

while [[ $# -gt 0 ]]; do
    case "$1" in
        --dry-run)
            dry_run=1
            ;;
        --allow-unverified)
            allow_unverified=1
            ;;
        *)
            echo "Usage: $0 [--dry-run] [--allow-unverified]" >&2
            exit 2
            ;;
    esac
    shift
done

die() {
    echo "Error: $*" >&2
    exit 1
}

work_dir=${WORK_DIR:-work}
states_file="$work_dir/states.tsv"
amber_engine=${AMBER_ENGINE:-pmemd.cuda}
amber_mpi_engine=${AMBER_MPI_ENGINE:-pmemd.cuda.MPI}
mpi_launcher=${MPI_LAUNCHER:-mpirun}
replica_count=20
mpi_processes=${MPI_PROCESSES:-$replica_count}
production_segments=1
gamd_reference_replica=009

read -r -a mpi_options <<< "${MPI_OPTIONS:-}"
read -r -a amber_options <<< "${AMBER_OPTIONS:-}"

if [[ ! -s "$states_file" ]]; then
    die "Run build.sh first: $states_file"
fi
if [[ "$mpi_processes" -ne "$replica_count" ]]; then
    die "MPI_PROCESSES must equal the window count: $replica_count"
fi
if (( ! dry_run && ! allow_unverified )); then
    die "GaMD state and multipmemd replica suffixes are not validated. Specify --allow-unverified to run."
fi

if (( ! dry_run )); then
    for executable in "$amber_engine" "$amber_mpi_engine" "$mpi_launcher"; do
        if ! command -v "$executable" >/dev/null 2>&1; then
            die "Executable not found: $executable"
        fi
    done
fi

source completion_helpers.sh

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

        if ! (
            cd "$replica_dir"
            "$amber_engine" \
                "${amber_options[@]}" \
                -O \
                -i "$stage.in" \
                -o "$stage.out" \
                -p system.parm7 \
                -c "$input_restart" \
                -r "$stage.rst7" \
                -x "$stage.nc" \
                -inf "$stage.info"
        ); then
            die "$stage Calculation failed: $replica_dir/$stage.out"
        fi
    done < "$states_file"
}

run_stage_if_needed() {
    local stage=$1
    local input_restart=$2
    local completed

    completed=$(completed_stage_count "$stage" --allow-partial)
    if [[ -f "$work_dir/.$stage.complete" && "$completed" -eq "$replica_count" ]]; then
        return
    fi
    if [[ "$completed" -ne 0 || -f "$work_dir/.$stage.complete" ]]; then
        echo "Warning: removing incomplete $stage output from all windows and restarting the stage." >&2
    fi
    remove_stage_outputs "$stage"
    run_stage "$stage" "$input_restart"

    completed=$(completed_stage_count "$stage")
    if [[ "$completed" -ne "$replica_count" ]]; then
        die "$stage output is incomplete ($completed/$replica_count)."
    fi
    touch "$work_dir/.$stage.complete"
}

prepare_common_gamd_state() {
    local reference_dir="$work_dir/$gamd_reference_replica"
    local completed_segments
    local existing=0
    local output
    local replica
    local replica_dir
    local required=(
        "$reference_dir/gamd_prepare.out"
        "$reference_dir/gamd_prepare.rst7"
        "$reference_dir/gamd_prepare.nc"
        "$reference_dir/gamd_prepare.info"
        "$reference_dir/gamd.prepare.log"
        "$reference_dir/gamd-restart.dat"
    )
    local completion_marker="$work_dir/.gamd_prepare.complete"

    completed_segments=$(completed_stage_count production.001 --require-gamd-log)
    if [[ "$completed_segments" -ne 0 ]]; then
        return
    fi

    for output in "${required[@]}"; do
        if [[ -s "$output" ]]; then
            existing=$((existing + 1))
        fi
    done
    if [[ -f "$completion_marker" && "$existing" -eq "${#required[@]}" ]]; then
        :
    elif [[ "$existing" -ne 0 ]]; then
        die "GaMD preparation output is only partially present: $reference_dir"
    else
        echo "Prepared shared GaMD parameters from replica $gamd_reference_replica."

        if ! (
            cd "$reference_dir"
            "$amber_engine" \
                "${amber_options[@]}" \
                -O \
                -i gamd_prepare.in \
                -o gamd_prepare.out \
                -p system.parm7 \
                -c equilibrate.rst7 \
                -r gamd_prepare.rst7 \
                -x gamd_prepare.nc \
                -inf gamd_prepare.info \
                -gamd gamd.prepare.log
        ); then
            die "GaMD parameter preparation failed: $reference_dir/gamd_prepare.out"
        fi
    fi

    if [[ ! -s "$reference_dir/gamd-restart.dat" ]]; then
        die "shared GaMD state was not created: $reference_dir/gamd-restart.dat"
    fi

    while IFS=$'\t' read -r replica _; do
        if [[ "$replica" == "replica" ]]; then
            continue
        fi

        replica_dir="$work_dir/$replica"
        if [[ "$replica" != "$gamd_reference_replica" ]]; then
            cp "$reference_dir/gamd-restart.dat" "$replica_dir/gamd-restart.dat"
        fi
        cp "$replica_dir/equilibrate.rst7" "$replica_dir/production_start.rst7"

        if ! cmp -s "$reference_dir/gamd-restart.dat" "$replica_dir/gamd-restart.dat"; then
            die "Could not place the shared GaMD state in replica: $replica_dir"
        fi
    done < "$states_file"
    touch "$completion_marker"
}

write_group_file() {
    local segment=$1
    local input_restart=$2
    local group_file=$3
    local segment_name
    local replica
    local replica_dir
    local dump_file
    local gamd_log
    local group_command

    segment_name=$(printf 'production.%03d' "$segment")
    : > "$group_file"

    while IFS=$'\t' read -r replica _; do
        if [[ "$replica" == "replica" ]]; then
            continue
        fi
        replica_dir="$work_dir/$replica"
        dump_file="$replica_dir/restraint.$segment_name.dat"
        gamd_log="$replica_dir/gamd.$segment_name.log"

        sed \
            -e "s|@DUMPAVE@|$dump_file|g" \
            "$replica_dir/production.template.in" \
            > "$replica_dir/$segment_name.in"

        group_command="-O -i $replica_dir/$segment_name.in"
        group_command+=" -o $replica_dir/$segment_name.out"
        group_command+=" -p $replica_dir/system.parm7"
        group_command+=" -c $replica_dir/$input_restart"
        group_command+=" -r $replica_dir/$segment_name.rst7"
        group_command+=" -x $replica_dir/$segment_name.nc"
        group_command+=" -inf $replica_dir/$segment_name.info"
        group_command+=" -gamd $gamd_log"

        printf '%s\n' "$group_command" >> "$group_file"
    done < "$states_file"
}

if (( dry_run )); then
    echo "Engine: $amber_engine"
    echo "Replica exchange engine: $amber_mpi_engine"
    echo "20 windows, 6–25 Å, 1 ps exchange interval"
    echo "200 ps heating + 100 ps equilibration + one shared 4 ns GaMD preparation"
    echo "1 ns GaREUS production, igamd=3, sigma0P=sigma0D=6.0"
    printf '%q ' \
        "$mpi_launcher" \
        "${mpi_options[@]}" \
        -np "$mpi_processes" \
        "$amber_mpi_engine" \
        "${amber_options[@]}" \
        -ng "$replica_count" \
        -groupfile "$work_dir/production.001.group" \
        -rem 3
    printf '\n'
    exit 0
fi

run_stage_if_needed minimize system.rst7
run_stage_if_needed heat minimize.rst7
run_stage_if_needed equilibrate heat.rst7
prepare_common_gamd_state

for segment in $(seq 1 "$production_segments"); do
    segment_name=$(printf 'production.%03d' "$segment")
    completed=$(completed_stage_count "$segment_name" --require-gamd-log)

    if [[ -f "$work_dir/.$segment_name.complete" && "$completed" -eq "$replica_count" ]]; then
        continue
    fi
    if [[ "$completed" -ne 0 ]]; then
        die "Partial production output detected: $segment_name"
    fi

    if [[ "$segment" -eq 1 ]]; then
        input_restart=production_start.rst7
    else
        input_restart=$(printf 'production.%03d.rst7' "$((segment - 1))")
    fi

    group_file="$work_dir/$segment_name.group"
    exchange_log="$work_dir/exchange.$(printf '%03d' "$segment").log"
    write_group_file "$segment" "$input_restart" "$group_file"

    echo "Running GaREUS production segment $segment/$production_segments."

    if ! "$mpi_launcher" \
        "${mpi_options[@]}" \
        -np "$mpi_processes" \
        "$amber_mpi_engine" \
        "${amber_options[@]}" \
        -ng "$replica_count" \
        -groupfile "$group_file" \
        -rem 3 \
        -remlog "$exchange_log"; then
        die "GaREUS segment $segment Run failed: $exchange_log"
    fi

    completed=$(completed_stage_count "$segment_name" --require-gamd-log)
    if [[ "$completed" -ne "$replica_count" ]]; then
        die "$segment_name output is incomplete ($completed/$replica_count)."
    fi
    touch "$work_dir/.$segment_name.complete"
done

echo "Completed 1 ns GaREUS: $work_dir"
