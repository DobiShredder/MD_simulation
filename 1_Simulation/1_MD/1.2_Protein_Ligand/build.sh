#!/usr/bin/env bash
set -euo pipefail

dry_run=0

if [[ "${1:-}" == "--dry-run" ]]; then
    dry_run=1
    shift
fi

if [[ $# -ne 1 ]]; then
    echo "사용법: $0 [--dry-run] COMPLEX.pdb" >&2
    exit 2
fi

die() {
    echo "오류: $*" >&2
    exit 1
}

# Input과 사용자 설정
complex_pdb=$1
tleap=${TLEAP:-tleap}

script_dir=$(dirname "${BASH_SOURCE[0]}")
work_dir=${WORK_DIR:-"$script_dir/work"}

ligand_mol2="$work_dir/jz4.mol2"
ligand_frcmod="$work_dir/jz4.frcmod"

# 실행 전 확인
if (( ! dry_run )); then
    if [[ ! -f "$complex_pdb" ]]; then
        die "complex PDB를 찾을 수 없습니다: $complex_pdb"
    fi

    if [[ ! -s "$ligand_mol2" ]]; then
        die "ligand mol2가 없습니다. ./prepare.sh를 먼저 실행하세요."
    fi

    if [[ ! -s "$ligand_frcmod" ]]; then
        die "ligand frcmod이 없습니다. ./prepare.sh를 먼저 실행하세요."
    fi

    if ! command -v "$tleap" >/dev/null 2>&1; then
        die "tleap을 찾을 수 없습니다: $tleap"
    fi
fi

# Dry-run에서는 파일을 생성하지 않고 command만 보여줍니다.
if (( dry_run )); then
    printf 'mkdir -p %q\n' "$work_dir"
    printf 'cp %q %q\n' "$complex_pdb" "$work_dir/complex.pdb"
    printf 'cp %q %q\n' "$script_dir/tleap.in" "$work_dir/tleap.in"
    printf 'cd %q\n' "$work_dir"
    printf '%q \\\n' "$tleap"
    printf '  -f tleap.in\n'
    exit 0
fi

# Protein과 ligand를 하나의 solvated system으로 만듭니다.
echo "ff19SB/GAFF2/TIP3P로 T4 lysozyme–JZ4 system을 생성합니다."

mkdir -p "$work_dir"
cp "$complex_pdb" "$work_dir/complex.pdb"
cp "$script_dir/tleap.in" "$work_dir/tleap.in"

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

echo "AMBER topology와 restart: $work_dir"
