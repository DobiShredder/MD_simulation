#!/usr/bin/env bash
set -euo pipefail

if [[ $# -ne 1 ]]; then
    echo "Usage: $0 PROTEIN.pdb" >&2
    exit 2
fi

die() {
    echo "Error: $*" >&2
    exit 1
}

refuse_existing_results() {
    local directory=$1
    local existing_result=""
    if [[ -d "$directory" ]]; then
        existing_result=$(find "$directory" -type f \
            \( -name 'min*.out' -o -name 'heat*.out' \
               -o -name 'equil*.out' -o -name 'production*.out' \) \
            -print -quit)
    fi
    if [[ -n "$existing_result" ]]; then
        die "Existing simulation results were found: $existing_result. Remove the previous calculation results before rebuilding."
    fi
}

protein_pdb=$1
structure_dir=$(dirname "$protein_pdb")
work_dir=work
build_dir="$work_dir/build"
antechamber=${ANTECHAMBER:-antechamber}
parmchk2=${PARMCHK2:-parmchk2}
tleap=${TLEAP:-tleap}

refuse_existing_results "$work_dir"

for input_file in "$protein_pdb" "$structure_dir/bound_bnz.pdb" "$structure_dir/bound_mbn.pdb"; do
    if [[ ! -s "$input_file" ]]; then
        die "prepare.py output not found: $input_file"
    fi
done
for executable in "$antechamber" "$parmchk2" "$tleap" python3; do
    if ! command -v "$executable" >/dev/null 2>&1; then
        die "Executable not found: $executable"
    fi
done

mkdir -p "$build_dir"
cp "$protein_pdb" "$build_dir/protein.pdb"
bound_bnz=$(cd "$structure_dir" && pwd -P)/bound_bnz.pdb
bound_mbn=$(cd "$structure_dir" && pwd -P)/bound_mbn.pdb

echo "Parameterizing benzene and toluene with GAFF2/AM1-BCC."
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

echo "Generating complex and solvent topologies."
for environment in complex solvent; do
    cp "inputs/tleap_${environment}.in" "$build_dir/tleap_${environment}.in"
    if ! (cd "$build_dir" && "$tleap" -f "tleap_${environment}.in" > "tleap_${environment}.log" 2>&1); then
        die "$environment topology build failed: $build_dir/tleap_${environment}.log"
    fi
    for suffix in parm7 rst7 pdb; do
        if [[ ! -s "$build_dir/$environment.$suffix" ]]; then
            die "$environment build Output not found: $build_dir/$environment.$suffix"
        fi
    done
done

python3 "generate_inputs.py" "$work_dir" "inputs"
echo "Created 22 RBFE windows: $work_dir/complex, $work_dir/solvent"
