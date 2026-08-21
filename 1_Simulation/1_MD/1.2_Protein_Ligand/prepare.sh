#!/usr/bin/env bash
set -euo pipefail

die() {
    echo "Error: $*" >&2
    exit 1
}

if [[ $# -ne 1 ]]; then
    echo "Usage: $0 JZ4_ideal.sdf" >&2
    exit 2
fi

ligand_sdf=$1
ligand_charge=0
work_dir=work

ligand_mol2="$work_dir/jz4.mol2"
ligand_frcmod="$work_dir/jz4.frcmod"

if [[ ! -f "$ligand_sdf" ]]; then
    die "Ligand SDF not found: $ligand_sdf"
fi
if ! command -v antechamber >/dev/null 2>&1; then
    die "antechamber not found."
fi
if ! command -v parmchk2 >/dev/null 2>&1; then
    die "parmchk2 not found."
fi

# Assign GAFF2 atom types and AM1-BCC charges.
echo "Parameterizing JZ4 with GAFF2/AM1-BCC (net charge: $ligand_charge)."
mkdir -p "$work_dir"
cp "$ligand_sdf" "$work_dir/JZ4_ideal.sdf"

if ! (
    cd "$work_dir"
    antechamber \
        -i JZ4_ideal.sdf \
        -fi sdf \
        -o jz4.mol2 \
        -fo mol2 \
        -at gaff2 \
        -c bcc \
        -nc "$ligand_charge" \
        -rn JZ4 \
        -s 2 \
        > antechamber.log 2>&1
); then
    die "antechamber run failed. See log: $work_dir/antechamber.log"
fi

# Generate an frcmod file for GAFF2 parameters missing from the Mol2 file.
if ! (
    cd "$work_dir"
    parmchk2 \
        -i jz4.mol2 \
        -f mol2 \
        -o jz4.frcmod \
        -s gaff2 \
        > parmchk2.log 2>&1
); then
    die "parmchk2 run failed. See log: $work_dir/parmchk2.log"
fi

if [[ ! -s "$ligand_mol2" ]]; then
    die "ligand mol2 was not created: $ligand_mol2"
fi

if [[ ! -s "$ligand_frcmod" ]]; then
    die "ligand frcmod was not created: $ligand_frcmod"
fi

echo "Ligand parameter: $work_dir"
