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
if [[ "$work_dir" != /* ]]; then
    work_dir="$(pwd)/$work_dir"
fi
engine=${AMBER_ENGINE:-pmemd.cuda}
random_seed=${RANDOM_SEED:-41001}
production_segments=1
read -r -a amber_options <<< "${AMBER_OPTIONS:-}"

if [[ ! "$random_seed" =~ ^[1-9][0-9]*$ ]]; then
    die "RANDOM_SEED는 positive integer여야 합니다: $random_seed"
fi

topology="$work_dir/system.parm7"
initial_restart="$work_dir/system.rst7"
heat_input="$work_dir/heat.in"

if (( ! dry_run )); then
    if ! command -v "$engine" >/dev/null 2>&1; then
        die "AMBER engine을 찾을 수 없습니다: $engine"
    fi
    if [[ ! -s "$topology" || ! -s "$initial_restart" ]]; then
        die "build.sh를 먼저 실행해야 합니다: $work_dir"
    fi

    mkdir -p "$work_dir"
    sed "s/@RANDOM_SEED@/$random_seed/g" \
        "$script_dir/inputs/heat.in.template" \
        > "$heat_input"
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

run_command() {
    local stage=$1
    shift

    if (( dry_run )); then
        printf '+ '
        printf '%q ' "$@"
        printf '\n'
        return
    fi

    echo "실행: $stage"
    if ! (
        cd "$work_dir"
        "$@"
    ); then
        die "$stage 계산에 실패했습니다: $work_dir"
    fi
}

run_md_stage() {
    local stage=$1
    local input_file=$2
    local input_restart=$3
    local with_trajectory=$4
    local with_gamd_log=$5
    local gamd_state_input=${6:-}
    local prefix="$work_dir/$stage"
    local required=("$prefix.out" "$prefix.rst7" "$prefix.info")
    local command=(
        "$engine" "${amber_options[@]}" -O
        -i "$input_file"
        -o "$prefix.out"
        -p "$topology"
        -c "$input_restart"
        -r "$prefix.rst7"
        -inf "$prefix.info"
    )

    if [[ "$with_trajectory" == yes ]]; then
        required+=("$prefix.nc")
        command+=(-x "$prefix.nc")
    fi
    if [[ "$with_gamd_log" == yes ]]; then
        required+=("$prefix.gamd.log" "$prefix.gamd.rst")
        command+=(-gamd "$prefix.gamd.log")
    fi

    if (( dry_run )); then
        run_command "$stage" "${command[@]}"
        return
    fi

    state=$(stage_state "${required[@]}")
    if [[ "$state" == complete ]]; then
        return
    fi
    if [[ "$state" == partial ]]; then
        die "$stage output이 일부만 존재합니다. 해당 stage output을 확인하세요."
    fi

    if [[ -n "$gamd_state_input" ]]; then
        if [[ ! -s "$gamd_state_input" ]]; then
            die "이전 GaMD state를 찾을 수 없습니다: $gamd_state_input"
        fi
        cp "$gamd_state_input" "$work_dir/gamd-restart.dat"
    fi

    run_command "$stage" "${command[@]}"
    if [[ "$with_gamd_log" == yes ]]; then
        if [[ ! -s "$work_dir/gamd-restart.dat" ]]; then
            die "$stage GaMD state가 생성되지 않았습니다: $work_dir/gamd-restart.dat"
        fi
        cp "$work_dir/gamd-restart.dat" "$prefix.gamd.rst"
    fi
    for output in "${required[@]}"; do
        if [[ ! -s "$output" ]]; then
            die "$stage output이 생성되지 않았습니다: $output"
        fi
    done
}

if (( dry_run )); then
    echo "Dual-boost GaMD: 200 ps heating + 100 ps NPT + 4 ns parameter preparation + 1 ns production"
fi

run_md_stage minimize "$script_dir/inputs/minimize.in" "$initial_restart" no no
run_md_stage heat "${heat_input:-$script_dir/inputs/heat.in.template}" "$work_dir/minimize.rst7" yes no
run_md_stage equilibrate "$script_dir/inputs/equilibrate.in" "$work_dir/heat.rst7" yes no
run_md_stage gamd_prepare "$script_dir/inputs/gamd_prepare.in" "$work_dir/equilibrate.rst7" yes yes

for segment_number in $(seq 1 "$production_segments"); do
    segment=$(printf 'production.%03d' "$segment_number")
    if [[ "$segment_number" -eq 1 ]]; then
        input_restart="$work_dir/gamd_prepare.rst7"
        gamd_state_input="$work_dir/gamd_prepare.gamd.rst"
    else
        previous=$(printf 'production.%03d.rst7' "$((segment_number - 1))")
        input_restart="$work_dir/$previous"
        gamd_state_input="$work_dir/$(printf 'production.%03d.gamd.rst' "$((segment_number - 1))")"
    fi
    run_md_stage "$segment" "$script_dir/inputs/production.in" "$input_restart" yes yes "$gamd_state_input"
done

if (( ! dry_run )); then
    echo "1 ns GaMD production이 완료되었습니다: $work_dir"
fi
