#!/usr/bin/env bash
set -euo pipefail

original_args=("$@")

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

if (( ! ${dry_run:-0} )) &&
        [[ ${original_args[0]:-} != -h && ${original_args[0]:-} != --help && ${original_args[0]:-} != --dry-run ]] &&
        [[ ${MD_WRITER_PARENT:-} != "$PPID" || ${MD_WRITER_ENTRY:-} != "$0" ]]; then
    exec "${PYTHON:-python3}" helpers/writer_guard.py \
        --registry "work" --read "$ligand_sdf" --write "work" -- "$0" "${original_args[@]}"
fi


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
echo "Parameterizing JZ4 with GAFF2/AM1-BCC (net charge: $ligand_charge); log: $work_dir/antechamber.log"
mkdir -p "$work_dir"
parameter_record="$work_dir/.ligand-parameters.identity.json"
"${PYTHON:-python3}" helpers/input_identity.py \
    --record "$parameter_record" --stage "ligand parameter preparation" \
    --input "$ligand_sdf" --value="$ligand_charge" \
    --output "$work_dir/sqm.out" --output "$ligand_mol2" --output "$ligand_frcmod"
parameter_state=$("${PYTHON:-python3}" helpers/input_identity.py --check-completion "$parameter_record")
if [[ "$parameter_state" == complete ]]; then
    echo "Using completed ligand parameters: $ligand_mol2, $ligand_frcmod"
    exit 0
fi
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

if [[ ! -s "$ligand_mol2" ]]; then
    die "ligand mol2 was not created: $ligand_mol2"
fi

echo "Completed: antechamber ($ligand_mol2)"
printf '\n'

# Generate an frcmod file for GAFF2 parameters missing from the Mol2 file.
echo "Generating missing GAFF2 parameters: $work_dir/parmchk2.log"
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

if [[ ! -s "$ligand_frcmod" ]]; then
    die "ligand frcmod was not created: $ligand_frcmod"
fi

"${PYTHON:-python3}" helpers/input_identity.py \
    --finish-completion "$parameter_record" \
    --required-output "$work_dir/sqm.out" \
    --required-output "$ligand_mol2" \
    --required-output "$ligand_frcmod"
echo "Ligand parameter: $work_dir"
