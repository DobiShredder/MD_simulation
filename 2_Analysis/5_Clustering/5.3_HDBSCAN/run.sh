#!/usr/bin/env bash
set -euo pipefail

if [[ $# -ne 0 ]]; then
    echo "사용법: $0" >&2
    exit 2
fi

simulation_dir="../../../1_Simulation/1_MD/1.1_Soluble_Protein"
topology="$simulation_dir/work/system.parm7"
trajectory="$simulation_dir/work/production.nc"
cpptraj=cpptraj
input_file=inputs/cpptraj.in
output_dir=output

if ! command -v "$cpptraj" >/dev/null 2>&1; then
    echo "오류: cpptraj을 찾을 수 없습니다." >&2
    exit 1
fi
if [[ ! -s "$input_file" ]]; then
    echo "오류: cpptraj input이 없습니다: $input_file" >&2
    exit 1
fi
if [[ ! -s "$topology" ]]; then
    echo "오류: Chignolin topology가 없습니다: $topology" >&2
    exit 1
fi
if [[ ! -s "$trajectory" ]]; then
    echo "오류: Chignolin trajectory가 없습니다: $trajectory" >&2
    exit 1
fi

mkdir -p "$output_dir"
cd "$output_dir"
topology="../$topology"
trajectory="../$trajectory"
input_file="../$input_file"

if ! "$cpptraj" \
    -p "$topology" \
    -y "$trajectory" \
    -i "$input_file" \
    > cpptraj.log 2>&1; then
    echo "오류: cpptraj 실행에 실패했습니다: $output_dir/cpptraj.log" >&2
    exit 1
fi

echo "Dihedral feature: $output_dir/phi_psi.dat"
