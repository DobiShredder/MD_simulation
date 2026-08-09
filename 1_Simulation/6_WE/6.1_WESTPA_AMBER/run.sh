#!/usr/bin/env bash
set -euo pipefail

source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/env.sh"

dry_run=0
if [[ "${1:-}" == "--dry-run" ]]; then
    dry_run=1
    shift
fi
if [[ $# -ne 0 ]]; then
    echo "사용법: $0 [--dry-run]" >&2
    exit 2
fi

case "$WESTPA_WORK_MANAGER" in
    serial|processes)
        ;;
    *)
        echo "오류: WESTPA_WORK_MANAGER는 serial 또는 processes여야 합니다." >&2
        exit 1
        ;;
esac

if [[ ! "$WESTPA_WORKERS" =~ ^[1-9][0-9]*$ ]]; then
    echo "오류: WESTPA_WORKERS는 1 이상의 정수여야 합니다." >&2
    exit 1
fi

if [[ "$WESTPA_WORK_MANAGER" == "serial" && "$WESTPA_WORKERS" -ne 1 ]]; then
    echo "오류: serial work manager에서는 WESTPA_WORKERS=1을 사용하세요." >&2
    exit 1
fi

if [[ "$WESTPA_WORK_MANAGER" == "processes" && "$AMBER_ENGINE" == "pmemd.cuda" ]]; then
    echo "오류: process worker 예제는 CPU engine용입니다. AMBER_ENGINE=sander를 지정하세요." >&2
    exit 1
fi

westpa_command=(
    w_run
    --work-manager "$WESTPA_WORK_MANAGER"
)

if [[ "$WESTPA_WORK_MANAGER" == "processes" ]]; then
    westpa_command+=(
        --n-workers "$WESTPA_WORKERS"
    )
fi

if (( dry_run )); then
    echo "WESTPA 2: Na+/Cl- distance, bin당 walker 4개, 1 ps × 20 iterations"
    printf 'AMBER engine: %s\n' "$AMBER_ENGINE"
    printf 'Work manager: %s, worker 수: %s\n' \
        "$WESTPA_WORK_MANAGER" \
        "$WESTPA_WORKERS"
    printf '%q ' "${westpa_command[@]}"
    printf '\n'
    exit 0
fi

if [[ ! -s "$WORK_DIR/west.h5" ]]; then
    echo "오류: init.sh를 먼저 실행해야 합니다: $WORK_DIR/west.h5" >&2
    exit 1
fi

for executable in w_run "$AMBER_ENGINE" "$CPPTRAJ"; do
    if ! command -v "$executable" >/dev/null 2>&1; then
        echo "오류: $executable 실행 파일을 찾을 수 없습니다." >&2
        exit 1
    fi
done

cd "$WEST_SIM_ROOT"
if ! "${westpa_command[@]}" > "$WORK_DIR/west.log" 2>&1; then
    echo "오류: WESTPA 실행에 실패했습니다: $WORK_DIR/west.log" >&2
    exit 1
fi

echo "WESTPA 실행이 완료되었습니다: $WORK_DIR/west.h5"
