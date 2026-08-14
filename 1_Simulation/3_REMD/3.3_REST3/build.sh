#!/usr/bin/env bash
set -euo pipefail

dry_run=0
positional_arguments=()

while [[ $# -gt 0 ]]; do
    case "$1" in
        --dry-run)
            dry_run=1
            ;;
        -*)
            echo "Usage: $0 [--dry-run] INPUT.pdb [states.tsv]" >&2
            exit 2
            ;;
        *)
            positional_arguments+=("$1")
            ;;
    esac
    shift
done

if (( ${#positional_arguments[@]} < 1 || ${#positional_arguments[@]} > 2 )); then
    echo "Usage: $0 [--dry-run] INPUT.pdb [states.tsv]" >&2
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
            \( -name '.*.complete' -o -name 'min*.out' -o -name 'minimize.gro' \
               -o -name 'heat*.out' -o -name 'equil*.out' -o -name 'equilibrate.gro' \
               -o -name 'equilibrate.cpt' -o -name 'gamd_prepare.out' \
               -o -name 'production*.out' -o -name 'production*.gro' \
               -o -name 'production*.cpt' \) -print -quit)
    fi
    if [[ -n "$existing_result" ]]; then
        die "Existing simulation results were found: $existing_result. Use a new WORK_DIR or remove the previous calculation results before rebuilding."
    fi
}

input_pdb=${positional_arguments[0]}
states_file=${positional_arguments[1]:-"inputs/states.tsv"}
work_dir=${WORK_DIR:-"work"}
tleap=${TLEAP:-tleap}
gmx=${GROMACS:-gmx}
python_bin=${PYTHON:-python3}

refuse_existing_results "$work_dir"

for input_file in "$input_pdb" "$states_file"; do
    if [[ ! -s "$input_file" ]]; then
        die "Required input not found: $input_file"
    fi
done

if ! "$python_bin" validate_states.py "$states_file"; then
    die "REST3 state-table validation failed."
fi

if (( ! dry_run )); then
    for executable in "$tleap" "$gmx" "$python_bin"; do
        if ! command -v "$executable" >/dev/null 2>&1; then
            die "Executable not found: $executable"
        fi
    done

    if ! "$python_bin" -c "import parmed" >/dev/null 2>&1; then
        die "ParmEd is required: $python_bin -m pip install -r requirements.txt"
    fi
fi

replica_count=$(awk 'NR > 1 {count++} END {print count + 0}' "$states_file")
last_replica=$(awk 'END {print $1}' "$states_file")

if (( dry_run )); then
    echo "Converting the ff19SB/TIP3P AMBER system to GROMACS topology."
    echo "Generating $replica_count REST3 topologies from the specified temperature/kappa table."
    echo "Checking base identity and water-water/ion-water interactions."
    echo "State table: $states_file"
    echo "Output directories: $work_dir/000 ... $last_replica"
    exit 0
fi

echo "Generating an ff19SB/TIP3P AMBER system."
mkdir -p "$work_dir"
cp "$input_pdb" "$work_dir/input.pdb"
cp inputs/tleap.in "$work_dir/tleap.in"

if ! (
    cd "$work_dir"
    "$tleap" \
        -f tleap.in \
        > leap.log 2>&1
); then
    die "tleap failed. See log: $work_dir/leap.log"
fi

if ! "$python_bin" "convert_topology.py" \
    "$work_dir/system.parm7" \
    "$work_dir/system.rst7" \
    "$work_dir/topol.top" \
    "$work_dir/system.gro"; then
    die "ParmEd topology conversion failed."
fi

if ! "$gmx" grompp \
    -f "inputs/energy_check.mdp" \
    -p "$work_dir/topol.top" \
    -c "$work_dir/system.gro" \
    -pp "$work_dir/processed.top" \
    -o "$work_dir/preprocess.tpr" \
    > "$work_dir/grompp_preprocess.log" 2>&1; then
    die "processed topology generation failed: $work_dir/grompp_preprocess.log"
fi

if ! "$python_bin" "scale_cmap.py" \
    "$work_dir/topol.top" \
    "$work_dir/processed.top" \
    1.0; then
    die "Failed to restore residue-specific CMAPs in the processed topology."
fi

echo "Generating REST3 topologies with the published κ schedule."

if ! "$python_bin" "generate_rest3.py" \
    "$work_dir/processed.top" \
    "$states_file" \
    "$work_dir"; then
    die "REST3 topology generation failed."
fi

while IFS=$'\t' read -r replica _ _ _ _ seed; do
    if [[ "$replica" == "replica" ]]; then
        continue
    fi

    replica_dir="$work_dir/$replica"
    cp "$work_dir/system.gro" "$replica_dir/system.gro"
    cp "inputs/plumed.dat" "$replica_dir/plumed.dat"

    sed \
        -e "s/@SEED@/$seed/g" \
        "inputs/equilibrate.mdp" \
        > "$replica_dir/equilibrate.mdp"

    cp "inputs/minimize.mdp" "$replica_dir/minimize.mdp"
    cp "inputs/production.mdp" "$replica_dir/production.mdp"
done < "$states_file"

cp "$states_file" "$work_dir/states.tsv"

if ! "$python_bin" "verify_rest3.py" \
    "$work_dir/processed.top" \
    "$work_dir/states.tsv" \
    "$work_dir"; then
    die "REST3 topology-preservation check failed."
fi

echo "REST3 topologies and coordinates: $work_dir"
