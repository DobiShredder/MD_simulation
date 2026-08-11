#!/usr/bin/env bash
set -euo pipefail

dry_run=0

if [[ "${1:-}" == "--dry-run" ]]; then
    dry_run=1
    shift
fi

if [[ $# -ne 0 ]]; then
    echo "사용법: $0 [--dry-run]" >&2
    exit 2
fi

die() {
    echo "오류: $*" >&2
    exit 1
}

work_dir=${WORK_DIR:-work}
states_file="$work_dir/states.tsv"
amber_engine=${AMBER_ENGINE:-pmemd.cuda}
amber_mpi_engine=${AMBER_MPI_ENGINE:-pmemd.cuda.MPI}
mpi_launcher=${MPI_LAUNCHER:-mpirun}
replica_count=20
production_segments=1
mpi_processes=${MPI_PROCESSES:-$replica_count}

read -r -a mpi_options <<< "${MPI_OPTIONS:-}"
read -r -a amber_options <<< "${AMBER_OPTIONS:-}"

if [[ ! -s "$states_file" ]]; then
    die "build.sh를 먼저 실행해야 합니다: $states_file"
fi

if [[ "$mpi_processes" -ne "$replica_count" ]]; then
    die "MPI_PROCESSES는 replica 수와 같아야 합니다: $replica_count"
fi

if (( ! dry_run )); then
    for executable in "$amber_engine" "$amber_mpi_engine" "$mpi_launcher"; do
        if ! command -v "$executable" >/dev/null 2>&1; then
            die "실행 파일을 찾을 수 없습니다: $executable"
        fi
    done
fi

stage_status() {
    local filename=$1
    local completed=0
    local replica

    while IFS=$'\t' read -r replica _; do
        if [[ "$replica" == "replica" ]]; then
            continue
        fi

        if [[ -s "$work_dir/$replica/$filename" ]]; then
            completed=$((completed + 1))
        fi
    done < "$states_file"

    echo "$completed"
}

run_single_replica_stage() {
    local stage=$1
    local input_restart=$2
    local replica
    local replica_dir

    echo "$stage stage를 실행합니다."

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
            die "$stage 계산에 실패했습니다: $replica_dir/$stage.out"
        fi
    done < "$states_file"
}

run_stage_if_needed() {
    local stage=$1
    local input_restart=$2
    local completed

    completed=$(stage_status "$stage.rst7")

    if [[ "$completed" -eq "$replica_count" ]]; then
        return
    fi

    if [[ "$completed" -ne 0 ]]; then
        die "$stage stage가 일부 replica에서만 완료되었습니다 ($completed/$replica_count)."
    fi

    run_single_replica_stage "$stage" "$input_restart"
}

write_group_file() {
    local segment=$1
    local input_restart=$2
    local group_file=$3
    local replica
    local replica_dir
    local segment_name

    segment_name=$(printf 'production.%03d' "$segment")
    : > "$group_file"

    while IFS=$'\t' read -r replica _; do
        if [[ "$replica" == "replica" ]]; then
            continue
        fi

        replica_dir="$work_dir/$replica"
        printf '%s\n' \
            "-O -i $replica_dir/production.in -o $replica_dir/$segment_name.out -p $replica_dir/system.parm7 -c $replica_dir/$input_restart -r $replica_dir/$segment_name.rst7 -x $replica_dir/$segment_name.nc -inf $replica_dir/$segment_name.info" \
            >> "$group_file"
    done < "$states_file"
}

if (( dry_run )); then
    echo "Engine: $amber_engine"
    echo "Replica exchange engine: $amber_mpi_engine"
    echo "20 replicas, 300–373 K, 1 ps exchange interval"
    echo "200 ps heating + 100 ps equilibration + 1 ns production"
    printf '%q ' "$mpi_launcher" "${mpi_options[@]}" -np "$mpi_processes" "$amber_mpi_engine" "${amber_options[@]}" -ng "$replica_count" -groupfile "$work_dir/production.001.group" -rem 1
    printf '\n'
    exit 0
fi

run_stage_if_needed minimize system.rst7
run_stage_if_needed heat minimize.rst7
run_stage_if_needed equilibrate heat.rst7

for segment in $(seq 1 "$production_segments"); do
    segment_name=$(printf 'production.%03d' "$segment")
    completed=$(stage_status "$segment_name.rst7")

    if [[ "$completed" -eq "$replica_count" ]]; then
        continue
    fi

    if [[ "$completed" -ne 0 ]]; then
        die "$segment_name segment가 일부 replica에서만 완료되었습니다 ($completed/$replica_count)."
    fi

    if [[ "$segment" -eq 1 ]]; then
        input_restart="equilibrate.rst7"
    else
        previous_segment=$(printf 'production.%03d.rst7' "$((segment - 1))")
        input_restart="$previous_segment"
    fi

    group_file="$work_dir/$segment_name.group"
    exchange_log="$work_dir/exchange.$(printf '%03d' "$segment").log"
    write_group_file "$segment" "$input_restart" "$group_file"

    echo "T-REMD production segment $segment/$production_segments 을 실행합니다."

    if ! "$mpi_launcher" \
        "${mpi_options[@]}" \
        -np "$mpi_processes" \
        "$amber_mpi_engine" \
        "${amber_options[@]}" \
        -ng "$replica_count" \
        -groupfile "$group_file" \
        -rem 1 \
        -remlog "$exchange_log"; then
        die "T-REMD segment $segment 실행에 실패했습니다: $exchange_log"
    fi
done

echo "1 ns T-REMD가 완료되었습니다: $work_dir"
