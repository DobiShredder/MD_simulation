#!/usr/bin/env bash
set -euo pipefail

dry_run=0
if [[ "${1:-}" == "--dry-run" ]]; then
    dry_run=1
    shift
fi
if [[ $# -lt 2 ]]; then
    echo "사용법: run.sh [--dry-run] TOPOLOGY TRAJECTORY [TRAJECTORY ...]" >&2
    exit 2
fi

die() {
    echo "오류: $*" >&2
    exit 1
}

absolute_file() {
    local path=$1
    local directory
    local filename

    directory=$(cd "$(dirname "$path")" && pwd -P)
    filename=$(basename "$path")
    echo "$directory/$filename"
}

tutorial_dir=${TUTORIAL_DIR:?TUTORIAL_DIR가 지정되지 않았습니다.}
expected_outputs=${EXPECTED_OUTPUTS:?EXPECTED_OUTPUTS가 지정되지 않았습니다.}
cpptraj=${CPPTRAJ:-cpptraj}
output_dir=${OUTPUT_DIR:-"$tutorial_dir/output"}
start_frame=${START_FRAME:-1}
stop_frame=${STOP_FRAME:-last}
stride=${STRIDE:-1}
frame_interval_ps=${FRAME_INTERVAL_PS:-10.0}

topology=$1
shift
trajectories=("$@")

if [[ ! "$start_frame" =~ ^[1-9][0-9]*$ ]]; then
    die "START_FRAME은 positive integer여야 합니다."
fi
if [[ "$stop_frame" != last && ! "$stop_frame" =~ ^[1-9][0-9]*$ ]]; then
    die "STOP_FRAME은 last 또는 positive integer여야 합니다."
fi
if [[ ! "$stride" =~ ^[1-9][0-9]*$ ]]; then
    die "STRIDE는 positive integer여야 합니다."
fi
if ! awk -v value="$frame_interval_ps" \
    'BEGIN {exit !(value ~ /^[0-9]+([.][0-9]+)?$/ && value > 0)}'; then
    die "FRAME_INTERVAL_PS는 0보다 큰 number여야 합니다."
fi

if (( dry_run )); then
    echo "cpptraj input: $tutorial_dir/inputs/cpptraj.in"
    echo "frame selection: start=$start_frame stop=$stop_frame stride=$stride"
    echo "output: $output_dir"
    exit 0
fi

if ! command -v "$cpptraj" >/dev/null 2>&1; then
    die "cpptraj을 찾을 수 없습니다: $cpptraj"
fi
if [[ ! -s "$topology" ]]; then
    die "topology를 찾을 수 없습니다: $topology"
fi
if [[ ! -s "$tutorial_dir/inputs/cpptraj.in" ]]; then
    die "cpptraj action input이 없습니다: $tutorial_dir/inputs/cpptraj.in"
fi
for trajectory in "${trajectories[@]}"; do
    if [[ ! -s "$trajectory" ]]; then
        die "trajectory를 찾을 수 없습니다: $trajectory"
    fi
done

topology=$(absolute_file "$topology")
for index in "${!trajectories[@]}"; do
    trajectories[$index]=$(absolute_file "${trajectories[$index]}")
done
if [[ "$output_dir" != /* ]]; then
    output_dir="$(pwd)/$output_dir"
fi

mkdir -p "$output_dir"
rendered_input="$output_dir/cpptraj.in"
{
    printf 'parm "%s"\n' "$topology"
    for trajectory in "${trajectories[@]}"; do
        printf 'trajin "%s" %s %s %s\n' \
            "$trajectory" "$start_frame" "$stop_frame" "$stride"
    done
    sed -n '/^[^#]/p' "$tutorial_dir/inputs/cpptraj.in"
} > "$rendered_input"

effective_interval_ps=$(awk -v interval="$frame_interval_ps" -v step="$stride" \
    'BEGIN {printf "%.10g", interval * step}')
{
    printf 'key\tvalue\n'
    printf 'topology\t%s\n' "$topology"
    printf 'start_frame\t%s\n' "$start_frame"
    printf 'stop_frame\t%s\n' "$stop_frame"
    printf 'stride\t%s\n' "$stride"
    printf 'frame_interval_ps\t%s\n' "$frame_interval_ps"
    printf 'effective_frame_interval_ps\t%s\n' "$effective_interval_ps"
} > "$output_dir/run_metadata.tsv"

{
    printf 'index\ttrajectory\n'
    for index in "${!trajectories[@]}"; do
        printf '%d\t%s\n' "$((index + 1))" "${trajectories[$index]}"
    done
} > "$output_dir/trajectories.tsv"

if ! (
    cd "$output_dir"
    "$cpptraj" -i cpptraj.in > cpptraj.log 2>&1
); then
    die "cpptraj 실행에 실패했습니다: $output_dir/cpptraj.log"
fi

for output in $expected_outputs; do
    if [[ ! -s "$output_dir/$output" ]]; then
        die "output이 없습니다: $output_dir/$output"
    fi
done

echo "Analysis 결과: $output_dir"
