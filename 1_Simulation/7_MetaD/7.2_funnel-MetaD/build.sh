#!/usr/bin/env bash
set -euo pipefail

original_args=("$@")

if [[ $# -ne 2 ]]; then
    echo "Usage: $0 COMPLEX.pdb BEN_ideal.sdf" >&2
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
            \( -name 'minimize*.out' -o -name 'heat.out' \
               -o -name 'equilibrate.out' -o -name 'production.out' \) -print -quit)
    fi
    if [[ -n "$existing_result" ]]; then
        die "Existing simulation results were found: $existing_result. Remove the previous calculation results before rebuilding."
    fi
}

complex_pdb=$1
ligand_sdf=$2
input_dir=$(dirname "$complex_pdb")
disulfides="$input_dir/disulfides.leap"
residue_map="$input_dir/funnel_residues.tsv"
work_dir=work

if (( ! ${dry_run:-0} )) &&
        [[ ${original_args[0]:-} != -h && ${original_args[0]:-} != --help && ${original_args[0]:-} != --dry-run ]] &&
        [[ ${MD_WRITER_PARENT:-} != "$PPID" || ${MD_WRITER_ENTRY:-} != "$0" ]]; then
    exec "${PYTHON:-python3}" helpers/writer_guard.py \
        --registry "work" --read "$1" --read "$input_dir" --read "$disulfides" --read "$ligand_sdf" --read "inputs" --write "work" -- "$0" "${original_args[@]}"
fi


# A rebuild must not mix new inputs with topology/restart files from an older build.
if [[ -d "$work_dir" ]]; then
    existing_build=$(find "$work_dir" -type f \
        \( -name '*.parm7' -o -name '*.rst7' \) -print -quit)
    if [[ -n "$existing_build" ]]; then
        die "Build output already exists and was retained: $existing_build. Use a new work directory for a new build."
    fi
fi

python=${PYTHON:-python3}

refuse_existing_results "$work_dir"
antechamber=${ANTECHAMBER:-antechamber}
parmchk2=${PARMCHK2:-parmchk2}
tleap=${TLEAP:-tleap}

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

if [[ ! -s "$work_dir/ben.mol2" ]]; then
    die "Ligand parameterization did not create: $work_dir/ben.mol2; log: $work_dir/antechamber.log"
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

if [[ ! -s "$work_dir/ben.frcmod" ]]; then
    die "Ligand parameterization did not create: $work_dir/ben.frcmod; log: $work_dir/parmchk2.log"
fi
echo "Completed: ligand parameterization ($work_dir/ben.mol2, $work_dir/ben.frcmod)"
printf '\n'

echo "Generating an ff19SB/GAFF2/OPC topology."
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

echo "Preparing funnel geometry: $residue_map; topology: $work_dir/system.parm7"
"$python" \
    "setup_funnel.py" \
    "$work_dir/system.parm7" \
    "$work_dir/system.rst7" \
    "$residue_map" \
    "inputs/plumed.dat.template" \
    "$work_dir"

for output in funnel-reference.pdb plumed.dat atom_count.txt funnel_geometry.tsv; do
    if [[ ! -s "$work_dir/$output" ]]; then
        die "Funnel setup did not create: $work_dir/$output"
    fi
done

echo "Funnel MetaD topology and geometry: $work_dir"
