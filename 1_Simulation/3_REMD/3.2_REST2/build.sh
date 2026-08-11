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
gmx=${GROMACS:-gmx}
plumed=${PLUMED:-plumed}
python_bin=${PYTHON:-python3}
energy_tolerance=${ENERGY_TOLERANCE_KJ_MOL:-0.0001}

for input_file in "$input_pdb" "$states_file"; do
    if [[ ! -s "$input_file" ]]; then
        die "필요한 input을 찾을 수 없습니다: $input_file"
    fi
done

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
if [[ "$replica_count" -ne 8 ]]; then
    die "states.tsv에는 8개 replica가 있어야 합니다: $replica_count"
fi

if (( dry_run )); then
    echo "ff19SB/TIP3P AMBER system을 GROMACS topology로 변환합니다."
    echo "Protein atom만 표시하고 8개 REST2 topology를 생성합니다."
    echo "Scale 1.0 topology와 원본 topology의 potential energy를 비교합니다."
    echo "생성 위치: $work_dir/000 ... 007"
    exit 0
fi

echo "ff19SB/TIP3P AMBER system을 생성합니다."
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

if ! "$python_bin" "$script_dir/convert_topology.py" \
    "$work_dir/system.parm7" \
    "$work_dir/system.rst7" \
    "$work_dir/topol.top" \
    "$work_dir/system.gro"; then
    die "ParmEd topology 변환에 실패했습니다."
fi

echo "Protein hot region과 REST2 topology를 생성합니다."

if ! "$gmx" grompp \
    -f "$script_dir/inputs/energy_check.mdp" \
    -p "$work_dir/topol.top" \
    -c "$work_dir/system.gro" \
    -pp "$work_dir/processed.top" \
    -o "$work_dir/preprocess.tpr" \
    > "$work_dir/grompp_preprocess.log" 2>&1; then
    die "processed topology 생성에 실패했습니다: $work_dir/grompp_preprocess.log"
fi

if ! "$python_bin" "$script_dir/scale_cmap.py" \
    "$work_dir/topol.top" \
    "$work_dir/processed.top" \
    1.0; then
    die "processed topology의 CMAP residue selector 복원에 실패했습니다."
fi

if ! "$python_bin" "$script_dir/mark_hot.py" \
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

    if ! "$python_bin" "$script_dir/scale_cmap.py" \
        "$work_dir/processed.top" \
        "$replica_dir/topol.top" \
        "$lambda_pp"; then
        die "REST2 CMAP scaling에 실패했습니다: replica $replica"
    fi

    cp "$work_dir/system.gro" "$replica_dir/system.gro"
    cp "$script_dir/inputs/plumed.dat" "$replica_dir/plumed.dat"

    sed \
        -e "s/@SEED@/$seed/g" \
        "$script_dir/inputs/equilibrate.mdp" \
        > "$replica_dir/equilibrate.mdp"

    cp "$script_dir/inputs/minimize.mdp" "$replica_dir/minimize.mdp"
    cp "$script_dir/inputs/production.mdp" "$replica_dir/production.mdp"
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
        -f "$script_dir/inputs/energy_check.mdp" \
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
        < "$script_dir/inputs/energy_selection.txt" \
        > "$energy_dir/$variant.energy.log" 2>&1; then
        die "Potential energy 추출에 실패했습니다: $energy_dir/$variant.energy.log"
    fi
done

"$python_bin" "$script_dir/compare_energy.py" \
    "$energy_dir/unscaled.xvg" \
    "$energy_dir/scale_one.xvg" \
    "$energy_tolerance"

echo "REST2 topology와 좌표: $work_dir"
