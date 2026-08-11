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

complex_pdb=$1
ligand_sdf=$2
metadata=$(dirname "$complex_pdb")/system_metadata.tsv
disulfides=$(dirname "$complex_pdb")/disulfides.leap
antechamber=${ANTECHAMBER:-antechamber}
parmchk2=${PARMCHK2:-parmchk2}
tleap=${TLEAP:-tleap}
python=${PYTHON:-python3}
ligand_charge=${LIGAND_CHARGE:-1}
work_dir=${WORK_DIR:-"work"}

if [[ ! "$ligand_charge" =~ ^-?[0-9]+$ ]]; then
    die "LIGAND_CHARGE must be an integer: $ligand_charge"
fi

if (( dry_run )); then
    printf 'mkdir -p %q\n' "$work_dir"
    parameter_sdf=$ligand_sdf
    if [[ "$ligand_charge" -eq 1 ]]; then
        parameter_sdf="$work_dir/ben-protonated.sdf"
        printf '%q %q %q %q\n' "$python" "protonate_benzamidine.py" "$ligand_sdf" "$parameter_sdf"
    fi
    printf '%q -i %q -fi sdf -o %q -fo mol2 -at gaff2 -c bcc -nc %q -rn BEN -s 2\n' "$antechamber" "$parameter_sdf" "$work_dir/ben.mol2" "$ligand_charge"
    printf '%q -i %q -f mol2 -o %q -s gaff2\n' "$parmchk2" "$work_dir/ben.mol2" "$work_dir/ben.frcmod"
    printf '%q -f %q\n' "$tleap" "inputs/tleap.in"
    printf '%q %q %q %q %q %q\n' \
        "$python" \
        "render_inputs.py" \
        "$work_dir/system.parm7" \
        "$metadata" \
        "inputs" \
        "$work_dir/inputs"
    exit 0
fi

for input in "$complex_pdb" "$ligand_sdf" "$metadata" "$disulfides"; do
    if [[ ! -s "$input" ]]; then
        die "Build input not found: $input"
    fi
done
ligand_sdf=$(cd "$(dirname "$ligand_sdf")" && pwd -P)/$(basename "$ligand_sdf")
for executable in "$antechamber" "$parmchk2" "$tleap" "$python"; do
    if ! command -v "$executable" >/dev/null 2>&1; then
        die "Executable not found: $executable"
    fi
done

mkdir -p "$work_dir"
cp "$complex_pdb" "$work_dir/complex.pdb"
cp "$disulfides" "$work_dir/disulfides.leap"
cp inputs/tleap.in "$work_dir/tleap.in"

echo "Parameterizing BEN with GAFF2/AM1-BCC."
parameter_sdf=$ligand_sdf
if [[ "$ligand_charge" -eq 1 ]]; then
    protonated_sdf="$work_dir/ben-protonated.sdf"
    "$python" \
        "protonate_benzamidine.py" \
        "$ligand_sdf" \
        "$protonated_sdf"
    parameter_sdf=ben-protonated.sdf
fi
if ! (
    cd "$work_dir"
    "$antechamber" \
        -i "$parameter_sdf" -fi sdf \
        -o ben.mol2 -fo mol2 \
        -at gaff2 -c bcc -nc "$ligand_charge" -rn BEN -s 2 \
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
        die "build Output was not created: $work_dir/$output"
    fi
done

if ! "$python" \
    "render_inputs.py" \
    "$work_dir/system.parm7" \
    "$metadata" \
    "inputs" \
    "$work_dir/inputs"; then
    die "LiGaMD3 input generation failed."
fi

echo "LiGaMD3 topology, restart, and generated inputs: $work_dir"
