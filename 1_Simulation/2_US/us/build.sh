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

# 사용자 설정과 input/output 경로
script_dir=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
window_file=${WINDOW_FILE:-"$script_dir/windows.tsv"}
seed_dir=${SEED_DIR:-"$script_dir/../rmd/work/seeds"}
seed_metadata="$seed_dir/seeds.tsv"
topology=${TOPOLOGY:-"$script_dir/../work/system.parm7"}
work_dir=${WORK_DIR:-"$script_dir/work"}
window_root="$work_dir/windows"

# Window 설정 읽기
if [[ ! -s "$window_file" ]]; then
    die "window 설정을 찾을 수 없습니다: $window_file"
fi

window_rows=()
previous_center=""

while read -r center_angstrom force_kcal_mol_angstrom2 extra_field; do
    if [[ -z "${center_angstrom:-}" ]]; then
        continue
    fi

    if [[ "$center_angstrom" == \#* ]]; then
        continue
    fi

    if [[ -n "${extra_field:-}" ]]; then
        die "${window_file}에는 CENTER_A와 FORCE 두 열만 허용됩니다."
    fi

    if [[ ! "$center_angstrom" =~ ^[0-9]+([.][0-9]+)?$ ]]; then
        die "window center는 숫자여야 합니다: $center_angstrom"
    fi

    if [[ ! "$force_kcal_mol_angstrom2" =~ ^[0-9]+([.][0-9]+)?$ ]]; then
        die "window force constant는 숫자여야 합니다: $force_kcal_mol_angstrom2"
    fi

    if ! awk \
        -v center="$center_angstrom" \
        -v force="$force_kcal_mol_angstrom2" \
        'BEGIN { exit !(center > 0 && force > 0) }'; then
        die "window center와 force constant는 양수여야 합니다:" \
            "$center_angstrom $force_kcal_mol_angstrom2"
    fi

    if [[ -n "$previous_center" ]]; then
        if ! awk \
            -v previous="$previous_center" \
            -v center="$center_angstrom" \
            'BEGIN { exit !(center > previous) }'; then
            die "window center는 중복 없이 증가해야 합니다: $previous_center -> $center_angstrom"
        fi
    fi

    window_rows+=("$center_angstrom $force_kcal_mol_angstrom2")
    previous_center=$center_angstrom
done < "$window_file"

if (( ${#window_rows[@]} == 0 )); then
    die "${window_file}에 window가 없습니다."
fi

# Seed와 공통 topology 확인
if (( ! dry_run )); then
    if [[ ! -s "$topology" ]]; then
        die "공통 topology를 찾을 수 없습니다: $topology"
    fi

    if [[ ! -s "$seed_metadata" ]]; then
        die "seed metadata를 찾을 수 없습니다: $seed_metadata"
    fi

    if [[ -e "$window_root" ]]; then
        die "window output이 이미 존재합니다: $window_root"
    fi

    for row_index in "${!window_rows[@]}"; do
        window_number=$((row_index + 1))
        printf -v window_id '%03d' "$window_number"

        metadata_line_number=$((row_index + 2))
        metadata_row=$(awk \
            -v line="$metadata_line_number" \
            'NR == line { print $1, $2, $3 }' \
            "$seed_metadata")

        if [[ -z "$metadata_row" ]]; then
            die "${seed_metadata}에 $window_id window가 없습니다."
        fi

        read -r metadata_window metadata_center _ <<< "$metadata_row"

        if [[ "$metadata_window" != "$window_number" ]]; then
            die "${seed_metadata}의 window 순서가 windows.tsv와 다릅니다: $window_id"
        fi

        read -r configured_center _ <<< "${window_rows[$row_index]}"

        if ! awk \
            -v configured="$configured_center" \
            -v observed="$metadata_center" \
            'BEGIN {
                difference = configured - observed
                if (difference < 0) difference = -difference
                exit !(difference < 1e-6)
            }'; then
            die "$window_id center가 seed metadata와 다릅니다: $configured_center vs $metadata_center"
        fi

        seed_restart="$seed_dir/seed_${window_id}.rst7"

        if [[ ! -s "$seed_restart" ]]; then
            die "seed restart를 찾을 수 없습니다: $seed_restart"
        fi
    done
fi

# Dry-run에서는 생성할 규모와 경로만 보여줍니다.
if (( dry_run )); then
    echo "공통 topology: $topology"
    echo "Seed directory: $seed_dir"
    echo "생성할 umbrella window: ${#window_rows[@]}개 ($window_root)"
    exit 0
fi

# Window별 topology, seed, restraint와 metadata를 생성합니다.
mkdir -p "$window_root"

for row_index in "${!window_rows[@]}"; do
    read -r center_angstrom force_kcal_mol_angstrom2 <<< "${window_rows[$row_index]}"

    window_number=$((row_index + 1))
    printf -v window_id '%03d' "$window_number"
    window_dir="$window_root/$window_id"

    mkdir -p "$window_dir"
    cp "$topology" "$window_dir/system.parm7"
    cp "$seed_dir/seed_${window_id}.rst7" "$window_dir/seed.rst7"

    sed \
        -e "s/CENTER/$center_angstrom/g" \
        -e "s/FORCE/$force_kcal_mol_angstrom2/g" \
        "$script_dir/inputs/restraint.RST.template" \
        > "$window_dir/restraint.RST"

    printf 'window\tcenter_A\tforce_kcal_mol_A2\n%s\t%s\t%s\n' \
        "$window_id" \
        "$center_angstrom" \
        "$force_kcal_mol_angstrom2" \
        > "$window_dir/window.tsv"
done

echo "동일 topology를 사용하는 umbrella window ${#window_rows[@]}개를 생성했습니다:" \
    "$window_root"
