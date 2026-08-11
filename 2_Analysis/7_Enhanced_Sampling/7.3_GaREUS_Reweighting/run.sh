#!/usr/bin/env bash
set -euo pipefail

simulation_dir="../../../1_Simulation/3_REMD/3.5_GaREUS"
simulation_work="$simulation_dir/work"
output=output
python=python3

if [[ ! -s "$simulation_work/states.tsv" ]]; then
    echo "오류: GaREUS simulation을 먼저 실행해야 합니다: $simulation_work/states.tsv" >&2
    exit 1
fi

if ! command -v "$python" >/dev/null 2>&1; then
    echo "오류: Python을 찾을 수 없습니다: $python" >&2
    exit 1
fi

"$python" prepare.py

echo "GaREUS reweighting 입력을 생성했습니다: $output"
