#!/usr/bin/env bash
set -euo pipefail

if [[ $# -ne 1 ]]; then
    echo "Usage: $0 INPUT.pdb" >&2
    exit 2
fi

die() {
    echo "Error: $*" >&2
    exit 1
}

input_pdb=$1
temperature_file=inputs/temperatures.txt
kappa_file=inputs/kappa.txt
work_dir=work

# A rebuild must not mix new inputs with topology/restart files from an older build.
if [[ -d "$work_dir" ]]; then
    existing_build=$(find "$work_dir" -type f \
        \( -name '*.parm7' -o -name '*.rst7' \) -print -quit)
    if [[ -n "$existing_build" ]]; then
        die "Build output already exists and was retained: $existing_build. Use a new work directory for a new build."
    fi
fi

states_file="$work_dir/states.tsv"
tleap=${TLEAP:-tleap}
gmx=${GROMACS:-gmx}
python_bin=${PYTHON:-python3}

if find "$work_dir" -type f \
    \( -name 'minimize.gro' -o -name 'equilibrate.gro' -o -name 'production.gro' \) \
    -print -quit 2>/dev/null | grep -q .; then
    die "Simulation output already exists in $work_dir. Remove it before rebuilding."
fi

for input_file in "$input_pdb" "$temperature_file" "$kappa_file"; do
    if [[ ! -s "$input_file" ]]; then
        die "Required input not found: $input_file"
    fi
done

if ! replica_count=$("$python_bin" generate_states.py --count "$temperature_file" "$kappa_file"); then
    die "REST3 temperature/kappa-list validation failed: $temperature_file, $kappa_file"
fi
for executable in "$tleap" "$gmx" "$python_bin"; do
    if ! command -v "$executable" >/dev/null 2>&1; then
        die "Executable not found: $executable"
    fi
done
if ! "$python_bin" -c "import parmed" >/dev/null 2>&1; then
    die "ParmEd is required: $python_bin -m pip install -r requirements.txt"
fi

echo "Generating an ff19SB/OPC AMBER system."
mkdir -p "$work_dir"
cp "$input_pdb" "$work_dir/input.pdb"
cp inputs/tleap.in "$work_dir/tleap.in"

if ! "$python_bin" generate_states.py \
    "$temperature_file" \
    "$kappa_file" \
    "$states_file"; then
    die "REST3 state-table generation failed: $states_file"
fi
if ! "$python_bin" validate_states.py "$states_file"; then
    die "Generated REST3 state-table validation failed: $states_file"
fi

if ! (
    cd "$work_dir"
    "$tleap" \
        -f tleap.in \
        > leap.log 2>&1
); then
    die "tleap failed. See log: $work_dir/leap.log"
fi

echo "Converting AMBER topology to GROMACS: $work_dir/system.parm7"
if ! "$python_bin" "convert_topology.py" \
    "$work_dir/system.parm7" \
    "$work_dir/system.rst7" \
    "$work_dir/topol.top" \
    "$work_dir/system.gro"; then
    die "ParmEd topology conversion failed: $work_dir/system.parm7, $work_dir/system.rst7 -> $work_dir/topol.top"
fi

# ParmEd can emit CMAP numbers longer than GROMACS 2024.x can safely parse.
if ! "$python_bin" "scale_cmap.py" \
    "$work_dir/topol.top" \
    "$work_dir/topol.top" \
    1.0; then
    die "CMAP serialization normalization failed: $work_dir/topol.top"
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
    die "Failed to restore residue-specific CMAPs: $work_dir/topol.top -> $work_dir/processed.top"
fi

echo "Generating REST3 topologies with the published κ schedule."

if ! "$python_bin" "generate_rest3.py" \
    "$work_dir/processed.top" \
    "$states_file" \
    "$work_dir"; then
    die "REST3 topology generation failed: $states_file, $work_dir/processed.top"
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

if ! "$python_bin" "verify_rest3.py" \
    "$work_dir/processed.top" \
    "$work_dir/states.tsv" \
    "$work_dir"; then
    die "REST3 topology-preservation check failed: $states_file, $work_dir/processed.top and replica topologies in $work_dir"
fi

echo "REST3 topologies and coordinates: $work_dir"
