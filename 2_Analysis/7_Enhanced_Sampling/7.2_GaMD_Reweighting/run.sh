#!/usr/bin/env bash
set -euo pipefail

if [[ $# -ne 2 ]]; then
    echo "사용법: $0 {chignolin|ligamd3|pepgamd} SIMULATION_WORK_DIR" >&2
    exit 2
fi

die() {
    echo "오류: $*" >&2
    exit 1
}

profile=$1
simulation_work=$2
cpptraj=${CPPTRAJ:-cpptraj}
python=${PYTHON:-python3}
script_dir=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
output_dir=${OUTPUT_DIR:-"$script_dir/output/$profile"}

case "$profile" in
    chignolin | pepgamd)
        components=2
        ;;
    ligamd3)
        components=3
        ;;
    *)
        die "지원하지 않는 profile입니다: $profile"
        ;;
esac

for executable in "$cpptraj" "$python"; do
    if ! command -v "$executable" >/dev/null 2>&1; then
        die "실행 파일을 찾을 수 없습니다: $executable"
    fi
done
if ! "$python" -c 'import numpy' >/dev/null 2>&1; then
    die "NumPy를 import할 수 없습니다."
fi

mkdir -p "$output_dir"
"$python" \
    "$script_dir/prepare.py" \
    "$profile" \
    "$simulation_work" \
    "$output_dir/cpptraj.in"

if ! "$cpptraj" \
    -i "$output_dir/cpptraj.in" \
    > "$output_dir/cpptraj.log" 2>&1; then
    die "cpptraj CV 계산에 실패했습니다: $output_dir/cpptraj.log"
fi
if [[ ! -s "$output_dir/cv.dat" ]]; then
    die "CV output이 생성되지 않았습니다: $output_dir/cv.dat"
fi

"$python" \
    "$script_dir/reweight.py" \
    --cv "$output_dir/cv.dat" \
    --log-directory "$simulation_work" \
    --components "$components" \
    --temperature 300 \
    --bin-width 0.25 \
    --output "$output_dir/pmf.tsv"

echo "GaMD reweighting 결과: $output_dir"
