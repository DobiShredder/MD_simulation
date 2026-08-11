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
seed_base=${RANDOM_SEED:-72000}
production_segments=1
read -r -a amber_options <<< "${AMBER_OPTIONS:-}"

if [[ ! "$seed_base" =~ ^[1-9][0-9]*$ ]]; then
    die "RANDOM_SEED는 positive integer여야 합니다."
fi

topology="$work_dir/system.parm7"
initial_restart="$work_dir/system.rst7"

stage_state() {
    local present=0
    local path

    for path in "$@"; do
        if [[ -s "$path" ]]; then
            present=$((present + 1))
        fi
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
        -i "$input_file"
        -o "$stage.out"
        -p system.parm7
        -c "$input_restart"
        -r "$stage.rst7"
        -inf "$stage.info"
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
        if [[ "$state" == complete ]]; then
            return 0
        fi
        if [[ "$state" == partial ]]; then
            die "$stage output이 일부만 존재합니다."
        fi
    fi

    run_command "$stage" "$work_dir" "${command[@]}"

    if (( ! dry_run )); then
        for output in "${required[@]}"; do
            if [[ ! -s "$output" ]]; then
                die "$stage output이 없습니다: $output"
            fi
        done
    fi
}

run_production_segment() {
    local segment_number=$1
    local segment
    local segment_dir
    local input_restart
    local previous_dir=""
    local state

    segment=$(printf '%03d' "$segment_number")
    segment_dir="$work_dir/production/$segment"

    if [[ "$segment_number" -eq 1 ]]; then
        input_restart=../../equilibrate.rst7
    else
        previous_dir="$work_dir/production/$(printf '%03d' "$((segment_number - 1))")"
        input_restart="../$(printf '%03d' "$((segment_number - 1))")/md.rst7"
    fi

    local required=(
        "$segment_dir/md.out"
        "$segment_dir/md.info"
        "$segment_dir/md.rst7"
        "$segment_dir/md.nc"
        "$segment_dir/COLVAR"
        "$segment_dir/HILLS"
        "$segment_dir/FUNNEL_GRID"
    )

    if (( ! dry_run )); then
        state=$(stage_state "${required[@]}")
        if [[ "$state" == complete ]]; then
            return 0
        fi
        if [[ "$state" == partial ]]; then
            die "production $segment output이 일부만 존재합니다."
        fi

        mkdir -p "$segment_dir"
        render_amber_input \
            inputs/production.in.template \
            "$segment_dir/production.in" \
            "$((seed_base + 100 + segment_number))"
        cp "$work_dir/funnel-reference.pdb" "$segment_dir/funnel-reference.pdb"

        if [[ "$segment_number" -eq 1 ]]; then
            cp "$work_dir/plumed.initial.dat" "$segment_dir/plumed.dat"
        else
            if [[ ! -s "$previous_dir/HILLS" ]]; then
                die "이전 HILLS가 없습니다: $previous_dir/HILLS"
            fi
            cp "$work_dir/plumed.restart.dat" "$segment_dir/plumed.dat"
            cp "$previous_dir/HILLS" "$segment_dir/HILLS"
        fi
    fi

    run_command "production $segment" "$segment_dir" \
        "$engine" "${amber_options[@]}" -O \
        -i production.in \
        -o md.out \
        -p ../../system.parm7 \
        -c "$input_restart" \
        -r md.rst7 \
        -x md.nc \
        -inf md.info

    if (( ! dry_run )); then
        for output in "${required[@]}"; do
            if [[ ! -s "$output" ]]; then
                die "production $segment output이 없습니다: $output"
            fi
        done
    fi
}

if (( ! dry_run )); then
    for executable in "$engine" "$plumed"; do
        if ! command -v "$executable" >/dev/null 2>&1; then
            die "실행 파일을 찾을 수 없습니다: $executable"
        fi
    done

    for input in \
        "$topology" \
        "$initial_restart" \
        "$work_dir/funnel-reference.pdb" \
        "$work_dir/plumed.initial.dat" \
        "$work_dir/atom_count.txt"; do
        if [[ ! -s "$input" ]]; then
            die "build.sh를 먼저 실행하세요: $input"
        fi
    done

    mkdir -p "$work_dir/inputs"
    cp inputs/minimize-solvent.in "$work_dir/inputs/minimize-solvent.in"
    cp inputs/minimize-all.in "$work_dir/inputs/minimize-all.in"
    render_amber_input inputs/heat.in.template "$work_dir/inputs/heat.in" "$((seed_base + 1))"
    render_amber_input inputs/equilibrate.in.template "$work_dir/inputs/equilibrate.in" "$((seed_base + 2))"

    atom_count=$(<"$work_dir/atom_count.txt")
    (
        cd "$work_dir"
        "$plumed" driver \
            --plumed plumed.initial.dat \
            --parse-only \
            --natoms "$atom_count"
    )
fi

run_standard_stage minimize-solvent inputs/minimize-solvent.in system.rst7 no system.rst7
run_standard_stage minimize-all inputs/minimize-all.in minimize-solvent.rst7 no
run_standard_stage heat inputs/heat.in minimize-all.rst7 yes minimize-all.rst7
run_standard_stage equilibrate inputs/equilibrate.in heat.rst7 yes heat.rst7

for segment_number in $(seq 1 "$production_segments"); do
    run_production_segment "$segment_number"
done

if (( ! dry_run )); then
    echo "1 ns Funnel MetaD production 완료: $work_dir/production"
fi
