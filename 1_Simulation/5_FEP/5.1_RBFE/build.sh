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
    if "$antechamber" \
        -i "$bound_bnz" -fi pdb \
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
        -i "$bound_mbn" -fi pdb \
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
done

echo "Generating FEP window inputs: $build_dir -> $work_dir/states.tsv"
python3 "generate_inputs.py" "$work_dir" "inputs"
if [[ ! -s "$work_dir/states.tsv" ]]; then
    die "FEP window generation did not create: $work_dir/states.tsv"
fi

echo "Created 22 RBFE windows: $work_dir/complex, $work_dir/solvent"
