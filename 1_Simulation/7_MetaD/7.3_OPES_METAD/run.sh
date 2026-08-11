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

work_dir=${WORK_DIR:-work}
engine=${AMBER_ENGINE:-pmemd.cuda}
plumed=${PLUMED:-plumed}
seed_base=${RANDOM_SEED:-73000}
production_segments=1
read -r -a amber_options <<< "${AMBER_OPTIONS:-}"

[[ "$seed_base" =~ ^[1-9][0-9]*$ ]] || die "RANDOM_SEED는 positive integer여야 합니다."
topology="$work_dir/system.parm7"
initial_restart="$work_dir/system.rst7"

stage_state() {
    local present=0
    local path
    for path in "$@"; do
        [[ -s "$path" ]] && present=$((present + 1))
    done
    if [[ "$present" -eq 0 ]]; then
        echo missing
    elif [[ "$present" -eq "$#" ]]; then
        echo complete
    else
        echo partial
    fi
}

render_amber_input() {
    local template=$1
    local output=$2
    local seed=$3
    sed "s/@RANDOM_SEED@/$seed/g" "$template" > "$output"
}

run_command() {
    local stage=$1
    local directory=$2
    shift 2
    if (( dry_run )); then
        printf '+ (cd %q && ' "$directory"
        printf '%q ' "$@"
        printf ')\n'
        return
    fi
    echo "실행: $stage"
    if ! (
        cd "$directory"
        "$@"
    ); then
        die "$stage 계산에 실패했습니다: $directory"
    fi
}

run_standard_stage() {
    local stage=$1
    local input_file=$2
    local input_restart=$3
    local write_trajectory=$4
    local reference_restart=${5:-}
    local prefix="$work_dir/$stage"
    local required=("$prefix.out" "$prefix.info" "$prefix.rst7")
    local command=(
        "$engine" "${amber_options[@]}" -O
        -i "$input_file" -o "$stage.out"
        -p system.parm7 -c "$input_restart"
        -r "$stage.rst7" -inf "$stage.info"
    )
    local state

    if [[ "$write_trajectory" == yes ]]; then
        required+=("$prefix.nc")
        command+=(-x "$stage.nc")
    fi
    if [[ -n "$reference_restart" ]]; then
        command+=(-ref "$reference_restart")
    fi
    if (( ! dry_run )); then
        state=$(stage_state "${required[@]}")
        [[ "$state" != complete ]] || return 0
        [[ "$state" != partial ]] || die "$stage output이 일부만 존재합니다."
    fi
    run_command "$stage" "$work_dir" "${command[@]}"
    if (( ! dry_run )); then
        for output in "${required[@]}"; do
            [[ -s "$output" ]] || die "$stage output이 없습니다: $output"
        done
    fi
}

render_plumed_input() {
    local output=$1
    local continuation=$2
    if [[ "$continuation" == yes ]]; then
        sed \
            -e 's/@RESTART@/RESTART/' \
            -e 's/@STATE_RFILE@/STATE_RFILE=opes.state/' \
            inputs/plumed.dat.template \
            > "$output"
    else
        sed \
            -e 's/@RESTART@//' \
            -e 's/@STATE_RFILE@//' \
            inputs/plumed.dat.template \
            > "$output"
    fi
}

run_production_segment() {
    local number=$1
    local segment
    local segment_dir
    local previous_dir=""
    local input_restart
    local continuation=no
    local state

    segment=$(printf '%03d' "$number")
    segment_dir="$work_dir/production/$segment"
    if [[ "$number" -eq 1 ]]; then
        input_restart=../../equilibrate.rst7
    else
        previous_dir="$work_dir/production/$(printf '%03d' "$((number - 1))")"
        input_restart="../$(printf '%03d' "$((number - 1))")/md.rst7"
        continuation=yes
    fi

    local required=(
        "$segment_dir/md.out" "$segment_dir/md.info"
        "$segment_dir/md.rst7" "$segment_dir/md.nc"
        "$segment_dir/COLVAR" "$segment_dir/KERNELS"
        "$segment_dir/opes.state"
    )

    if (( ! dry_run )); then
        state=$(stage_state "${required[@]}")
        [[ "$state" != complete ]] || return 0
        [[ "$state" != partial ]] || die "production $segment output이 일부만 존재합니다."
        mkdir -p "$segment_dir"
        render_amber_input inputs/production.in.template \
            "$segment_dir/production.in" "$((seed_base + 100 + number))"
        render_plumed_input "$segment_dir/plumed.dat" "$continuation"

        if [[ "$continuation" == yes ]]; then
            [[ -s "$previous_dir/opes.state" ]] || die "이전 OPES state가 없습니다."
            [[ -s "$previous_dir/KERNELS" ]] || die "이전 KERNELS가 없습니다."
            cp "$previous_dir/opes.state" "$segment_dir/opes.state"
            cp "$previous_dir/KERNELS" "$segment_dir/KERNELS"
        fi
    fi

    run_command "production $segment" "$segment_dir" \
        "$engine" "${amber_options[@]}" -O \
        -i production.in -o md.out \
        -p ../../system.parm7 -c "$input_restart" \
        -r md.rst7 -x md.nc -inf md.info

    if (( ! dry_run )); then
        for output in "${required[@]}"; do
            [[ -s "$output" ]] || die "production $segment output이 없습니다: $output"
        done
    fi
}

if (( ! dry_run )); then
    command -v "$engine" >/dev/null 2>&1 || die "AMBER engine을 찾을 수 없습니다: $engine"
    command -v "$plumed" >/dev/null 2>&1 || die "PLUMED를 찾을 수 없습니다: $plumed"
    [[ -s "$topology" && -s "$initial_restart" ]] || die "build.sh를 먼저 실행하세요: $work_dir"
    [[ -s "$work_dir/atom_count.txt" ]] || die "atom_count.txt가 없습니다. build.sh를 다시 실행하세요."
    mkdir -p "$work_dir"
    mkdir -p "$work_dir/inputs"
    cp inputs/minimize.in "$work_dir/inputs/minimize.in"
    render_amber_input inputs/heat.in.template "$work_dir/inputs/heat.in" "$((seed_base + 1))"
    render_amber_input inputs/equilibrate.in.template "$work_dir/inputs/equilibrate.in" "$((seed_base + 2))"
    render_plumed_input "$work_dir/plumed.parse.dat" no
    atom_count=$(<"$work_dir/atom_count.txt")
    (
        cd "$work_dir"
        "$plumed" driver \
            --plumed plumed.parse.dat \
            --parse-only \
            --natoms "$atom_count"
    )
fi

run_standard_stage minimize inputs/minimize.in system.rst7 no
run_standard_stage heat inputs/heat.in minimize.rst7 yes minimize.rst7
run_standard_stage equilibrate inputs/equilibrate.in heat.rst7 yes

for segment_number in $(seq 1 "$production_segments"); do
    run_production_segment "$segment_number"
done

if (( ! dry_run )); then
    echo "1 ns OPES_METAD production 완료: $work_dir/production"
fi
