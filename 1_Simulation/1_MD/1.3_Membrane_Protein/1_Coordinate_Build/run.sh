#!/usr/bin/env bash
set -euo pipefail

usage() {
    echo "사용법: $0 [--dry-run] KCSA.pdb" >&2
}

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
    usage
    exit 2
fi

# Input과 output 경로
protein_pdb=$1
python=${PYTHON:-python3}
composition="POPC=90,POPE=5,CHOL=5"
xy_padding=25
water_padding=20
protein_lipid_distance=2.0
structure_dir=structure
work_dir=${WORK_DIR:-work}
output_pdb="$work_dir/system-coordinates.pdb"

if (( dry_run )); then
    printf 'mkdir -p %q\n' "$work_dir"
    printf '%q %q %q %q %q %q %q \\\n' \
        "$python" \
        build_membrane.py \
        "$protein_pdb" \
        "$structure_dir/POPC.gro" \
        "$structure_dir/POPE.gro" \
        "$structure_dir/CHOL15.gro" \
        "$output_pdb"
    printf '  --composition %q \\\n' "$composition"
    printf '  --xy-padding %q \\\n' "$xy_padding"
    printf '  --water-padding %q \\\n' "$water_padding"
    printf '  --protein-lipid-distance %q\n' "$protein_lipid_distance"
    exit 0
fi

# 실행 전 확인
if [[ ! -f "$protein_pdb" ]]; then
    die "KcsA PDB를 찾을 수 없습니다: $protein_pdb"
fi

if ! command -v "$python" >/dev/null 2>&1; then
    die "Python을 찾을 수 없습니다: $python"
fi

for coordinate in POPC.gro POPE.gro CHOL15.gro; do
    if [[ ! -f "$structure_dir/$coordinate" ]]; then
        die "bilayer coordinate가 없습니다. 먼저 ./download.sh를 실행하세요."
    fi
done

if ! "$python" -c "import numpy" >/dev/null 2>&1; then
    die "NumPy를 import할 수 없습니다. ambertools26 환경을 활성화하세요."
fi

# 평형화한 Lipid21 patch를 복제하고 KcsA를 삽입합니다.
mkdir -p "$work_dir"

"$python" \
    build_membrane.py \
    "$protein_pdb" \
    "$structure_dir/POPC.gro" \
    "$structure_dir/POPE.gro" \
    "$structure_dir/CHOL15.gro" \
    "$output_pdb" \
    --composition "$composition" \
    --xy-padding "$xy_padding" \
    --water-padding "$water_padding" \
    --protein-lipid-distance "$protein_lipid_distance"

echo "Coordinate build 결과: $output_pdb"
