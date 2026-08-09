#!/usr/bin/env bash
set -euo pipefail

usage() {
    echo "사용법: $0 [--dry-run] KCSA.pdb" >&2
}

die() {
    echo "오류: $*" >&2
    exit 1
}

make_absolute_path() {
    local path=$1
    local directory
    local filename

    directory=$(dirname "$path")
    filename=$(basename "$path")
    directory=$(cd "$directory" && pwd -P)

    echo "$directory/$filename"
}

show_dry_run() {
    printf 'mkdir -p %q\n' "$work_dir"
    printf 'cd %q\n' "$work_dir"
    printf '%q \\\n' "$memgen"
    printf '  --pdb %q \\\n' "$input_absolute"
    printf '  --preoriented \\\n'
    printf '  --mem_opt 3 \\\n'
    printf '  --lipids %q \\\n' "$lipids"
    printf '  --ratio %q \\\n' "$lipid_ratio"
    printf '  --dist_wat %q \\\n' "$water_distance_angstrom"
    printf '  --salt \\\n'
    printf '  --salt_c K+ \\\n'
    printf '  --salt_a Cl- \\\n'
    printf '  --saltcon %q \\\n' "$salt_concentration_molar"
    printf '  --keepligs \\\n'
    printf '  --nottrim \\\n'
    printf '  --notprotonate'
    if (( ${#memgen_options[@]} > 0 )); then
        printf ' %q' "${memgen_options[@]}"
    fi
    printf '\n'
}

run_packmol_memgen() {
    mkdir -p "$work_dir"

    if ! (
        cd "$work_dir"

        "$memgen" \
            --pdb "$input_absolute" \
            --preoriented \
            --mem_opt 3 \
            --lipids "$lipids" \
            --ratio "$lipid_ratio" \
            --dist_wat "$water_distance_angstrom" \
            --salt \
            --salt_c K+ \
            --salt_a Cl- \
            --saltcon "$salt_concentration_molar" \
            --keepligs \
            --nottrim \
            --notprotonate \
            "${memgen_options[@]}" \
            > packmol-memgen.log 2>&1
    ); then
        die "PACKMOL-Memgen 실행에 실패했습니다. " \
            "확인할 파일: $work_dir/packmol-memgen.log"
    fi
}

save_coordinate_file() {
    local -a candidates

    shopt -s nullglob
    candidates=("$work_dir"/bilayer_*.pdb)

    if [[ ${#candidates[@]} -ne 1 ]]; then
        die "bilayer_*.pdb가 1개여야 하지만 ${#candidates[@]}개입니다. " \
            "확인할 경로: $work_dir"
    fi

    cp "${candidates[0]}" "$work_dir/system-coordinates.pdb"
}

# Command-line option 처리
dry_run=0

if [[ "${1:-}" == "--dry-run" ]]; then
    dry_run=1
    shift
fi

if [[ $# -ne 1 ]]; then
    usage
    exit 2
fi

# Input과 사용자 설정
input_pdb=$1
memgen=${PACKMOL_MEMGEN:-packmol-memgen}
lipids=${LIPIDS:-POPC:POPE:CHL1}
lipid_ratio=${LIPID_RATIO:-90:5:5}
salt_concentration_molar=${SALT_CONCENTRATION:-0.15}
water_distance_angstrom=${WATER_DISTANCE:-20}
read -r -a memgen_options <<< "${PACKMOL_MEMGEN_OPTIONS:-}"

script_dir=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
work_dir=${WORK_DIR:-"$script_dir/work/packed"}

# Lipid 목록과 비율 중 하나만 잘못 바꾸는 실수를 막습니다.
# 다른 조성을 쓸 때는 두 값을 함께 바꾼 뒤 override를 활성화합니다.
composition="$lipids:$lipid_ratio"
tutorial_composition="POPC:POPE:CHL1:90:5:5"

if [[ "$composition" != "$tutorial_composition" ]]; then
    if [[ -z "${ALLOW_CUSTOM_COMPOSITION:-}" ]]; then
        echo "오류: 다른 lipid 조성을 사용하려면 " \
            "ALLOW_CUSTOM_COMPOSITION=1을 설정하세요." >&2
        exit 2
    fi
fi

if (( ! dry_run )); then
    if [[ ! -f "$input_pdb" ]]; then
        die "KcsA PDB를 찾을 수 없습니다: $input_pdb"
    fi

    if ! command -v "$memgen" >/dev/null 2>&1; then
        die "PACKMOL-Memgen을 찾을 수 없습니다: $memgen"
    fi
fi

input_absolute=$(make_absolute_path "$input_pdb")

if (( dry_run )); then
    show_dry_run
    exit 0
fi

# 실행 workflow
echo "KcsA 막 좌표를 생성합니다 " \
    "($lipids, $lipid_ratio, ${salt_concentration_molar} M KCl)."

run_packmol_memgen
save_coordinate_file

echo "좌표 생성 결과: $work_dir/system-coordinates.pdb"
