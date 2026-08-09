#!/usr/bin/env bash
set -euo pipefail

script_dir=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
analysis_root=$(cd "$script_dir/../.." && pwd)
python=${PYTHON:-python3}

export TUTORIAL_DIR="$script_dir"
export EXPECTED_OUTPUTS="sampled.nc sampled.dcd first_frame.pdb"

"$analysis_root/_run_cpptraj.sh" "$@"

if [[ "${1:-}" != "--dry-run" ]]; then
    output_dir=${OUTPUT_DIR:-"$script_dir/output"}
    cpptraj=${CPPTRAJ:-cpptraj}

    if ! command -v "$python" >/dev/null 2>&1; then
        echo "오류: Python을 찾을 수 없습니다: $python" >&2
        exit 1
    fi

    "$python" "$script_dir/frame_map.py" \
        --output "$output_dir" \
        --cpptraj "$cpptraj"

    if [[ ! -s "$output_dir/frame_map.tsv" ]]; then
        echo "오류: frame_map.tsv가 생성되지 않았습니다." >&2
        exit 1
    fi
fi
