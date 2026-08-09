#!/usr/bin/env bash
set -euo pipefail

dry_run=0
if [[ "${1:-}" == "--dry-run" ]]; then
    dry_run=1
    shift
fi

if [[ $# -ne 1 ]]; then
    echo "사용법: $0 [--dry-run] CHIGNOLIN.pdb" >&2
    exit 2
fi

die() {
    echo "오류: $*" >&2
    exit 1
}

input_pdb=$1
tleap=${TLEAP:-tleap}
script_dir=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
work_dir=${WORK_DIR:-"$script_dir/work"}

if (( dry_run )); then
    printf 'mkdir -p %q\n' "$work_dir"
    printf 'cp %q %q\n' "$input_pdb" "$work_dir/input.pdb"
    printf 'cd %q\n' "$work_dir"
    printf '%q -f %q\n' "$tleap" "$script_dir/inputs/tleap.in"
    exit 0
fi

if [[ ! -s "$input_pdb" ]]; then
    die "전처리 PDB를 찾을 수 없습니다: $input_pdb"
fi
if ! command -v "$tleap" >/dev/null 2>&1; then
    die "tleap을 찾을 수 없습니다: $tleap"
fi

mkdir -p "$work_dir"
cp "$input_pdb" "$work_dir/input.pdb"

echo "ff19SB/TIP3P Chignolin topology를 생성합니다."
if ! (
    cd "$work_dir"
    "$tleap" -f "$script_dir/inputs/tleap.in" > leap.log 2>&1
); then
    die "tleap 실행에 실패했습니다: $work_dir/leap.log"
fi

for output in system.parm7 system.rst7 system.pdb; do
    if [[ ! -s "$work_dir/$output" ]]; then
        die "build output이 생성되지 않았습니다: $work_dir/$output"
    fi
done

echo "AMBER topology와 restart: $work_dir"
