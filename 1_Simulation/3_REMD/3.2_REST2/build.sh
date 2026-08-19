#!/usr/bin/env bash
set -euo pipefail

dry_run=0
positional_arguments=()

show_help() {
    cat <<'EOF'
Usage: ./build.sh [--dry-run] INPUT.pdb [temperatures.txt]

Build REST2 replica topologies from an effective-temperature list.

Temperature input:
  Separate values with commas, semicolons, vertical bars, or whitespace.
  Text after # is ignored. The first value must be 300 K, and subsequent
  values must increase strictly.

Generated scaling:
  lambda_pp = 300 / T
  lambda_pw = sqrt(lambda_pp)
  The complete table is written to work/states.tsv by default.

Options:
  --dry-run    Validate inputs and print the planned build without running it.
  -h, --help   Show this help message and exit.
EOF
}

while [[ $# -gt 0 ]]; do
    case "$1" in
        --dry-run)
            dry_run=1
            ;;
        -h|--help)
            show_help
            exit 0
            ;;
        -*)
            show_help >&2
            exit 2
            ;;
        *)
            positional_arguments+=("$1")
            ;;
    esac
    shift
done

if (( ${#positional_arguments[@]} < 1 || ${#positional_arguments[@]} > 2 )); then
    show_help >&2
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
temperature_file=${positional_arguments[1]:-"inputs/temperatures.txt"}
work_dir=${WORK_DIR:-"work"}
states_file="$work_dir/states.tsv"
tleap=${TLEAP:-tleap}
gmx=${GROMACS:-gmx}
plumed=${PLUMED:-plumed}
python_bin=${PYTHON:-python3}
energy_tolerance=${ENERGY_TOLERANCE_KJ_MOL:-0.1}

refuse_existing_results "$work_dir"

for input_file in "$input_pdb" "$temperature_file"; do
    if [[ ! -s "$input_file" ]]; then
        die "Required input not found: $input_file"
    fi
done

if ! replica_count=$("$python_bin" generate_states.py --count "$temperature_file"); then
    die "REST2 temperature-list validation failed."
fi
last_replica=$(printf '%03d' "$((replica_count - 1))")

if (( ! dry_run )); then
    for executable in "$tleap" "$gmx" "$plumed" "$python_bin"; do
        if ! command -v "$executable" >/dev/null 2>&1; then
            die "Executable not found: $executable"
        fi
    done

    if ! "$python_bin" -c "import parmed" >/dev/null 2>&1; then
        die "ParmEd is required: $python_bin -m pip install -r requirements.txt"
    fi
fi

if (( dry_run )); then
    echo "Converting the ff19SB/TIP3P AMBER system to GROMACS topology."
    echo "Marking only protein atoms and generating $replica_count REST2 topologies."
    echo "Comparing potential energies of the scale-1.0 and original topologies."
    echo "Temperature input: $temperature_file"
    echo "Generated state table: $states_file"
    echo "Output directories: $work_dir/000 ... $last_replica"
    exit 0
fi

echo "Generating an ff19SB/TIP3P AMBER system."
mkdir -p "$work_dir"
cp "$input_pdb" "$work_dir/input.pdb"
cp inputs/tleap.in "$work_dir/tleap.in"

if ! "$python_bin" generate_states.py "$temperature_file" "$states_file"; then
    die "REST2 state-table generation failed."
fi
if ! "$python_bin" validate_states.py "$states_file"; then
    die "Generated REST2 state-table validation failed."
fi

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

echo "Generating the protein hot region and REST2 topology."

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

if ! "$python_bin" "mark_hot.py" \
    "$work_dir/processed.top" \
    "$work_dir/processed.hot.top"; then
    die "protein hot-region marker generation failed."
fi

while IFS=$'\t' read -r replica effective_temperature lambda_pp _ seed; do
    if [[ "$replica" == "replica" ]]; then
        continue
    fi

    replica_dir="$work_dir/$replica"
    mkdir -p "$replica_dir"

    if ! "$plumed" partial_tempering "$lambda_pp" \
        < "$work_dir/processed.hot.top" \
        > "$replica_dir/topol.top"; then
        die "REST2 topology generation failed: replica $replica"
    fi

    if ! "$python_bin" "scale_cmap.py" \
        "$work_dir/processed.top" \
        "$replica_dir/topol.top" \
        "$lambda_pp"; then
        die "REST2 CMAP scaling failed: replica $replica"
    fi

    cp "$work_dir/system.gro" "$replica_dir/system.gro"
    cp "inputs/plumed.dat" "$replica_dir/plumed.dat"

    sed \
        -e "s/@SEED@/$seed/g" \
        "inputs/equilibrate.mdp" \
        > "$replica_dir/equilibrate.mdp"

    cp "inputs/minimize.mdp" "$replica_dir/minimize.mdp"
    cp "inputs/production.mdp" "$replica_dir/production.mdp"
done < "$states_file"

# At scale=1 the Hamiltonian must match the original, so compare the energy of one frame.
energy_dir="$work_dir/energy_check"
mkdir -p "$energy_dir"

for variant in unscaled scale_one; do
    if [[ "$variant" == "unscaled" ]]; then
        topology="$work_dir/topol.top"
    else
        topology="$work_dir/000/topol.top"
    fi

    if ! "$gmx" grompp \
        -f "inputs/energy_check.mdp" \
        -p "$topology" \
        -c "$work_dir/system.gro" \
        -o "$energy_dir/$variant.tpr" \
        > "$energy_dir/$variant.grompp.log" 2>&1; then
        die "Failed to generate the tpr for the energy check: $energy_dir/$variant.grompp.log"
    fi

    if ! "$gmx" mdrun \
        -s "$energy_dir/$variant.tpr" \
        -rerun "$work_dir/system.gro" \
        -deffnm "$energy_dir/$variant" \
        > "$energy_dir/$variant.mdrun.log" 2>&1; then
        die "energy rerun failed: $energy_dir/$variant.mdrun.log"
    fi

    if ! "$gmx" energy \
        -f "$energy_dir/$variant.edr" \
        -o "$energy_dir/$variant.xvg" \
        < "inputs/energy_selection.txt" \
        > "$energy_dir/$variant.energy.log" 2>&1; then
        die "Failed to extract potential energy: $energy_dir/$variant.energy.log"
    fi
done

"$python_bin" "compare_energy.py" \
    "$energy_dir/unscaled.xvg" \
    "$energy_dir/scale_one.xvg" \
    "$energy_tolerance"

echo "REST2 topologies and coordinates: $work_dir"
