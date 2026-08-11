#!/usr/bin/env bash
set -euo pipefail

if [[ $# -ne 0 ]]; then
    echo "사용법: $0" >&2
    exit 2
fi

# 다른 system이나 frame 범위를 사용할 때는 아래 설정을 수정합니다.
simulation_dir="../../../1_Simulation/1_MD/1.1_Soluble_Protein"
topology="$simulation_dir/work/system.parm7"
trajectory="$simulation_dir/work/production.nc"
start_frame=1
stop_frame=last
stride=1

cpptraj=cpptraj
input_file=inputs/cpptraj.in
output_dir=output
trajectory_arguments="$start_frame $stop_frame $stride"

if ! command -v "$cpptraj" >/dev/null 2>&1; then
    echo "오류: cpptraj을 찾을 수 없습니다." >&2
    exit 1
fi
if [[ ! -f "$input_file" ]]; then
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
echo "선택한 frame을 NetCDF, DCD와 PDB로 변환합니다."

cd "$output_dir"
topology="../$topology"
trajectory="../$trajectory"
input_file="../$input_file"
if ! "$cpptraj" \
    -p "$topology" \
    -y "$trajectory" \
    -ya "$trajectory_arguments" \
    -i "$input_file" \
    > cpptraj.log 2>&1; then
    echo "오류: cpptraj 실행에 실패했습니다: $output_dir/cpptraj.log" >&2
    exit 1
fi

echo "변환 결과: $output_dir"
