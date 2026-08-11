#!/usr/bin/env bash
set -euo pipefail

dry_run=0
states_argument=""

while [[ $# -gt 0 ]]; do
    case "$1" in
        --dry-run)
            dry_run=1
            ;;
        -*)
            echo "사용법: $0 [--dry-run] [states.tsv]" >&2
            exit 2
            ;;
        *)
            if [[ -n "$states_argument" ]]; then
                echo "사용법: $0 [--dry-run] [states.tsv]" >&2
                exit 2
            fi
            states_argument=$1
            ;;
    esac
    shift
done

die() {
    echo "오류: $*" >&2
    exit 1
}

validate_states() {
    local expected_header=$'replica\ttemperature_K\tseed'
    local actual_header

    IFS= read -r actual_header < "$states_file"
    if [[ "$actual_header" != "$expected_header" ]]; then
        die "state table header가 올바르지 않습니다: $expected_header"
    fi

    if ! awk -F '\t' '
        NR == 1 { next }
        NF != 3 { exit 1 }
        $1 !~ /^[0-9][0-9][0-9]$/ { exit 1 }
        $2 !~ /^[0-9]+([.][0-9]+)?$/ || $2 <= 0 { exit 1 }
        $3 !~ /^[0-9]+$/ || $3 <= 0 { exit 1 }
        seen[$1]++ { exit 1 }
        count == 0 && $1 != "000" { exit 1 }
        count > 0 && $2 <= previous_temperature { exit 1 }
        { previous_temperature = $2; count++ }
        END { if (count < 2) exit 1 }
    ' "$states_file"; then
        die "state table에는 000부터 시작하는 두 개 이상의 고유 replica, 증가하는 positive temperature와 positive integer seed가 필요합니다: $states_file"
    fi
}

script_dir=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
input_pdb="$script_dir/structure/chignolin.pdb"
states_file=${states_argument:-"$script_dir/inputs/states.tsv"}
work_dir=${WORK_DIR:-"$script_dir/work"}
tleap=${TLEAP:-tleap}

if [[ ! -s "$input_pdb" ]]; then
    die "전처리한 PDB를 찾을 수 없습니다: $input_pdb"
fi

if [[ ! -s "$states_file" ]]; then
    die "replica table을 찾을 수 없습니다: $states_file"
fi

validate_states

if (( ! dry_run )); then
    if ! command -v "$tleap" >/dev/null 2>&1; then
        die "tleap을 찾을 수 없습니다: $tleap"
    fi
fi

replica_count=$(awk 'NR > 1 {count++} END {print count + 0}' "$states_file")
last_replica=$(awk 'END {print $1}' "$states_file")

if (( dry_run )); then
    echo "$replica_count 개 replica용 ff19SB/TIP3P system을 생성합니다."
    printf '%q -f %q\n' "$tleap" "$script_dir/inputs/tleap.in"
    echo "State table: $states_file"
    echo "생성 위치: $work_dir/000 ... $last_replica"
    exit 0
fi

echo "$replica_count 개 replica용 ff19SB/TIP3P system을 생성합니다."
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
