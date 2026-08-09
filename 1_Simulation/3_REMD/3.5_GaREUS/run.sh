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

script_dir=$(dirname "${BASH_SOURCE[0]}")
work_dir=${WORK_DIR:-"$script_dir/work"}
states_file="$work_dir/states.tsv"
amber_engine=${AMBER_ENGINE:-pmemd.cuda}
amber_mpi_engine=${AMBER_MPI_ENGINE:-pmemd.cuda.MPI}
mpi_launcher=${MPI_LAUNCHER:-mpirun}
replica_count=20
mpi_processes=${MPI_PROCESSES:-$replica_count}
production_segments=10
gamd_reference_replica=009

read -r -a mpi_options <<< "${MPI_OPTIONS:-}"
read -r -a amber_options <<< "${AMBER_OPTIONS:-}"

if [[ ! -s "$states_file" ]]; then
    die "build.sh를 먼저 실행해야 합니다: $states_file"
fi
if [[ "$mpi_processes" -ne "$replica_count" ]]; then
    die "MPI_PROCESSES는 window 수와 같아야 합니다: $replica_count"
fi
if (( ! dry_run )) && [[ "${ALLOW_UNVERIFIED_GAREUS:-0}" != 1 ]]; then
    die "GaMD state와 multipmemd replica suffix 검증 전입니다. 실행하려면 ALLOW_UNVERIFIED_GAREUS=1을 지정하세요."
fi

if (( ! dry_run )); then
    for executable in "$amber_engine" "$amber_mpi_engine" "$mpi_launcher"; do
        if ! command -v "$executable" >/dev/null 2>&1; then
            die "실행 파일을 찾을 수 없습니다: $executable"
        fi
    done
fi

completed_stage_count() {
    local stage=$1
    local require_gamd_log=${2:-no}
    local completed=0
    local existing
    local replica
    local replica_dir
    local required

    while IFS=$'\t' read -r replica _; do
        if [[ "$replica" == "replica" ]]; then
            continue
        fi

        replica_dir="$work_dir/replicas/$replica"
        required=(
            "$replica_dir/$stage.out"
            "$replica_dir/$stage.rst7"
            "$replica_dir/$stage.nc"
            "$replica_dir/$stage.info"
        )
        if [[ "$require_gamd_log" == yes ]]; then
            required+=("$replica_dir/gamd.$stage.log")
        fi

        existing=0
        for output in "${required[@]}"; do
            if [[ -s "$output" ]]; then
                existing=$((existing + 1))
            fi
        done

        if [[ "$existing" -eq "${#required[@]}" ]]; then
            completed=$((completed + 1))
        elif [[ "$existing" -ne 0 ]]; then
            die "$stage output이 일부만 존재합니다: $replica_dir"
        fi
    done < "$states_file"

    echo "$completed"
}

run_stage() {
    local stage=$1
    local input_restart=$2
    local replica
    local replica_dir

    echo "$stage stage를 실행합니다."

    while IFS=$'\t' read -r replica _; do
        if [[ "$replica" == "replica" ]]; then
            continue
        fi
        replica_dir="$work_dir/replicas/$replica"

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
            die "$stage 계산에 실패했습니다: $replica_dir/$stage.out"
        fi
    done < "$states_file"
}

run_stage_if_needed() {
    local stage=$1
    local input_restart=$2
    local completed

    completed=$(completed_stage_count "$stage")
    if [[ "$completed" -eq "$replica_count" ]]; then
        return
    fi
    if [[ "$completed" -ne 0 ]]; then
        die "$stage stage가 일부 window에서만 완료되었습니다 ($completed/$replica_count)."
    fi
    run_stage "$stage" "$input_restart"

    completed=$(completed_stage_count "$stage")
    if [[ "$completed" -ne "$replica_count" ]]; then
        die "$stage output이 완성되지 않았습니다 ($completed/$replica_count)."
    fi
}

prepare_common_gamd_state() {
    local reference_dir="$work_dir/replicas/$gamd_reference_replica"
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

    completed_segments=$(completed_stage_count production.001 yes)
    if [[ "$completed_segments" -ne 0 ]]; then
        return
    fi

    for output in "${required[@]}"; do
        if [[ -s "$output" ]]; then
            existing=$((existing + 1))
        fi
    done
    if [[ "$existing" -ne 0 && "$existing" -ne "${#required[@]}" ]]; then
        die "GaMD preparation output이 일부만 존재합니다: $reference_dir"
    fi

    if [[ "$existing" -eq 0 ]]; then
        echo "Replica $gamd_reference_replica 에서 공통 GaMD parameter를 준비합니다."

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
            die "GaMD parameter preparation에 실패했습니다: $reference_dir/gamd_prepare.out"
        fi
    fi

    if [[ ! -s "$reference_dir/gamd-restart.dat" ]]; then
        die "공통 GaMD state가 생성되지 않았습니다: $reference_dir/gamd-restart.dat"
    fi

    while IFS=$'\t' read -r replica _; do
        if [[ "$replica" == "replica" ]]; then
            continue
        fi

        replica_dir="$work_dir/replicas/$replica"
        if [[ "$replica" != "$gamd_reference_replica" ]]; then
            cp "$reference_dir/gamd-restart.dat" "$replica_dir/gamd-restart.dat"
        fi
        cp "$replica_dir/equilibrate.rst7" "$replica_dir/production_start.rst7"

        if ! cmp -s "$reference_dir/gamd-restart.dat" "$replica_dir/gamd-restart.dat"; then
            die "replica에 공통 GaMD state를 배치하지 못했습니다: $replica_dir"
        fi
    done < "$states_file"
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
        replica_dir="$work_dir/replicas/$replica"
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
    echo "200 ps heating + 1 ns equilibration + one shared 4 ns GaMD preparation"
    echo "10 × 1 ns GaREUS production, igamd=3, sigma0P=sigma0D=6.0"
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
    completed=$(completed_stage_count "$segment_name" yes)

    if [[ "$completed" -eq "$replica_count" ]]; then
        continue
    fi
    if [[ "$completed" -ne 0 ]]; then
        die "$segment_name segment가 일부 window에서만 완료되었습니다 ($completed/$replica_count)."
    fi

    if [[ "$segment" -eq 1 ]]; then
        input_restart=production_start.rst7
    else
        input_restart=$(printf 'production.%03d.rst7' "$((segment - 1))")
    fi

    group_file="$work_dir/$segment_name.group"
    exchange_log="$work_dir/exchange.$(printf '%03d' "$segment").log"
    write_group_file "$segment" "$input_restart" "$group_file"

    echo "GaREUS production segment $segment/$production_segments 을 실행합니다."

    if ! "$mpi_launcher" \
        "${mpi_options[@]}" \
        -np "$mpi_processes" \
        "$amber_mpi_engine" \
        "${amber_options[@]}" \
        -ng "$replica_count" \
        -groupfile "$group_file" \
        -rem 3 \
        -remlog "$exchange_log"; then
        die "GaREUS segment $segment 실행에 실패했습니다: $exchange_log"
    fi

    completed=$(completed_stage_count "$segment_name" yes)
    if [[ "$completed" -ne "$replica_count" ]]; then
        die "$segment_name output이 완성되지 않았습니다 ($completed/$replica_count)."
    fi
done

echo "10 ns GaREUS가 완료되었습니다: $work_dir/replicas"
