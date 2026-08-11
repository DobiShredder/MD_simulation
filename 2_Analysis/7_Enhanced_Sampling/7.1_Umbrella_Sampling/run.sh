#!/usr/bin/env bash
set -euo pipefail

simulation_dir="../../../1_Simulation/2_US/us"
windows="$simulation_dir/work"
output=output
python=python3

if [[ ! -d "$windows" ]]; then
    echo "오류: umbrella window output을 찾을 수 없습니다: $windows" >&2
    exit 1
fi

if ! command -v "$python" >/dev/null 2>&1; then
    echo "오류: Python을 찾을 수 없습니다: $python" >&2
    exit 1
fi

"$python" prepare.py

echo "WHAM 입력을 생성했습니다: $output"
