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

script_dir=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
work_dir=${WORK_DIR:-"$script_dir/work"}
states_file="$work_dir/states.tsv"
gmx=${GROMACS:-gmx}
gmx_mpi=${GROMACS_MPI:-gmx_mpi}
mpi_launcher=${MPI_LAUNCHER:-mpirun}
replica_count=8
mpi_processes=${MPI_PROCESSES:-$replica_count}
production_segments=10
exchange_steps=1000

read -r -a mpi_options <<< "${MPI_OPTIONS:-}"
read -r -a gromacs_options <<< "${GROMACS_OPTIONS:-}"

if [[ ! -s "$states_file" ]]; then
    die "build.sh를 먼저 실행해야 합니다: $states_file"
fi

if [[ "$mpi_processes" -ne "$replica_count" ]]; then
    die "MPI_PROCESSES는 replica 수와 같아야 합니다: $replica_count"
fi

if (( ! dry_run )); then
    for executable in "$gmx" "$gmx_mpi" "$mpi_launcher"; do
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
        if [[ -s "$work_dir/replicas/$replica/$filename" ]]; then
            completed=$((completed + 1))
        fi
    done < "$states_file"

    echo "$completed"
}

run_preproduction() {
    local replica
    local replica_dir

    echo "Minimization과 1 ns equilibration을 실행합니다."

    while IFS=$'\t' read -r replica _; do
        if [[ "$replica" == "replica" ]]; then
            continue
        fi
        replica_dir="$work_dir/replicas/$replica"

        if ! "$gmx" grompp \
            -f "$replica_dir/minimize.mdp" \
            -p "$replica_dir/topol.top" \
            -c "$replica_dir/system.gro" \
            -o "$replica_dir/minimize.tpr" \
            > "$replica_dir/minimize.grompp.log" 2>&1; then
            die "minimization tpr 생성에 실패했습니다: $replica_dir/minimize.grompp.log"
        fi

        if ! "$gmx" mdrun \
            -deffnm "$replica_dir/minimize" \
            "${gromacs_options[@]}" \
            > "$replica_dir/minimize.mdrun.log" 2>&1; then
            die "minimization에 실패했습니다: $replica_dir/minimize.mdrun.log"
        fi

        if ! "$gmx" grompp \
            -f "$replica_dir/equilibrate.mdp" \
            -p "$replica_dir/topol.top" \
            -c "$replica_dir/minimize.gro" \
            -o "$replica_dir/equilibrate.tpr" \
            > "$replica_dir/equilibrate.grompp.log" 2>&1; then
            die "equilibration tpr 생성에 실패했습니다: $replica_dir/equilibrate.grompp.log"
        fi

        if ! "$gmx" mdrun \
            -deffnm "$replica_dir/equilibrate" \
            "${gromacs_options[@]}" \
            > "$replica_dir/equilibrate.mdrun.log" 2>&1; then
            die "equilibration에 실패했습니다: $replica_dir/equilibrate.mdrun.log"
        fi
    done < "$states_file"
}

if (( dry_run )); then
    echo "GROMACS: $gmx"
    echo "HREX engine: $gmx_mpi"
    echo "8 replicas, effective 300–500 K, 2 ps exchange interval"
    echo "1 ns equilibration + 10 × 1 ns production"
    printf '%q ' "$mpi_launcher" "${mpi_options[@]}" -np "$mpi_processes" "$gmx_mpi" mdrun -multidir "$work_dir/replicas/000" ... "$work_dir/replicas/007" -deffnm production.001 -hrex -replex "$exchange_steps" -plumed plumed.dat
    printf '\n'
    exit 0
fi

equilibrated=$(stage_status equilibrate.cpt)
if [[ "$equilibrated" -eq 0 ]]; then
    run_preproduction
elif [[ "$equilibrated" -ne "$replica_count" ]]; then
    die "equilibration이 일부 replica에서만 완료되었습니다 ($equilibrated/$replica_count)."
fi

replica_dirs=()
while IFS=$'\t' read -r replica _; do
    if [[ "$replica" == "replica" ]]; then
        continue
    fi
    replica_dirs+=("$work_dir/replicas/$replica")
done < "$states_file"

for segment in $(seq 1 "$production_segments"); do
    segment_name=$(printf 'production.%03d' "$segment")
    completed=$(stage_status "$segment_name.cpt")

    if [[ "$completed" -eq "$replica_count" ]]; then
        continue
    fi

    if [[ "$completed" -ne 0 ]]; then
        die "$segment_name segment가 일부 replica에서만 완료되었습니다 ($completed/$replica_count)."
    fi

    if [[ "$segment" -eq 1 ]]; then
        previous_name=equilibrate
    else
        previous_name=$(printf 'production.%03d' "$((segment - 1))")
    fi

    while IFS=$'\t' read -r replica _; do
        if [[ "$replica" == "replica" ]]; then
            continue
        fi
        replica_dir="$work_dir/replicas/$replica"

        if ! "$gmx" grompp \
            -f "$replica_dir/production.mdp" \
            -p "$replica_dir/topol.top" \
            -c "$replica_dir/$previous_name.gro" \
            -t "$replica_dir/$previous_name.cpt" \
            -o "$replica_dir/$segment_name.tpr" \
            > "$replica_dir/$segment_name.grompp.log" 2>&1; then
            die "production tpr 생성에 실패했습니다: $replica_dir/$segment_name.grompp.log"
        fi
    done < "$states_file"

    echo "REST2 production segment $segment/$production_segments 을 실행합니다."

    if ! "$mpi_launcher" \
        "${mpi_options[@]}" \
        -np "$mpi_processes" \
        "$gmx_mpi" \
        mdrun \
        -multidir "${replica_dirs[@]}" \
        -deffnm "$segment_name" \
        -hrex \
        -replex "$exchange_steps" \
        -plumed plumed.dat \
        "${gromacs_options[@]}"; then
        die "REST2 segment $segment 실행에 실패했습니다."
    fi
done

echo "10 ns REST2가 완료되었습니다: $work_dir/replicas"

