#!/usr/bin/env bash
set -euo pipefail

source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/env.sh"

reset=0
if [[ "${1:-}" == "--reset" ]]; then
    reset=1
    shift
fi
if [[ $# -ne 0 ]]; then
    echo "사용법: $0 [--reset]" >&2
    exit 2
fi

die() {
    echo "오류: $*" >&2
    exit 1
}

if [[ ! -s "$WORK_DIR/bstates/basis.rst7" ]]; then
    die "build.sh를 먼저 실행해야 합니다: $WORK_DIR/bstates/basis.rst7"
fi
if ! command -v w_init >/dev/null 2>&1; then
    die "w_init을 찾을 수 없습니다. WESTPA 2 환경을 활성화하세요."
fi

if [[ -e "$WORK_DIR/west.h5" && "$reset" -eq 0 ]]; then
    die "기존 WESTPA state가 있습니다. 새로 시작하려면 ./init.sh --reset을 사용하세요."
fi

if (( reset )); then
    if [[ -z "$WORK_DIR" || "$WORK_DIR" == / || "$WORK_DIR" == "$HOME" ]]; then
        die "안전하지 않은 WORK_DIR에서는 reset할 수 없습니다: $WORK_DIR"
    fi
    rm -rf \
        "$WORK_DIR/traj_segs" \
        "$WORK_DIR/seg_logs" \
        "$WORK_DIR/istates" \
        "$WORK_DIR/analysis"
    rm -f "$WORK_DIR/west.h5" "$WORK_DIR/west.log"
fi

mkdir -p "$WORK_DIR/traj_segs" "$WORK_DIR/seg_logs" "$WORK_DIR/istates"
cd "$WEST_SIM_ROOT"
w_init \
    --bstate-file "$WEST_SIM_ROOT/bstates/bstates.txt" \
    --tstate-file "$WEST_SIM_ROOT/tstate.file" \
    --segs-per-state 4 \
    --work-manager serial

echo "WESTPA state: $WORK_DIR/west.h5"
