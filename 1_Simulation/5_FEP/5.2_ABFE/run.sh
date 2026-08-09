#!/usr/bin/env bash
set -euo pipefail

dry_run=0
if [[ "${1:-}" == "--dry-run" ]]; then
    dry_run=1
    shift
fi
if [[ $# -ne 0 ]]; then
    echo "사용법: $0 [--dry-run]" >&2
    exit 2
fi

die() {
    echo "오류: $*" >&2
    exit 1
}

script_dir=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
work_dir=${WORK_DIR:-"$script_dir/work"}
states_file="$work_dir/states.tsv"
engine=${AMBER_ENGINE:-pmemd.cuda}
read -r -a amber_options <<< "${AMBER_OPTIONS:-}"

if [[ ! -s "$states_file" ]]; then
    die "build.sh를 먼저 실행해야 합니다: $states_file"
fi
if (( ! dry_run )); then
    if ! command -v "$engine" >/dev/null 2>&1; then
        die "AMBER engine을 찾을 수 없습니다: $engine"
    fi
    if [[ "$(basename "$engine")" != "pmemd.cuda" ]]; then
        die "ACES26 soft-core input은 pmemd.cuda로 실행해야 합니다: $engine"
    fi
fi

stage_state() {
    local existing=0
    local path
    for path in "$@"; do
        if [[ -s "$path" ]]; then
            existing=$((existing + 1))
        fi
    done
    if [[ "$existing" -eq 0 ]]; then
        echo missing
    elif [[ "$existing" -eq "$#" ]]; then
        echo complete
    else
        echo partial
    fi
}

run_stage() {
    local directory=$1
    local stage=$2
    local input_restart=$3
    local trajectory=$4
    local prefix="$directory/$stage"
    local required=("$prefix.out" "$prefix.rst7" "$prefix.info")
    local command=(
        "$engine" "${amber_options[@]}" -O
        -i "$directory/${stage%%.*}.in"
        -o "$prefix.out"
        -p "$directory/system.parm7"
        -c "$directory/$input_restart"
        -r "$prefix.rst7"
        -inf "$prefix.info"
    )
    if [[ "$trajectory" == yes ]]; then
        required+=("$prefix.nc")
        command+=(-x "$prefix.nc")
    fi
    if (( dry_run )); then
        printf '+ '
        printf '%q ' "${command[@]}"
        printf '\n'
        return
    fi
    local state
    state=$(stage_state "${required[@]}")
    if [[ "$state" == complete ]]; then
        return
    fi
    if [[ "$state" == partial ]]; then
        die "일부 output만 존재합니다: $prefix"
    fi
    if ! (cd "$directory" && "${command[@]}"); then
        die "$stage 계산에 실패했습니다: $prefix.out"
    fi
    for output in "${required[@]}"; do
        if [[ ! -s "$output" ]]; then
            die "$stage output이 생성되지 않았습니다: $output"
        fi
    done
}

if (( dry_run )); then
    echo "ABFE: restraint/charge/LJ 65 windows, window당 2 × 1 ns production"
fi

while IFS=$'\t' read -r method_stage leg window lambda seed directory; do
    if [[ "$method_stage" == stage ]]; then
        continue
    fi
    run_stage "$directory" minimize system.rst7 no
    run_stage "$directory" heat minimize.rst7 yes
    run_stage "$directory" equilibrate heat.rst7 yes
    run_stage "$directory" production.001 equilibrate.rst7 yes
    run_stage "$directory" production.002 production.001.rst7 yes
done < "$states_file"

if (( ! dry_run )); then
    echo "ABFE production이 완료되었습니다: $work_dir/windows"
fi
