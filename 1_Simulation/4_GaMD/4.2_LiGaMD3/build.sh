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
metadata=$(dirname "$complex_pdb")/system_metadata.tsv
disulfides=$(dirname "$complex_pdb")/disulfides.leap
antechamber=${ANTECHAMBER:-antechamber}
parmchk2=${PARMCHK2:-parmchk2}
tleap=${TLEAP:-tleap}
python=${PYTHON:-python3}
ligand_charge=${LIGAND_CHARGE:-1}
script_dir=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
work_dir=${WORK_DIR:-"$script_dir/work"}

if [[ ! "$ligand_charge" =~ ^-?[0-9]+$ ]]; then
    die "LIGAND_CHARGE는 정수여야 합니다: $ligand_charge"
fi

if (( dry_run )); then
    printf 'mkdir -p %q\n' "$work_dir"
    parameter_sdf=$ligand_sdf
    if [[ "$ligand_charge" -eq 1 ]]; then
        parameter_sdf="$work_dir/ben-protonated.sdf"
        printf '%q %q %q %q\n' "$python" "$script_dir/protonate_benzamidine.py" "$ligand_sdf" "$parameter_sdf"
    fi
    printf '%q -i %q -fi sdf -o %q -fo mol2 -at gaff2 -c bcc -nc %q -rn BEN -s 2\n' "$antechamber" "$parameter_sdf" "$work_dir/ben.mol2" "$ligand_charge"
    printf '%q -i %q -f mol2 -o %q -s gaff2\n' "$parmchk2" "$work_dir/ben.mol2" "$work_dir/ben.frcmod"
    printf '%q -f %q\n' "$tleap" "$script_dir/inputs/tleap.in"
    printf '%q %q %q %q %q %q\n' \
        "$python" \
        "$script_dir/render_inputs.py" \
        "$work_dir/system.parm7" \
        "$metadata" \
        "$script_dir/inputs" \
        "$work_dir/inputs"
    exit 0
fi

for input in "$complex_pdb" "$ligand_sdf" "$metadata" "$disulfides"; do
    if [[ ! -s "$input" ]]; then
        die "build input을 찾을 수 없습니다: $input"
    fi
done
ligand_sdf=$(cd "$(dirname "$ligand_sdf")" && pwd -P)/$(basename "$ligand_sdf")
for executable in "$antechamber" "$parmchk2" "$tleap" "$python"; do
    if ! command -v "$executable" >/dev/null 2>&1; then
        die "실행 파일을 찾을 수 없습니다: $executable"
    fi
done

mkdir -p "$work_dir"
cp "$complex_pdb" "$work_dir/complex.pdb"
cp "$disulfides" "$work_dir/disulfides.leap"

echo "BEN을 GAFF2/AM1-BCC로 parameterize합니다."
parameter_sdf=$ligand_sdf
if [[ "$ligand_charge" -eq 1 ]]; then
    parameter_sdf="$work_dir/ben-protonated.sdf"
    "$python" \
        "$script_dir/protonate_benzamidine.py" \
        "$ligand_sdf" \
        "$parameter_sdf"
fi
if ! (
    cd "$work_dir"
    "$antechamber" \
        -i "$parameter_sdf" -fi sdf \
        -o ben.mol2 -fo mol2 \
        -at gaff2 -c bcc -nc "$ligand_charge" -rn BEN -s 2 \
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
    "$tleap" -f "$script_dir/inputs/tleap.in" > leap.log 2>&1
); then
    die "tleap 실행에 실패했습니다: $work_dir/leap.log"
fi
for output in system.parm7 system.rst7 system.pdb; do
    if [[ ! -s "$work_dir/$output" ]]; then
        die "build output이 생성되지 않았습니다: $work_dir/$output"
    fi
done

if ! "$python" \
    "$script_dir/render_inputs.py" \
    "$work_dir/system.parm7" \
    "$metadata" \
    "$script_dir/inputs" \
    "$work_dir/inputs"; then
    die "LiGaMD3 input 생성에 실패했습니다."
fi

echo "LiGaMD3 topology, restart와 generated input: $work_dir"
