#!/usr/bin/env bash
set -euo pipefail

dry_run=0
if [[ "${1:-}" == "--dry-run" ]]; then
    dry_run=1
    shift
fi
if [[ $# -ne 1 ]]; then
    echo "사용법: $0 [--dry-run] PROTEIN.pdb" >&2
    exit 2
fi

die() {
    echo "오류: $*" >&2
    exit 1
}

protein_pdb=$1
structure_dir=$(dirname "$protein_pdb")
script_dir=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
work_dir=${WORK_DIR:-"$script_dir/work"}
build_dir="$work_dir/build"
antechamber=${ANTECHAMBER:-antechamber}
parmchk2=${PARMCHK2:-parmchk2}
tleap=${TLEAP:-tleap}

if (( dry_run )); then
    echo "Build: ff19SB/GAFF2/AM1-BCC/TIP3P, complex와 solvent leg"
    printf '%q -i %q -fi pdb -o %q -fo mol2 -at gaff2 -c bcc -nc 0 -rn BNZ\n' "$antechamber" "$structure_dir/bound_bnz.pdb" "$build_dir/bnz.mol2"
    printf '%q -i %q -fi pdb -o %q -fo mol2 -at gaff2 -c bcc -nc 0 -rn MBN\n' "$antechamber" "$structure_dir/bound_mbn.pdb" "$build_dir/mbn.mol2"
    printf '%q %q %q %q\n' python3 "$script_dir/generate_inputs.py" "$work_dir" "$script_dir/inputs"
    exit 0
fi

for input_file in "$protein_pdb" "$structure_dir/bound_bnz.pdb" "$structure_dir/bound_mbn.pdb"; do
    if [[ ! -s "$input_file" ]]; then
        die "prepare.py output을 찾을 수 없습니다: $input_file"
    fi
done
for executable in "$antechamber" "$parmchk2" "$tleap" python3; do
    if ! command -v "$executable" >/dev/null 2>&1; then
        die "실행 파일을 찾을 수 없습니다: $executable"
    fi
done

mkdir -p "$build_dir"
cp "$protein_pdb" "$build_dir/protein.pdb"
bound_bnz=$(cd "$structure_dir" && pwd -P)/bound_bnz.pdb
bound_mbn=$(cd "$structure_dir" && pwd -P)/bound_mbn.pdb

echo "Benzene과 toluene을 GAFF2/AM1-BCC로 parameterize합니다."
(
    cd "$build_dir"
    "$antechamber" \
        -i "$bound_bnz" -fi pdb \
        -o bnz.mol2 -fo mol2 \
        -at gaff2 -c bcc -nc 0 -rn BNZ -s 2 \
        > antechamber-bnz.log 2>&1
    "$parmchk2" \
        -i bnz.mol2 -f mol2 \
        -o bnz.frcmod -s gaff2 \
        > parmchk2-bnz.log 2>&1

    "$antechamber" \
        -i "$bound_mbn" -fi pdb \
        -o mbn.mol2 -fo mol2 \
        -at gaff2 -c bcc -nc 0 -rn MBN -s 2 \
        > antechamber-mbn.log 2>&1
    "$parmchk2" \
        -i mbn.mol2 -f mol2 \
        -o mbn.frcmod -s gaff2 \
        > parmchk2-mbn.log 2>&1
)

echo "Complex와 solvent topology를 생성합니다."
for leg in complex solvent; do
    cp "$script_dir/inputs/tleap_${leg}.in" "$build_dir/tleap_${leg}.in"
    if ! (cd "$build_dir" && "$tleap" -f "tleap_${leg}.in" > "tleap_${leg}.log" 2>&1); then
        die "$leg topology build에 실패했습니다: $build_dir/tleap_${leg}.log"
    fi
    for suffix in parm7 rst7 pdb; do
        if [[ ! -s "$build_dir/$leg.$suffix" ]]; then
            die "$leg build output이 없습니다: $build_dir/$leg.$suffix"
        fi
    done
done

python3 "$script_dir/generate_inputs.py" "$work_dir" "$script_dir/inputs"
echo "RBFE window 22개를 생성했습니다: $work_dir/legs"
