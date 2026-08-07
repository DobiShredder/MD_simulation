#!/usr/bin/env bash
set -euo pipefail

dry_run=0

if [[ "${1:-}" == "--dry-run" ]]; then
    dry_run=1
    shift
fi

if [[ $# -ne 1 ]]; then
    echo "사용법: $0 [--dry-run] SYSTEM-COORDINATES.pdb" >&2
    exit 2
fi

die() {
    echo "오류: $*" >&2
    exit 1
}

# Input과 사용자 설정
coordinate_pdb=$1
converter=${CHARMMLIPID2AMBER:-charmmlipid2amber.py}
tleap=${TLEAP:-tleap}

script_dir=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
work_dir=${WORK_DIR:-"$script_dir/work"}
amber_named_pdb="$work_dir/amber-named.pdb"

# 실행 전 확인
if (( ! dry_run )); then
    if [[ ! -f "$coordinate_pdb" ]]; then
        die "coordinate PDB를 찾을 수 없습니다: $coordinate_pdb"
    fi

    if ! command -v "$converter" >/dev/null 2>&1; then
        die "charmmlipid2amber.py를 찾을 수 없습니다: $converter"
    fi

    if ! command -v "$tleap" >/dev/null 2>&1; then
        die "tleap을 찾을 수 없습니다: $tleap"
    fi
fi

# Dry-run에서는 파일을 생성하지 않고 command만 보여줍니다.
if (( dry_run )); then
    printf 'mkdir -p %q\n' "$work_dir"
    printf '%q \\\n' "$converter"
    printf '  -i %q \\\n' "$coordinate_pdb"
    printf '  -o %q\n' "$amber_named_pdb"
    printf 'cd %q\n' "$work_dir"
    printf '%q \\\n' "$tleap"
    printf '  -f %q\n' "$script_dir/tleap.in"
    exit 0
fi

echo "AMBER topology를 생성합니다 (ff19SB/Lipid21/OPC)."
mkdir -p "$work_dir"

# PACKMOL-Memgen/CHARMM 표기를 AMBER Lipid21 표기로 바꿉니다.
if ! "$converter" \
    -i "$coordinate_pdb" \
    -o "$amber_named_pdb" \
    > "$work_dir/name-conversion.log" 2>&1; then
    die "lipid name 변환에 실패했습니다. 확인할 파일: $work_dir/name-conversion.log"
fi

if [[ ! -s "$amber_named_pdb" ]]; then
    die "변환된 PDB가 생성되지 않았습니다. " \
        "확인할 파일: $work_dir/name-conversion.log"
fi

# 변환된 coordinate file에 ff19SB, Lipid21과 OPC를 적용합니다.
if ! (
    cd "$work_dir"
    "$tleap" \
        -f "$script_dir/tleap.in" \
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

echo "AMBER topology와 restart: $work_dir"
