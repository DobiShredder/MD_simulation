#!/usr/bin/env bash
set -euo pipefail

dry_run=0

while [[ $# -gt 0 ]]; do
    case "$1" in
    --dry-run)
        dry_run=1
        ;;
    *)
        echo "사용법: $0 [--dry-run]" >&2
        exit 2
        ;;
    esac
    shift
done

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

# 사용자 설정과 input/output 경로
engine=${AMBER_ENGINE:-pmemd.cuda}

system_dir=${SYSTEM_DIR:-../work}
work_dir=${WORK_DIR:-work}

source_topology="$system_dir/system.parm7"
source_coordinates="$system_dir/system.rst7"

# 실행 전 확인
if (( ! dry_run )); then
    if ! command -v "$engine" >/dev/null 2>&1; then
        die "AMBER engine을 찾을 수 없습니다: $engine"
    fi

    if [[ ! -s "$source_topology" ]]; then
        die "공통 topology를 찾을 수 없습니다: $source_topology" \
            "상위 directory에서 ./prepare.sh를 먼저 실행하세요."
    fi

    if [[ ! -s "$source_coordinates" ]]; then
        die "공통 restart file을 찾을 수 없습니다: $source_coordinates" \
            "상위 directory에서 ./prepare.sh를 먼저 실행하세요."
    fi
fi

# Working directory에 PLUMED input을 고정된 이름으로 둡니다.
if (( dry_run )); then
    printf '+ mkdir -p %q\n' "$work_dir"
    printf '+ cp %q %q\n' "$source_topology" "$work_dir/system.parm7"
    printf '+ cp %q %q\n' "$source_coordinates" "$work_dir/system.rst7"
    printf '+ cp inputs/\*.in %q\n' "$work_dir/inputs/"
    printf '+ cp inputs/plumed.dat %q\n' "$work_dir/plumed.dat"
    printf '+ cd %q\n' "$work_dir"
else
    mkdir -p "$work_dir"
    mkdir -p "$work_dir/inputs"
    cp "$source_topology" "$work_dir/system.parm7"
    cp "$source_coordinates" "$work_dir/system.rst7"
    cp inputs/*.in "$work_dir/inputs/"
    cp inputs/plumed.dat "$work_dir/plumed.dat"
    cd "$work_dir"
    echo "Ratchet MD를 실행합니다: $engine"
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

if (( ! dry_run )); then
    final_density=$(awk '
        /A V E R A G E S/ { exit }
        /Density/ { density = $3 }
        END { print density }
    ' equil.out)

    if [[ -z "$final_density" ]]; then
        die "equil.out에서 최종 density를 읽지 못했습니다: $work_dir/equil.out"
    fi

    if ! awk \
        -v density="$final_density" \
        'BEGIN { exit !(density >= 0.90 && density <= 1.10) }'; then
        die "NPT 후 density가 확인 범위를 벗어났습니다: " \
            "${final_density} g/cm^3. ratchet MD를 시작하지 않습니다."
    fi

    echo "NPT 최종 density: ${final_density} g/cm^3"
fi

run_stage '1 ns ratchet MD' \
    "$engine" \
    -O \
    -i inputs/ratchet.in \
    -o ratchet.out \
    -p system.parm7 \
    -c equil.rst7 \
    -r ratchet.rst7 \
    -x ratchet.nc \
    -inf ratchet.info

if (( ! dry_run )); then
    echo "Ratchet MD trajectory: ratchet.nc"
fi
