#!/usr/bin/env bash
set -euo pipefail

dry_run=0
if [[ "${1:-}" == "--dry-run" ]]; then
    dry_run=1
    shift
fi

if [[ $# -ne 2 ]]; then
    echo "Usage: $0 [--dry-run] COMPLEX.pdb BEN_ideal.sdf" >&2
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
            \( -name '.*.complete' -o -name 'minimize*.out' -o -name 'heat.out' \
               -o -name 'equilibrate.out' -o -name 'md.out' \) -print -quit)
    fi
    if [[ -n "$existing_result" ]]; then
        die "Existing simulation results were found: $existing_result. Use a new WORK_DIR or remove the previous calculation results before rebuilding."
    fi
}

complex_pdb=$1
ligand_sdf=$2
input_dir=$(dirname "$complex_pdb")
disulfides="$input_dir/disulfides.leap"
residue_map="$input_dir/funnel_residues.tsv"
work_dir=${WORK_DIR:-"work"}
python=${PYTHON:-python3}

refuse_existing_results "$work_dir"
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
        die "Build input not found: $input"
    fi
done

for executable in "$python" "$antechamber" "$parmchk2" "$tleap"; do
    if ! command -v "$executable" >/dev/null 2>&1; then
        die "Executable not found: $executable"
    fi
done

mkdir -p "$work_dir"
cp "$complex_pdb" "$work_dir/complex.pdb"
cp "$disulfides" "$work_dir/disulfides.leap"
cp inputs/tleap.in "$work_dir/tleap.in"

echo "Converting BEN to benzamidinium (+1) and applying GAFF2/AM1-BCC."
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
    die "antechamber failed: $work_dir/antechamber.log"
fi

if ! (
    cd "$work_dir"
    "$parmchk2" \
        -i ben.mol2 -f mol2 \
        -o ben.frcmod -s gaff2 \
        > parmchk2.log 2>&1
); then
    die "parmchk2 failed: $work_dir/parmchk2.log"
fi

echo "Generating an ff19SB/GAFF2/TIP3P topology."
if ! (
    cd "$work_dir"
    "$tleap" -f tleap.in > leap.log 2>&1
); then
    die "tleap failed: $work_dir/leap.log"
fi

for output in system.parm7 system.rst7 system.pdb; do
    if [[ ! -s "$work_dir/$output" ]]; then
        die "build Output not found: $work_dir/$output"
    fi
done

"$python" \
    "setup_funnel.py" \
    "$work_dir/system.parm7" \
    "$work_dir/system.rst7" \
    "$residue_map" \
    "inputs/plumed.dat.template" \
    "$work_dir"

echo "Funnel MetaD topology and geometry: $work_dir"
