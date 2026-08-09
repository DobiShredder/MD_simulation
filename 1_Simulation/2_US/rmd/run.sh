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

make_absolute_path() {
    local path=$1
    local directory
    local filename

    directory=$(dirname "$path")
    filename=$(basename "$path")
    directory=$(cd "$directory" && pwd -P)

    echo "$directory/$filename"
}

run_stage() {
    local stage=$1
    shift

    if (( dry_run )); then
        printf '+'
        printf ' %q' "$@"
        printf '\n'
        return
    fi

    echo "실행: $stage ($engine)"

    if ! "$@"; then
        die "$stage 단계가 실패했습니다. 확인할 경로: $work_dir"
    fi
}

# 사용자 설정과 input/output 경로
engine=${AMBER_ENGINE:-pmemd.cuda}

script_dir=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
system_dir=${SYSTEM_DIR:-"$script_dir/../work"}
work_dir=${WORK_DIR:-"$script_dir/work"}

topology="$system_dir/system.parm7"
coordinates="$system_dir/system.rst7"

# 실행 전 확인
if (( ! dry_run )); then
    if ! command -v "$engine" >/dev/null 2>&1; then
        die "AMBER engine을 찾을 수 없습니다: $engine"
    fi

    if [[ ! -s "$topology" ]]; then
        die "공통 topology를 찾을 수 없습니다: $topology" \
            "상위 directory에서 ./prepare.sh를 먼저 실행하세요."
    fi

    if [[ ! -s "$coordinates" ]]; then
        die "공통 restart file을 찾을 수 없습니다: $coordinates" \
            "상위 directory에서 ./prepare.sh를 먼저 실행하세요."
    fi

    topology=$(make_absolute_path "$topology")
    coordinates=$(make_absolute_path "$coordinates")
fi

# Working directory에 PLUMED input을 고정된 이름으로 둡니다.
if (( dry_run )); then
    printf '+ mkdir -p %q\n' "$work_dir"
    printf '+ cp %q %q\n' "$script_dir/inputs/plumed.dat" "$work_dir/plumed.dat"
    printf '+ cd %q\n' "$work_dir"
else
    mkdir -p "$work_dir"
    cp "$script_dir/inputs/plumed.dat" "$work_dir/plumed.dat"
    cd "$work_dir"
    echo "Ratchet MD를 실행합니다: $engine"
fi

# Main workflow
run_stage 'solvent minimization' \
    "$engine" \
    -O \
    -i "$script_dir/inputs/min-solvent.in" \
    -o min-solvent.out \
    -p "$topology" \
    -c "$coordinates" \
    -r min-solvent.rst7 \
    -ref "$coordinates"

run_stage '전체 system minimization' \
    "$engine" \
    -O \
    -i "$script_dir/inputs/min-all.in" \
    -o min-all.out \
    -p "$topology" \
    -c min-solvent.rst7 \
    -r min-all.rst7

run_stage 'NVT 가열' \
    "$engine" \
    -O \
    -i "$script_dir/inputs/heat.in" \
    -o heat.out \
    -p "$topology" \
    -c min-all.rst7 \
    -r heat.rst7 \
    -x heat.nc \
    -inf heat.info \
    -ref min-all.rst7

run_stage 'NPT equilibration' \
    "$engine" \
    -O \
    -i "$script_dir/inputs/equil.in" \
    -o equil.out \
    -p "$topology" \
    -c heat.rst7 \
    -r equil.rst7 \
    -x equil.nc \
    -inf equil.info \
    -ref heat.rst7

run_stage '1 ns ratchet MD' \
    "$engine" \
    -O \
    -i "$script_dir/inputs/ratchet.in" \
    -o ratchet.out \
    -p "$topology" \
    -c equil.rst7 \
    -r ratchet.rst7 \
    -x ratchet.nc \
    -inf ratchet.info

if (( ! dry_run )); then
    echo "Ratchet MD trajectory: $work_dir/ratchet.nc"
fi
