#!/usr/bin/env bash
set -euo pipefail

dry_run=0
if [[ "${1:-}" == "--dry-run" ]]; then
    dry_run=1
    shift
fi

if [[ $# -ne 2 ]]; then
    echo "사용법: $0 [--dry-run] COMPLEX.pdb BEN_ideal.sdf" >&2
    exit 2
fi

die() {
    echo "오류: $*" >&2
    exit 1
}

complex_pdb=$1
ligand_sdf=$2
input_dir=$(dirname "$complex_pdb")
disulfides="$input_dir/disulfides.leap"
residue_map="$input_dir/funnel_residues.tsv"
work_dir=${WORK_DIR:-"work"}
python=${PYTHON:-python3}
antechamber=${ANTECHAMBER:-antechamber}
parmchk2=${PARMCHK2:-parmchk2}
tleap=${TLEAP:-tleap}

if (( dry_run )); then
    echo "BEN(+1) GAFF2/AM1-BCC parameterization"
    echo "ff19SB/GAFF2/TIP3P topology build"
    echo "3PTB funnel axis and atom-group calculation"
    exit 0
fi

for input in "$complex_pdb" "$ligand_sdf" "$disulfides" "$residue_map"; do
    if [[ ! -s "$input" ]]; then
        die "build input을 찾을 수 없습니다: $input"
    fi
done

for executable in "$python" "$antechamber" "$parmchk2" "$tleap"; do
    if ! command -v "$executable" >/dev/null 2>&1; then
        die "실행 파일을 찾을 수 없습니다: $executable"
    fi
done

mkdir -p "$work_dir"
cp "$complex_pdb" "$work_dir/complex.pdb"
cp "$disulfides" "$work_dir/disulfides.leap"
cp inputs/tleap.in "$work_dir/tleap.in"

echo "BEN을 benzamidinium(+1)으로 만들고 GAFF2/AM1-BCC를 적용합니다."
"$python" \
    "protonate_benzamidine.py" \
    "$ligand_sdf" \
    "$work_dir/ben-protonated.sdf"

if ! (
    cd "$work_dir"
    "$antechamber" \
        -i ben-protonated.sdf -fi sdf \
        -o ben.mol2 -fo mol2 \
        -at gaff2 -c bcc -nc 1 -rn BEN -s 2 \
        > antechamber.log 2>&1
); then
    die "antechamber 실행에 실패했습니다: $work_dir/antechamber.log"
fi

if ! (
    cd "$work_dir"
    "$parmchk2" \
        -i ben.mol2 -f mol2 \
        -o ben.frcmod -s gaff2 \
        > parmchk2.log 2>&1
); then
    die "parmchk2 실행에 실패했습니다: $work_dir/parmchk2.log"
fi

echo "ff19SB/GAFF2/TIP3P topology를 생성합니다."
if ! (
    cd "$work_dir"
    "$tleap" -f tleap.in > leap.log 2>&1
); then
    die "tleap 실행에 실패했습니다: $work_dir/leap.log"
fi

for output in system.parm7 system.rst7 system.pdb; do
    if [[ ! -s "$work_dir/$output" ]]; then
        die "build output이 없습니다: $work_dir/$output"
    fi
done

"$python" \
    "setup_funnel.py" \
    "$work_dir/system.parm7" \
    "$work_dir/system.rst7" \
    "$residue_map" \
    "inputs/plumed.dat.template" \
    "$work_dir"

echo "Funnel MetaD topology와 geometry: $work_dir"
