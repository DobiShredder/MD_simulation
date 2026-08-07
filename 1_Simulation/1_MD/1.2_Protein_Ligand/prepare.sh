#!/usr/bin/env bash
set -euo pipefail

die() {
    echo "오류: $*" >&2
    exit 1
}

dry_run=0

if [[ "${1:-}" == "--dry-run" ]]; then
    dry_run=1
    shift
fi

if [[ $# -ne 1 ]]; then
    echo "사용법: $0 [--dry-run] BEN_ideal.sdf" >&2
    exit 2
fi

# Input과 사용자 설정
ligand_sdf=$1
antechamber=${ANTECHAMBER:-antechamber}
parmchk2=${PARMCHK2:-parmchk2}
ligand_charge=${LIGAND_CHARGE:-1}

script_dir=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
work_dir=${WORK_DIR:-"$script_dir/work"}

ligand_mol2="$work_dir/ben.mol2"
ligand_frcmod="$work_dir/ben.frcmod"

# 사용자 설정 확인
if [[ ! "$ligand_charge" =~ ^-?[0-9]+$ ]]; then
    echo "오류: LIGAND_CHARGE는 정수여야 합니다: $ligand_charge" >&2
    exit 2
fi

# 실행 전 확인
if (( ! dry_run )); then
    if [[ ! -f "$ligand_sdf" ]]; then
        die "ligand SDF를 찾을 수 없습니다: $ligand_sdf"
    fi

    if ! command -v "$antechamber" >/dev/null 2>&1; then
        die "antechamber를 찾을 수 없습니다: $antechamber"
    fi

    if ! command -v "$parmchk2" >/dev/null 2>&1; then
        die "parmchk2를 찾을 수 없습니다: $parmchk2"
    fi
fi

# Dry-run에서는 파일을 생성하지 않고 command만 보여줍니다.
if (( dry_run )); then
    printf 'mkdir -p %q\n' "$work_dir"
    printf '%q \\\n' "$antechamber"
    printf '  -i %q \\\n' "$ligand_sdf"
    printf '  -fi sdf \\\n'
    printf '  -o %q \\\n' "$ligand_mol2"
    printf '  -fo mol2 \\\n'
    printf '  -at gaff2 \\\n'
    printf '  -c bcc \\\n'
    printf '  -nc %q \\\n' "$ligand_charge"
    printf '  -rn BEN \\\n'
    printf '  -s 2\n'
    printf '%q \\\n' "$parmchk2"
    printf '  -i %q \\\n' "$ligand_mol2"
    printf '  -f mol2 \\\n'
    printf '  -o %q \\\n' "$ligand_frcmod"
    printf '  -s gaff2\n'
    exit 0
fi

# GAFF2 atom type과 AM1-BCC charge를 적용합니다.
echo "BEN을 GAFF2/AM1-BCC로 parameterize합니다 (net charge: $ligand_charge)."
mkdir -p "$work_dir"

if ! "$antechamber" \
    -i "$ligand_sdf" \
    -fi sdf \
    -o "$ligand_mol2" \
    -fo mol2 \
    -at gaff2 \
    -c bcc \
    -nc "$ligand_charge" \
    -rn BEN \
    -s 2 \
    > "$work_dir/antechamber.log" 2>&1; then
    die "antechamber 실행에 실패했습니다. 확인할 파일: $work_dir/antechamber.log"
fi

# Mol2에 없는 GAFF2 parameter를 frcmod로 만듭니다.
if ! "$parmchk2" \
    -i "$ligand_mol2" \
    -f mol2 \
    -o "$ligand_frcmod" \
    -s gaff2 \
    > "$work_dir/parmchk2.log" 2>&1; then
    die "parmchk2 실행에 실패했습니다. 확인할 파일: $work_dir/parmchk2.log"
fi

if [[ ! -s "$ligand_mol2" ]]; then
    die "ligand mol2가 생성되지 않았습니다: $ligand_mol2"
fi

if [[ ! -s "$ligand_frcmod" ]]; then
    die "ligand frcmod가 생성되지 않았습니다: $ligand_frcmod"
fi

echo "Ligand parameter: $work_dir"
