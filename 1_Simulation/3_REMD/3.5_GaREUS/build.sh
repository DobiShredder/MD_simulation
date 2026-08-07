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
python_bin=${PYTHON:-python3}

for input_file in "$input_pdb" "$states_file"; do
    if [[ ! -s "$input_file" ]]; then
        die "필요한 input을 찾을 수 없습니다: $input_file"
    fi
done

if (( ! dry_run )); then
    if ! command -v "$tleap" >/dev/null 2>&1; then
        die "tleap을 찾을 수 없습니다: $tleap"
    fi
    if ! "$python_bin" -c "import parmed" >/dev/null 2>&1; then
        die "ParmEd가 필요합니다: $python_bin -m pip install parmed"
    fi
fi

window_count=$(awk 'NR > 1 {count++} END {print count + 0}' "$states_file")
if [[ "$window_count" -ne 19 ]]; then
    die "states.tsv에는 19개 window가 있어야 합니다: $window_count"
fi

if (( dry_run )); then
    echo "19개 GaREUS window용 ff19SB/TIP3P system을 생성합니다."
    echo "CV: :1@CA–:10@CA, 6–24 Å, 1 Å spacing"
    echo "생성 위치: $work_dir/replicas/000 ... 018"
    exit 0
fi

echo "19개 GaREUS window용 ff19SB/TIP3P system을 생성합니다."
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

"$python_bin" "$script_dir/make_restraints.py" \
    "$work_dir/system.parm7" \
    "$work_dir/system.rst7" \
    "$states_file" \
    "$work_dir/replicas"

while IFS=$'\t' read -r replica _ seed; do
    if [[ "$replica" == "replica" ]]; then
        continue
    fi

    replica_dir="$work_dir/replicas/$replica"
    restraint_file="$replica_dir/distance.RST"

    cp "$work_dir/system.parm7" "$replica_dir/system.parm7"
    cp "$work_dir/system.rst7" "$replica_dir/system.rst7"

    for stage in minimize heat equilibrate gamd_prepare; do
        sed \
            -e "s|@SEED@|$seed|g" \
            -e "s|@DISANG@|$restraint_file|g" \
            -e "s|@DUMPAVE@|$replica_dir/restraint.$stage.dat|g" \
            "$script_dir/inputs/$stage.in" \
            > "$replica_dir/$stage.in"
    done

    sed \
        -e "s|@SEED@|$seed|g" \
        -e "s|@DISANG@|$restraint_file|g" \
        "$script_dir/inputs/production.in" \
        > "$replica_dir/production.template.in"
done < "$states_file"

cp "$states_file" "$work_dir/states.tsv"
echo "GaREUS topology, restraint와 input: $work_dir/replicas"

