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
topology=${TOPOLOGY:-"$script_dir/../2_Topology_Build/work/system.parm7"}
coordinates=${COORDINATES:-"$script_dir/../2_Topology_Build/work/system.rst7"}
work_dir=${WORK_DIR:-"$script_dir/work"}

# 실행 전 확인
if (( ! dry_run )); then
    if ! command -v "$engine" >/dev/null 2>&1; then
        die "AMBER engine을 찾을 수 없습니다: $engine"
    fi

    if [[ ! -s "$topology" ]]; then
        die "topology를 찾을 수 없습니다: $topology"
    fi

    if [[ ! -s "$coordinates" ]]; then
        die "restart file을 찾을 수 없습니다: $coordinates"
    fi

    # Working directory로 이동해도 input 경로가 유지되도록
    # topology와 restart file을 절대 경로로 바꿉니다.
    topology=$(make_absolute_path "$topology")
    coordinates=$(make_absolute_path "$coordinates")
fi

# Working directory 준비
if (( dry_run )); then
    printf '+ mkdir -p %q\n' "$work_dir"
    printf '+ cd %q\n' "$work_dir"
else
    mkdir -p "$work_dir"
    cd "$work_dir"
    echo "AMBER engine: $engine (기본값: pmemd.cuda)"
fi

# Main workflow
run_stage 'environment 최소화' \
    "$engine" \
    -O \
    -i "$script_dir/inputs/min-environment.in" \
    -o min-environment.out \
    -p "$topology" \
    -c "$coordinates" \
    -r min-environment.rst7 \
    -ref "$coordinates"

run_stage '전체 system 최소화' \
    "$engine" \
    -O \
    -i "$script_dir/inputs/min-all.in" \
    -o min-all.out \
    -p "$topology" \
    -c min-environment.rst7 \
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
    -ref heat.rst7

run_stage '10 ns production' \
    "$engine" \
    -O \
    -i "$script_dir/inputs/production.in" \
    -o production.out \
    -p "$topology" \
    -c equil.rst7 \
    -r production.rst7 \
    -x production.nc \
    -inf production.info

if (( ! dry_run )); then
    echo "Production trajectory: $work_dir/production.nc"
fi
