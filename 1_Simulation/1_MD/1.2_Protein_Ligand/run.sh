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

# 사용자 설정과 output 경로
engine=${AMBER_ENGINE:-pmemd.cuda}

work_dir=${WORK_DIR:-work}
topology="$work_dir/system.parm7"
coordinates="$work_dir/system.rst7"

# 실행 전 확인
if (( ! dry_run )); then
    if ! command -v "$engine" >/dev/null 2>&1; then
        die "AMBER engine을 찾을 수 없습니다: $engine"
    fi

    if [[ ! -s "$topology" ]]; then
        die "topology를 찾을 수 없습니다. ./build.sh를 먼저 실행하세요."
    fi

    if [[ ! -s "$coordinates" ]]; then
        die "restart file을 찾을 수 없습니다. ./build.sh를 먼저 실행하세요."
    fi
fi

# Working directory 준비
if (( dry_run )); then
    printf '+ mkdir -p %q\n' "$work_dir"
    printf '+ cd %q\n' "$work_dir"
else
    mkdir -p "$work_dir"
    mkdir -p "$work_dir/inputs"
    cp inputs/*.in "$work_dir/inputs/"
    cd "$work_dir"
    echo "AMBER engine: $engine (기본값: pmemd.cuda)"
fi

# Main workflow
run_stage 'solvent minimization' \
    "$engine" \
    -O \
    -i inputs/min-solvent.in \
    -o min-solvent.out \
    -p system.parm7 \
    -c system.rst7 \
    -r min-solvent.rst7 \
    -ref system.rst7

run_stage '전체 system minimization' \
    "$engine" \
    -O \
    -i inputs/min-all.in \
    -o min-all.out \
    -p system.parm7 \
    -c min-solvent.rst7 \
    -r min-all.rst7

run_stage 'NVT 가열' \
    "$engine" \
    -O \
    -i inputs/heat.in \
    -o heat.out \
    -p system.parm7 \
    -c min-all.rst7 \
    -r heat.rst7 \
    -x heat.nc \
    -inf heat.info \
    -ref min-all.rst7

run_stage 'NPT equilibration' \
    "$engine" \
    -O \
    -i inputs/equil.in \
    -o equil.out \
    -p system.parm7 \
    -c heat.rst7 \
    -r equil.rst7 \
    -x equil.nc \
    -inf equil.info \
    -ref heat.rst7

run_stage '1 ns production' \
    "$engine" \
    -O \
    -i inputs/production.in \
    -o production.out \
    -p system.parm7 \
    -c equil.rst7 \
    -r production.rst7 \
    -x production.nc \
    -inf production.info

if (( ! dry_run )); then
    echo "Production trajectory: production.nc"
fi
