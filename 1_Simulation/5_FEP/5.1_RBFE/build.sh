#!/usr/bin/env bash
set -euo pipefail

original_args=("$@")

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

if (( ! ${dry_run:-0} )) &&
        [[ ${original_args[0]:-} != -h && ${original_args[0]:-} != --help && ${original_args[0]:-} != --dry-run ]] &&
        [[ ${MD_WRITER_PARENT:-} != "$PPID" || ${MD_WRITER_ENTRY:-} != "$0" ]]; then
    exec "${PYTHON:-python3}" helpers/writer_guard.py \
        --registry "work" --read "$1" --read "$structure_dir" --read "inputs" --write "work" -- "$0" "${original_args[@]}"
fi


# A rebuild must not mix new inputs with topology/restart files from an older build.
if [[ -d "$work_dir" ]]; then
    existing_build=$(find "$work_dir" -type f \
        \( -name '*.parm7' -o -name '*.rst7' \) -print -quit)
    if [[ -n "$existing_build" ]]; then
        die "Build output already exists and was retained: $existing_build. Use a new work directory for a new build."
    fi
fi

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
for input_file in "$structure_dir/BNZ_ideal.sdf" "$structure_dir/MBN_ideal.sdf"; do
    if [[ ! -s "$input_file" ]]; then
        die "download.sh output not found: $input_file"
    fi
done
for executable in "$antechamber" "$parmchk2" "$tleap" python3; do
    if ! command -v "$executable" >/dev/null 2>&1; then
        die "Executable not found: $executable"
    fi
done
if ! python3 -c 'import parmed' >/dev/null 2>&1; then
    die "ParmEd Python module is required by generate_inputs.py."
fi
if [[ ! -s inputs/atom_mapping.tsv ]]; then
    die "Common-core atom mapping not found: inputs/atom_mapping.tsv"
fi

mkdir -p "$build_dir"
cp "$protein_pdb" "$build_dir/protein.pdb"
cp "$structure_dir/bound_bnz.pdb" "$structure_dir/bound_mbn.pdb" "$build_dir/"
cp "$structure_dir/BNZ_ideal.sdf" "$structure_dir/MBN_ideal.sdf" "$build_dir/"

# The 4W53 ligand has no hydrogens. GAFF2 types and AM1-BCC charges are
# assigned from the RCSB ideal SDF files, which include all hydrogens. tleap
# later places these templates on the crystal heavy atoms in bound_*.pdb.
echo "Parameterizing benzene and toluene with GAFF2/AM1-BCC."
(
    cd "$build_dir"
    if "$antechamber" \
        -i BNZ_ideal.sdf -fi sdf \
        -o bnz.mol2 -fo mol2 \
        -at gaff2 -c bcc -nc 0 -rn BNZ -s 2 \
        > antechamber-bnz.log 2>&1; then
        if [[ ! -s bnz.mol2 ]]; then
            die "antechamber output was not created: $build_dir/bnz.mol2; log: $build_dir/antechamber-bnz.log"
        fi
    else
        status=$?
        echo "Error: ligand antechamber failed: $build_dir/antechamber-bnz.log" >&2
        exit "$status"
    fi
    if "$parmchk2" \
        -i bnz.mol2 -f mol2 \
        -o bnz.frcmod -s gaff2 \
        > parmchk2-bnz.log 2>&1; then
        if [[ ! -s bnz.frcmod ]]; then
            die "parmchk2 output was not created: $build_dir/bnz.frcmod; log: $build_dir/parmchk2-bnz.log"
        fi
    else
        status=$?
        echo "Error: ligand parmchk2 failed: $build_dir/parmchk2-bnz.log" >&2
        exit "$status"
    fi

    if "$antechamber" \
        -i MBN_ideal.sdf -fi sdf \
        -o mbn.mol2 -fo mol2 \
        -at gaff2 -c bcc -nc 0 -rn MBN -s 2 \
        > antechamber-mbn.log 2>&1; then
        if [[ ! -s mbn.mol2 ]]; then
            die "antechamber output was not created: $build_dir/mbn.mol2; log: $build_dir/antechamber-mbn.log"
        fi
    else
        status=$?
        echo "Error: ligand antechamber failed: $build_dir/antechamber-mbn.log" >&2
        exit "$status"
    fi
    if "$parmchk2" \
        -i mbn.mol2 -f mol2 \
        -o mbn.frcmod -s gaff2 \
        > parmchk2-mbn.log 2>&1; then
        if [[ ! -s mbn.frcmod ]]; then
            die "parmchk2 output was not created: $build_dir/mbn.frcmod; log: $build_dir/parmchk2-mbn.log"
        fi
    else
        status=$?
        echo "Error: ligand parmchk2 failed: $build_dir/parmchk2-mbn.log" >&2
        exit "$status"
    fi
)

echo "Completed: ligand parameterization ($build_dir)"
printf '\n'

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

    # Benzene is C6H6 and toluene is C7H8 after tleap adds the hydrogens.
    bnz_atom_count=$(awk '/^(ATOM|HETATM)/ && substr($0, 18, 3) == "BNZ" {count++} END {print count + 0}' "$build_dir/$environment.pdb")
    mbn_atom_count=$(awk '/^(ATOM|HETATM)/ && substr($0, 18, 3) == "MBN" {count++} END {print count + 0}' "$build_dir/$environment.pdb")
    if (( bnz_atom_count != 12 || mbn_atom_count != 15 )); then
        die "$environment ligand atom counts are BNZ=$bnz_atom_count, MBN=$mbn_atom_count (expected 12 and 15): $build_dir/tleap_${environment}.log"
    fi
done

# generate_inputs.py reads inputs/atom_mapping.tsv, checks the common-core order,
# copies the MBN core coordinates onto BNZ and writes build/*_core.rst7.
echo "Generating FEP window inputs: $build_dir -> $work_dir/states.tsv"
python3 "generate_inputs.py" "$work_dir" "inputs"
if [[ ! -s "$work_dir/states.tsv" ]]; then
    die "FEP window generation did not create: $work_dir/states.tsv"
fi

echo "Created 22 RBFE windows: $work_dir/complex, $work_dir/solvent"
