#!/usr/bin/env bash
set -euo pipefail

dry_run=0
selected_window=""

while [[ $# -gt 0 ]]; do
    case "$1" in
        --dry-run)
            dry_run=1
            shift
            ;;
        --window)
            if [[ $# -lt 2 ]]; then
                echo "오류: --window에는 번호가 필요합니다." >&2
                exit 2
            fi

            selected_window=$2
            shift 2
            ;;
        *)
            echo "사용법: $0 [--dry-run] [--window N]" >&2
            exit 2
            ;;
    esac
done

die() {
    echo "오류: $*" >&2
    exit 1
}

run_command() {
    if (( dry_run )); then
        printf '+'
        printf ' %q' "$@"
        printf '\n'
        return
    fi

    "$@"
}

run_window() {
    local window_dir=$1
    local window_id=${window_dir##*/}
    local required_file

    for required_file in system.parm7 seed.rst7 restraint.RST; do
        if [[ ! -s "$window_dir/$required_file" ]]; then
            die "$window_id window의 필수 input이 없습니다: $required_file"
        fi
    done

    if [[ -f "$window_dir/.production.complete" ]] && (( ! dry_run )); then
        skipped_window_count=$((skipped_window_count + 1))
        return
    fi

    # Minimization
    if [[ ! -f "$window_dir/.min.complete" ]] || (( dry_run )); then
        if ! (
            cd "$window_dir"
            run_command \
                "$engine" \
                -O \
                -i "$script_dir/inputs/min.in" \
                -o min.out \
                -p system.parm7 \
                -c seed.rst7 \
                -r min.rst7
        ); then
            die "$window_id window minimization이 실패했습니다: $window_dir/min.out"
        fi

        if (( ! dry_run )); then
            touch "$window_dir/.min.complete"
        fi
    fi

    # Heating
    if [[ ! -f "$window_dir/.heat.complete" ]] || (( dry_run )); then
        if ! (
            cd "$window_dir"
            run_command \
                "$engine" \
                -O \
                -i "$script_dir/inputs/heat.in" \
                -o heat.out \
                -p system.parm7 \
                -c min.rst7 \
                -r heat.rst7 \
                -x heat.nc \
                -ref min.rst7
        ); then
            die "$window_id window heating이 실패했습니다: $window_dir/heat.out"
        fi

        if (( ! dry_run )); then
            touch "$window_dir/.heat.complete"
        fi
    fi

    # Equilibration
    if [[ ! -f "$window_dir/.equil.complete" ]] || (( dry_run )); then
        if ! (
            cd "$window_dir"
            run_command \
                "$engine" \
                -O \
                -i "$script_dir/inputs/equil.in" \
                -o equil.out \
                -p system.parm7 \
                -c heat.rst7 \
                -r equil.rst7 \
                -x equil.nc
        ); then
            die "$window_id window equilibration이 실패했습니다: $window_dir/equil.out"
        fi

        if (( ! dry_run )); then
            touch "$window_dir/.equil.complete"
        fi
    fi

    # Production
    if [[ ! -f "$window_dir/.production.complete" ]] || (( dry_run )); then
        if ! (
            cd "$window_dir"
            run_command \
                "$engine" \
                -O \
                -i "$script_dir/inputs/production.in" \
                -o production.out \
                -p system.parm7 \
                -c equil.rst7 \
                -r production.rst7 \
                -x production.nc \
                -inf production.info
        ); then
            die "$window_id window production이 실패했습니다: $window_dir/production.out"
        fi

        if (( ! dry_run )); then
            touch "$window_dir/.production.complete"
        fi
    fi

    processed_window_count=$((processed_window_count + 1))
}

# 사용자 설정과 input/output 경로
engine=${AMBER_ENGINE:-pmemd.cuda}

script_dir=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
work_dir=${WORK_DIR:-"$script_dir/work"}
window_root="$work_dir/windows"

processed_window_count=0
skipped_window_count=0

# 실행 전 확인
if (( ! dry_run )); then
    if ! command -v "$engine" >/dev/null 2>&1; then
        die "AMBER engine을 찾을 수 없습니다: $engine"
    fi
fi

if [[ ! -d "$window_root" ]]; then
    die "생성된 window가 없습니다. ./build.sh를 먼저 실행하세요."
fi

# 선택한 window 또는 전체 window 실행
if [[ -n "$selected_window" ]]; then
    if [[ ! "$selected_window" =~ ^[0-9]+$ ]]; then
        die "window 번호는 양의 정수여야 합니다: $selected_window"
    fi

    if (( 10#$selected_window == 0 )); then
        die "window 번호는 1 이상이어야 합니다: $selected_window"
    fi

    printf -v selected_window_id '%03d' "$((10#$selected_window))"
    selected_window_dir="$window_root/$selected_window_id"

    if [[ ! -d "$selected_window_dir" ]]; then
        die "window를 찾을 수 없습니다: $selected_window_id"
    fi

    run_window "$selected_window_dir"
else
    found_window_count=0

    for window_dir in "$window_root"/[0-9][0-9][0-9]; do
        if [[ ! -d "$window_dir" ]]; then
            continue
        fi

        found_window_count=$((found_window_count + 1))
        run_window "$window_dir"
    done

    if (( found_window_count == 0 )); then
        die "${window_root}에 실행할 window가 없습니다."
    fi
fi

if (( ! dry_run )); then
    echo "Umbrella window 실행 완료: ${processed_window_count}개 실행," \
        "${skipped_window_count}개 기존 완료 ($window_root)"
fi
