#!/usr/bin/env bash
set -euo pipefail

if [[ $# -ne 0 ]]; then
    echo "사용법: $0" >&2
    exit 2
fi

# 다른 protein-ligand system을 사용할 때는 아래 경로와 ligand mask를 수정합니다.
simulation_dir="../../../1_Simulation/1_MD/1.2_Protein_Ligand"
solvated_topology="$simulation_dir/work/system.parm7"
trajectory="$simulation_dir/work/production.nc"
ligand_mask=:JZ4

ante_mmpbsa=ante-MMPBSA.py
mmpbsa=MMPBSA.py
input_file=inputs/mmpbsa.in
output_dir=output

for executable in "$ante_mmpbsa" "$mmpbsa"; do
    if ! command -v "$executable" >/dev/null 2>&1; then
        echo "오류: 실행 파일을 찾을 수 없습니다: $executable" >&2
        exit 1
    fi
done
if [[ ! -s "$input_file" ]]; then
    echo "오류: MMPBSA.py input이 없습니다: $input_file" >&2
    exit 1
fi
if [[ ! -s "$solvated_topology" ]]; then
    echo "오류: T4 lysozyme–JZ4 topology가 없습니다: $solvated_topology" >&2
    exit 1
fi
if [[ ! -s "$trajectory" ]]; then
    echo "오류: T4 lysozyme–JZ4 trajectory가 없습니다: $trajectory" >&2
    exit 1
fi

mkdir -p "$output_dir"
cd "$output_dir"
solvated_topology="../$solvated_topology"
trajectory="../$trajectory"
input_file="../$input_file"

echo "Complex, receptor와 ligand topology를 생성합니다."
if ! "$ante_mmpbsa" \
    -p "$solvated_topology" \
    -c complex.parm7 \
    -r receptor.parm7 \
    -l ligand.parm7 \
    -s ':WAT,Na+,Cl-' \
    -n "$ligand_mask" \
    --radii mbondi2 \
    > topology.log 2>&1; then
    echo "오류: MMPBSA topology 생성에 실패했습니다: $output_dir/topology.log" >&2
    exit 1
fi

echo "100개 frame의 MM/GBSA를 계산합니다."
if ! "$mmpbsa" \
    -O \
    -i "$input_file" \
    -sp "$solvated_topology" \
    -cp complex.parm7 \
    -rp receptor.parm7 \
    -lp ligand.parm7 \
    -y "$trajectory" \
    -o final_results.dat \
    -do final_decomposition.dat \
    -eo energy.csv \
    -deo decomposition.csv \
    > mmpbsa.log 2>&1; then
    echo "오류: MM/GBSA 계산에 실패했습니다: $output_dir/mmpbsa.log" >&2
    exit 1
fi

echo "MM/GBSA 결과: $output_dir"
