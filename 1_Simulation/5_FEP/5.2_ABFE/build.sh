#!/usr/bin/env bash
set -euo pipefail

dry_run=0
if [[ "${1:-}" == "--dry-run" ]]; then
    dry_run=1
    shift
fi
if [[ $# -ne 2 ]]; then
    echo "Usage: $0 [--dry-run] COMPLEX.pdb JZ4_ideal.sdf" >&2
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
            \( -name '.*.complete' -o -name 'min*.out' -o -name 'heat*.out' \
               -o -name 'equil*.out' -o -name 'production*.out' \) \
            -print -quit)
    fi
    if [[ -n "$existing_result" ]]; then
        die "Existing simulation results were found: $existing_result. Use a new WORK_DIR or remove the previous calculation results before rebuilding."
    fi
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

refuse_existing_results "$work_dir"

if (( dry_run )); then
    echo "Build: 3HTB ff19SB/GAFF2/AM1-BCC/TIP3P ABFE"
    printf '%q -i %q -fi sdf -o %q -fo mol2 -at gaff2 -c bcc -nc 0 -rn JZ4\n' "$antechamber" "$ligand_sdf" "$build_dir/jz4.mol2"
    printf '%q %q %q %q %q\n' "$python" "generate_inputs.py" "$work_dir" "inputs" GLN102_RESIDUE
    exit 0
fi

for input_file in "$complex_pdb" "$ligand_sdf" "$structure_dir/preparation.tsv"; do
    if [[ ! -s "$input_file" ]]; then
        die "Required input not found: $input_file"
    fi
done
for executable in "$antechamber" "$parmchk2" "$tleap" "$python"; do
    if ! command -v "$executable" >/dev/null 2>&1; then
        die "Executable not found: $executable"
    fi
done
if ! "$python" -c 'import parmed' >/dev/null 2>&1; then
    die "ParmEd Python module is required."
fi

anchor_residue=$(awk -F '\t' '$1 == "protein_anchor_residue" {print $2}' "$structure_dir/preparation.tsv")
if [[ ! "$anchor_residue" =~ ^[1-9][0-9]*$ ]]; then
    die "Protein anchor residue index could not be read: $structure_dir/preparation.tsv"
fi

mkdir -p "$build_dir"
cp "$complex_pdb" "$build_dir/complex.pdb"

echo "Parameterizing JZ4 with GAFF2/AM1-BCC."
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

echo "Generating complex and solvent topologies."
for environment in complex solvent; do
    cp "inputs/tleap_${environment}.in" "$build_dir/tleap_${environment}.in"
    if ! (cd "$build_dir" && "$tleap" -f "tleap_${environment}.in" > "tleap_${environment}.log" 2>&1); then
        die "$environment topology build failed: $build_dir/tleap_${environment}.log"
    fi
    for suffix in parm7 rst7; do
        if [[ ! -s "$build_dir/$environment.$suffix" ]]; then
            die "$environment build Output not found: $build_dir/$environment.$suffix"
        fi
    done
done

"$python" \
    "generate_inputs.py" \
    "$work_dir" \
    "inputs" \
    "$anchor_residue"

echo "Created 65 ABFE windows: $work_dir/restraint, $work_dir/charge, $work_dir/vdw"
