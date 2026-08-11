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
input_pdb="$script_dir/structure/chignolin.pdb"
states_file="$script_dir/inputs/states.tsv"
work_dir=${WORK_DIR:-"$script_dir/work"}
tleap=${TLEAP:-tleap}

if [[ ! -s "$input_pdb" ]]; then
    die "전처리한 PDB를 찾을 수 없습니다: $input_pdb"
fi

if [[ ! -s "$states_file" ]]; then
    die "replica table을 찾을 수 없습니다: $states_file"
fi

if (( ! dry_run )); then
    if ! command -v "$tleap" >/dev/null 2>&1; then
        die "tleap을 찾을 수 없습니다: $tleap"
    fi
fi

replica_count=$(awk 'NR > 1 {count++} END {print count + 0}' "$states_file")
if [[ "$replica_count" -ne 20 ]]; then
    die "states.tsv에는 20개 replica가 있어야 합니다: $replica_count"
fi

if (( dry_run )); then
    echo "20개 replica용 ff19SB/TIP3P system을 생성합니다."
    printf '%q -f %q\n' "$tleap" "$script_dir/inputs/tleap.in"
    echo "생성 위치: $work_dir/000 ... 019"
    exit 0
fi

echo "20개 replica용 ff19SB/TIP3P system을 생성합니다."
mkdir -p "$work_dir"
cp "$input_pdb" "$work_dir/input.pdb"

if ! (
    cd "$work_dir"
    "$tleap" \
        -f "$script_dir/inputs/tleap.in" \
        > leap.log 2>&1
); then
    die "tleap 실행에 실패했습니다. 확인할 파일: $work_dir/leap.log"
fi

for output in system.parm7 system.rst7; do
    if [[ ! -s "$work_dir/$output" ]]; then
        die "AMBER build output이 없습니다: $work_dir/$output"
    fi
done

while IFS=$'\t' read -r replica temperature_kelvin seed; do
    if [[ "$replica" == "replica" ]]; then
        continue
    fi

    replica_dir="$work_dir/$replica"
    mkdir -p "$replica_dir"

    cp "$work_dir/system.parm7" "$replica_dir/system.parm7"
    cp "$work_dir/system.rst7" "$replica_dir/system.rst7"

    sed \
        -e "s/@TEMP@/$temperature_kelvin/g" \
        -e "s/@SEED@/$seed/g" \
        "$script_dir/inputs/heat.in" \
        > "$replica_dir/heat.in"

    sed \
        -e "s/@TEMP@/$temperature_kelvin/g" \
        -e "s/@SEED@/$seed/g" \
        "$script_dir/inputs/equilibrate.in" \
        > "$replica_dir/equilibrate.in"

    sed \
        -e "s/@TEMP@/$temperature_kelvin/g" \
        -e "s/@SEED@/$seed/g" \
        "$script_dir/inputs/production.in" \
        > "$replica_dir/production.in"

    cp "$script_dir/inputs/minimize.in" "$replica_dir/minimize.in"
done < "$states_file"

cp "$states_file" "$work_dir/states.tsv"
echo "Replica input과 topology: $work_dir"
