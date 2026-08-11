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
    local expected_header=$'replica\teffective_temperature_K\tlambda_pp\tlambda_pw\tseed'
    local actual_header

    IFS= read -r actual_header < "$states_file"
    if [[ "$actual_header" != "$expected_header" ]]; then
        die "state table header가 올바르지 않습니다: $expected_header"
    fi

    if ! awk -F '\t' '
        function absolute(value) { return value < 0 ? -value : value }
        NR == 1 { next }
        NF != 5 { exit 1 }
        $1 !~ /^[0-9][0-9][0-9]$/ { exit 1 }
        $2 !~ /^[0-9]+([.][0-9]+)?$/ || $2 < 300 { exit 1 }
        $3 !~ /^[0-9]+([.][0-9]+)?$/ || $3 <= 0 || $3 > 1 { exit 1 }
        $4 !~ /^[0-9]+([.][0-9]+)?$/ || $4 <= 0 || $4 > 1 { exit 1 }
        $5 !~ /^[0-9]+$/ || $5 <= 0 { exit 1 }
        seen[$1]++ { exit 1 }
        count == 0 && ($1 != "000" || absolute($2 - 300) > 0.000001) { exit 1 }
        count > 0 && $2 <= previous_temperature { exit 1 }
        absolute($3 - 300 / $2) > 0.00001 { exit 1 }
        absolute($4 * $4 - $3) > 0.00001 { exit 1 }
        { previous_temperature = $2; count++ }
        END { if (count < 2) exit 1 }
    ' "$states_file"; then
        die "REST2 state table에는 000/300 K 기준 state, 증가하는 effective temperature, lambda_pp=300/T, lambda_pw=sqrt(lambda_pp), 고유 replica와 positive integer seed가 필요합니다: $states_file"
    fi
}

input_pdb="structure/chignolin.pdb"
states_file=${states_argument:-"inputs/states.tsv"}
work_dir=${WORK_DIR:-"work"}
tleap=${TLEAP:-tleap}
gmx=${GROMACS:-gmx}
plumed=${PLUMED:-plumed}
python_bin=${PYTHON:-python3}
energy_tolerance=${ENERGY_TOLERANCE_KJ_MOL:-0.1}

for input_file in "$input_pdb" "$states_file"; do
    if [[ ! -s "$input_file" ]]; then
        die "필요한 input을 찾을 수 없습니다: $input_file"
    fi
done

validate_states

if (( ! dry_run )); then
    for executable in "$tleap" "$gmx" "$plumed" "$python_bin"; do
        if ! command -v "$executable" >/dev/null 2>&1; then
            die "실행 파일을 찾을 수 없습니다: $executable"
        fi
    done

    if ! "$python_bin" -c "import parmed" >/dev/null 2>&1; then
        die "ParmEd가 필요합니다: $python_bin -m pip install -r requirements.txt"
    fi
fi

replica_count=$(awk 'NR > 1 {count++} END {print count + 0}' "$states_file")
last_replica=$(awk 'END {print $1}' "$states_file")

if (( dry_run )); then
    echo "ff19SB/TIP3P AMBER system을 GROMACS topology로 변환합니다."
    echo "Protein atom만 표시하고 $replica_count 개 REST2 topology를 생성합니다."
    echo "Scale 1.0 topology와 원본 topology의 potential energy를 비교합니다."
    echo "State table: $states_file"
    echo "생성 위치: $work_dir/000 ... $last_replica"
    exit 0
fi

echo "ff19SB/TIP3P AMBER system을 생성합니다."
mkdir -p "$work_dir"
cp "$input_pdb" "$work_dir/input.pdb"
cp inputs/tleap.in "$work_dir/tleap.in"

if ! (
    cd "$work_dir"
    "$tleap" \
        -f tleap.in \
        > leap.log 2>&1
); then
    die "tleap 실행에 실패했습니다. 확인할 파일: $work_dir/leap.log"
fi

if ! "$python_bin" "convert_topology.py" \
    "$work_dir/system.parm7" \
    "$work_dir/system.rst7" \
    "$work_dir/topol.top" \
    "$work_dir/system.gro"; then
    die "ParmEd topology 변환에 실패했습니다."
fi

echo "Protein hot region과 REST2 topology를 생성합니다."

if ! "$gmx" grompp \
    -f "inputs/energy_check.mdp" \
    -p "$work_dir/topol.top" \
    -c "$work_dir/system.gro" \
    -pp "$work_dir/processed.top" \
    -o "$work_dir/preprocess.tpr" \
    > "$work_dir/grompp_preprocess.log" 2>&1; then
    die "processed topology 생성에 실패했습니다: $work_dir/grompp_preprocess.log"
fi

if ! "$python_bin" "scale_cmap.py" \
    "$work_dir/topol.top" \
    "$work_dir/processed.top" \
    1.0; then
    die "processed topology의 residue-specific CMAP 복원에 실패했습니다."
fi

if ! "$python_bin" "mark_hot.py" \
    "$work_dir/processed.top" \
    "$work_dir/processed.hot.top"; then
    die "protein hot-region marker 생성에 실패했습니다."
fi

while IFS=$'\t' read -r replica effective_temperature lambda_pp _ seed; do
    if [[ "$replica" == "replica" ]]; then
        continue
    fi

    replica_dir="$work_dir/$replica"
    mkdir -p "$replica_dir"

    if ! "$plumed" partial_tempering "$lambda_pp" \
        < "$work_dir/processed.hot.top" \
        > "$replica_dir/topol.top"; then
        die "REST2 topology 생성에 실패했습니다: replica $replica"
    fi

    if ! "$python_bin" "scale_cmap.py" \
        "$work_dir/processed.top" \
        "$replica_dir/topol.top" \
        "$lambda_pp"; then
        die "REST2 CMAP scaling에 실패했습니다: replica $replica"
    fi

    cp "$work_dir/system.gro" "$replica_dir/system.gro"
    cp "inputs/plumed.dat" "$replica_dir/plumed.dat"

    sed \
        -e "s/@SEED@/$seed/g" \
        "inputs/equilibrate.mdp" \
        > "$replica_dir/equilibrate.mdp"

    cp "inputs/minimize.mdp" "$replica_dir/minimize.mdp"
    cp "inputs/production.mdp" "$replica_dir/production.mdp"
done < "$states_file"

cp "$states_file" "$work_dir/states.tsv"

# scale=1은 원본과 같은 Hamiltonian이어야 하므로 한 frame의 energy를 비교합니다.
energy_dir="$work_dir/energy_check"
mkdir -p "$energy_dir"

for variant in unscaled scale_one; do
    if [[ "$variant" == "unscaled" ]]; then
        topology="$work_dir/topol.top"
    else
        topology="$work_dir/000/topol.top"
    fi

    if ! "$gmx" grompp \
        -f "inputs/energy_check.mdp" \
        -p "$topology" \
        -c "$work_dir/system.gro" \
        -o "$energy_dir/$variant.tpr" \
        > "$energy_dir/$variant.grompp.log" 2>&1; then
        die "energy check용 tpr 생성에 실패했습니다: $energy_dir/$variant.grompp.log"
    fi

    if ! "$gmx" mdrun \
        -s "$energy_dir/$variant.tpr" \
        -rerun "$work_dir/system.gro" \
        -deffnm "$energy_dir/$variant" \
        > "$energy_dir/$variant.mdrun.log" 2>&1; then
        die "energy rerun에 실패했습니다: $energy_dir/$variant.mdrun.log"
    fi

    if ! "$gmx" energy \
        -f "$energy_dir/$variant.edr" \
        -o "$energy_dir/$variant.xvg" \
        < "inputs/energy_selection.txt" \
        > "$energy_dir/$variant.energy.log" 2>&1; then
        die "Potential energy 추출에 실패했습니다: $energy_dir/$variant.energy.log"
    fi
done

"$python_bin" "compare_energy.py" \
    "$energy_dir/unscaled.xvg" \
    "$energy_dir/scale_one.xvg" \
    "$energy_tolerance"

echo "REST2 topology와 좌표: $work_dir"
