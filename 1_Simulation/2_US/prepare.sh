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

# 사용자 설정과 input/output 경로
tleap=${TLEAP:-tleap}

input_pdb=${INPUT_PDB:-"structure/chignolin.pdb"}
work_dir=${WORK_DIR:-"work"}

# 실행 전 확인
if (( ! dry_run )); then
    if [[ ! -s "$input_pdb" ]]; then
        die "입력 PDB를 찾을 수 없습니다: $input_pdb"
    fi

    if ! command -v "$tleap" >/dev/null 2>&1; then
        die "tleap을 찾을 수 없습니다: $tleap"
    fi
fi

# Dry-run에서는 파일을 생성하지 않고 command만 보여줍니다.
if (( dry_run )); then
    printf 'mkdir -p %q\n' "$work_dir"
    printf 'cp %q %q\n' "$input_pdb" "$work_dir/input.pdb"
    printf 'cd %q\n' "$work_dir"
    printf '%q \\\n' "$tleap"
    printf '  -f %q\n' "inputs/tleap.in"
    exit 0
fi

# Ratchet MD와 모든 umbrella window가 공유할 system을 만듭니다.
echo "ff19SB/TIP3P로 ratchet MD와 US가 공유할 system을 생성합니다."

mkdir -p "$work_dir"
cp "$input_pdb" "$work_dir/input.pdb"
cp inputs/tleap.in "$work_dir/tleap.in"

if ! (
    cd "$work_dir"
    "$tleap" \
        -f tleap.in \
        > leap.log 2>&1
); then
    die "tleap 실행에 실패했습니다. 확인할 파일: $work_dir/leap.log"
fi

if [[ ! -s "$work_dir/system.parm7" ]]; then
    die "topology가 생성되지 않았습니다. 확인할 파일: $work_dir/leap.log"
fi

if [[ ! -s "$work_dir/system.rst7" ]]; then
    die "restart file이 생성되지 않았습니다. 확인할 파일: $work_dir/leap.log"
fi

echo "공통 AMBER topology와 restart: $work_dir"
