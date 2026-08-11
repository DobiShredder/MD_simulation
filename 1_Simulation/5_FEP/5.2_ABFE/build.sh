#!/usr/bin/env bash
set -euo pipefail

dry_run=0
if [[ "${1:-}" == "--dry-run" ]]; then
    dry_run=1
    shift
fi
if [[ $# -ne 2 ]]; then
    echo "사용법: $0 [--dry-run] COMPLEX.pdb JZ4_ideal.sdf" >&2
    exit 2
fi

die() {
    echo "오류: $*" >&2
    exit 1
}

complex_pdb=$1
ligand_sdf=$2
structure_dir=$(dirname "$complex_pdb")
work_dir=${WORK_DIR:-"work"}
build_dir="$work_dir/build"
antechamber=${ANTECHAMBER:-antechamber}
parmchk2=${PARMCHK2:-parmchk2}
tleap=${TLEAP:-tleap}
python=${PYTHON:-python3}

if (( dry_run )); then
    echo "Build: 3HTB ff19SB/GAFF2/AM1-BCC/TIP3P ABFE"
    printf '%q -i %q -fi sdf -o %q -fo mol2 -at gaff2 -c bcc -nc 0 -rn JZ4\n' "$antechamber" "$ligand_sdf" "$build_dir/jz4.mol2"
    printf '%q %q %q %q %q\n' "$python" "generate_inputs.py" "$work_dir" "inputs" GLN102_RESIDUE
    exit 0
fi

for input_file in "$complex_pdb" "$ligand_sdf" "$structure_dir/preparation.tsv"; do
    if [[ ! -s "$input_file" ]]; then
        die "필수 input을 찾을 수 없습니다: $input_file"
    fi
done
for executable in "$antechamber" "$parmchk2" "$tleap" "$python"; do
    if ! command -v "$executable" >/dev/null 2>&1; then
        die "실행 파일을 찾을 수 없습니다: $executable"
    fi
done
if ! "$python" -c 'import parmed' >/dev/null 2>&1; then
    die "ParmEd Python module이 필요합니다."
fi

anchor_residue=$(awk -F '\t' '$1 == "protein_anchor_residue" {print $2}' "$structure_dir/preparation.tsv")
if [[ ! "$anchor_residue" =~ ^[1-9][0-9]*$ ]]; then
    die "Protein anchor residue 번호를 읽지 못했습니다: $structure_dir/preparation.tsv"
fi

mkdir -p "$build_dir"
cp "$complex_pdb" "$build_dir/complex.pdb"

echo "JZ4를 GAFF2/AM1-BCC로 parameterize합니다."
cp "$ligand_sdf" "$build_dir/JZ4_ideal.sdf"
(
    cd "$build_dir"
    "$antechamber" \
        -i JZ4_ideal.sdf -fi sdf \
        -o jz4.mol2 -fo mol2 \
        -at gaff2 -c bcc -nc 0 -rn JZ4 -s 2 \
        > antechamber.log 2>&1
)
(
    cd "$build_dir"
    "$parmchk2" \
        -i jz4.mol2 -f mol2 \
        -o jz4.frcmod -s gaff2 \
        > parmchk2.log 2>&1
)

echo "Complex와 solvent topology를 생성합니다."
for leg in complex solvent; do
    cp "inputs/tleap_${leg}.in" "$build_dir/tleap_${leg}.in"
    if ! (cd "$build_dir" && "$tleap" -f "tleap_${leg}.in" > "tleap_${leg}.log" 2>&1); then
        die "$leg topology build에 실패했습니다: $build_dir/tleap_${leg}.log"
    fi
    for suffix in parm7 rst7; do
        if [[ ! -s "$build_dir/$leg.$suffix" ]]; then
            die "$leg build output이 없습니다: $build_dir/$leg.$suffix"
        fi
    done
done

"$python" \
    "generate_inputs.py" \
    "$work_dir" \
    "inputs" \
    "$anchor_residue"

echo "ABFE window 65개를 생성했습니다: $work_dir/windows"
