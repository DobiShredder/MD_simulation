#!/usr/bin/env bash
set -euo pipefail

if [[ "${1:-}" == -h || "${1:-}" == --help ]]; then
    cat <<'EOF'
Usage: ./build_replicas.sh METHOD [--config FILE] [--dry-run] INPUT.pdb

Shared internal builder used by the T-REMD, REST2, and REST3 build.sh wrappers.
METHOD must be remd, rest2, or rest3.

Options:
  --config FILE  Read settings from FILE instead of config.toml.
  --dry-run      Print the planned build without running external programs.
  -h, --help     Show this help message and exit.
EOF
    exit 0
fi
if [[ $# -lt 1 ]]; then
    echo "Error: METHOD is required." >&2
    exit 2
fi
method=$1
shift
if [[ "$method" != remd && "$method" != rest2 && "$method" != rest3 ]]; then
    echo "Error: METHOD must be remd, rest2, or rest3." >&2
    exit 2
fi
config=config.toml
dry_run=0

show_help() {
    cat <<EOF
Usage: ./build.sh [--config FILE] [--dry-run] INPUT.pdb

Build the solvated system, generate the $method state schedule, and create one
engine input directory per replica. T-REMD uses AMBER; REST2/REST3 use GROMACS.

Options:
  --config FILE  Read settings from FILE instead of config.toml.
  --dry-run      Print the planned build without running external programs.
  -h, --help     Show this help message and exit.
EOF
}

while [[ $# -gt 0 ]]; do
    case "$1" in
        --config)
            if [[ $# -lt 2 ]]; then
                echo "Error: --config requires a file." >&2
                exit 2
            fi
            config=$2
            shift 2
            ;;
        --dry-run)
            dry_run=1
            shift
            ;;
        -h|--help)
            show_help
            exit 0
            ;;
        *)
            break
            ;;
    esac
done

if [[ $# -ne 1 ]]; then
    show_help >&2
    exit 2
fi

die() {
    echo "Error: $*" >&2
    exit 1
}

input=$1
work_dir=${WORK_DIR:-work}
python=${PYTHON:-python3}
tleap=${TLEAP:-tleap}
gmx=${GROMACS:-gmx}
plumed=${PLUMED:-plumed}

if [[ -d "$work_dir" ]]; then
    existing_result=$(find "$work_dir" -type f \( -name '.*.complete' -o -name '*.out' -o -name '*.cpt' \) -print -quit)
    if [[ -n "$existing_result" ]]; then
        die "Existing simulation results were found: $existing_result"
    fi
fi

if (( ! dry_run )); then
    if [[ ! -s "$input" ]]; then
        die "Input PDB not found: $input"
    fi
    if [[ ! -s "$config" ]]; then
        die "Config file not found: $config"
    fi
    for executable in "$python" "$tleap"; do
        if ! command -v "$executable" >/dev/null 2>&1; then
            die "Executable not found: $executable"
        fi
    done
    if ! "$python" -c 'import parmed' >/dev/null 2>&1; then
        die "ParmEd is required. Install requirements.txt."
    fi
    if [[ "$method" == rest2 || "$method" == rest3 ]]; then
        if ! command -v "$gmx" >/dev/null 2>&1; then
            die "GROMACS not found: $gmx"
        fi
        if ! command -v "$plumed" >/dev/null 2>&1; then
            die "PLUMED not found: $plumed"
        fi
    fi
fi

if (( dry_run )); then
    echo "Method: $method"
    echo "Input structure: $input"
    echo "Config: $config"
    echo "Planned output: $work_dir/states.tsv and $work_dir/NNN replica directories"
    exit 0
fi

mkdir -p "$work_dir/inputs"
cp "$input" "$work_dir/input.pdb"
"$python" generate_inputs.py "$method" "$config" "$work_dir/inputs"

echo "Solvating the input structure to determine the water count."
if ! (cd "$work_dir" && "$tleap" -f inputs/tleap.solvate.in > leap.solvate.log 2>&1); then
    die "Initial tleap solvation failed. See log: $work_dir/leap.solvate.log"
fi
water_count=$("$python" count_waters.py "$work_dir/solvated.pdb")
salt_concentration=$("$python" - "$config" <<'PY'
import sys
sys.path.insert(0, ".")
from pathlib import Path
from config_utils import load_config
print(load_config(Path(sys.argv[1]))["build"]["salt_concentration_molar"])
PY
)
salt_pairs=$(awk -v waters="$water_count" -v concentration="$salt_concentration" 'BEGIN {printf "%d", waters * concentration / 55.5 + 0.5}')
"$python" generate_inputs.py "$method" "$config" "$work_dir/inputs" --salt-pairs "$salt_pairs"

echo "Building the AMBER system ($water_count waters, $salt_pairs salt formula units)."
if ! (cd "$work_dir" && "$tleap" -f inputs/tleap.final.in > leap.log 2>&1); then
    die "Final tleap build failed. See log: $work_dir/leap.log"
fi

"$python" generate_states.py "$method" "$config" "$work_dir/system.parm7" "$work_dir"
"$python" generate_inputs.py "$method" "$config" "$work_dir/inputs" \
    --salt-pairs "$salt_pairs" --states "$work_dir/states.tsv"

if [[ "$method" == rest2 || "$method" == rest3 ]]; then
    "$python" convert_topology.py "$work_dir/system.parm7" "$work_dir/system.rst7" \
        "$work_dir/topol.top" "$work_dir/system.gro"
    helper_dir="."
    if ! "$gmx" grompp -f "$helper_dir/inputs/energy_check.mdp" \
        -p "$work_dir/topol.top" -c "$work_dir/system.gro" \
        -pp "$work_dir/processed.top" -o "$work_dir/preprocess.tpr" \
        > "$work_dir/grompp_preprocess.log" 2>&1; then
        die "Processed topology generation failed: $work_dir/grompp_preprocess.log"
    fi
    "$python" "$helper_dir/scale_cmap.py" "$work_dir/topol.top" "$work_dir/processed.top" 1.0
fi

if [[ "$method" == remd ]]; then
    while IFS=$'\t' read -r replica _; do
        if [[ "$replica" == replica ]]; then
            continue
        fi
        cp "$work_dir/system.parm7" "$work_dir/$replica/system.parm7"
        cp "$work_dir/system.rst7" "$work_dir/$replica/system.rst7"
    done < "$work_dir/states.tsv"
elif [[ "$method" == rest2 ]]; then
    helper_dir="."
    "$python" "$helper_dir/mark_hot.py" "$work_dir/processed.top" "$work_dir/processed.hot.top"
    while IFS=$'\t' read -r replica _ lambda_pp _ _; do
        if [[ "$replica" == replica ]]; then
            continue
        fi
        "$plumed" partial_tempering "$lambda_pp" < "$work_dir/processed.hot.top" > "$work_dir/$replica/topol.top"
        "$python" "$helper_dir/scale_cmap.py" "$work_dir/processed.top" "$work_dir/$replica/topol.top" "$lambda_pp"
        cp "$work_dir/system.gro" "$work_dir/$replica/system.gro"
        printf 'energy: ENERGY\nPRINT ARG=energy STRIDE=5000 FILE=plumed_energy.dat\n' > "$work_dir/$replica/plumed.dat"
    done < "$work_dir/states.tsv"

    energy_dir="$work_dir/energy_check"
    mkdir -p "$energy_dir"
    for variant in unscaled scale_one; do
        if [[ "$variant" == unscaled ]]; then
            topology="$work_dir/topol.top"
        else
            topology="$work_dir/000/topol.top"
        fi
        if ! "$gmx" grompp \
            -f "$helper_dir/inputs/energy_check.mdp" \
            -p "$topology" \
            -c "$work_dir/system.gro" \
            -o "$energy_dir/$variant.tpr" \
            > "$energy_dir/$variant.grompp.log" 2>&1; then
            die "Energy-check tpr generation failed: $energy_dir/$variant.grompp.log"
        fi
        if ! "$gmx" mdrun \
            -s "$energy_dir/$variant.tpr" \
            -rerun "$work_dir/system.gro" \
            -deffnm "$energy_dir/$variant" \
            > "$energy_dir/$variant.mdrun.log" 2>&1; then
            die "Energy rerun failed: $energy_dir/$variant.mdrun.log"
        fi
        if ! "$gmx" energy \
            -f "$energy_dir/$variant.edr" \
            -o "$energy_dir/$variant.xvg" \
            < "$helper_dir/inputs/energy_selection.txt" \
            > "$energy_dir/$variant.energy.log" 2>&1; then
            die "Potential-energy extraction failed: $energy_dir/$variant.energy.log"
        fi
    done
    "$python" "$helper_dir/compare_energy.py" \
        "$energy_dir/unscaled.xvg" \
        "$energy_dir/scale_one.xvg" \
        0.1
else
    "$python" generate_rest3_topologies.py "$work_dir/processed.top" "$work_dir/states.tsv" "$work_dir"
    while IFS=$'\t' read -r replica _; do
        if [[ "$replica" == replica ]]; then
            continue
        fi
        cp "$work_dir/system.gro" "$work_dir/$replica/system.gro"
        printf 'energy: ENERGY\nPRINT ARG=energy STRIDE=5000 FILE=plumed_energy.dat\n' > "$work_dir/$replica/plumed.dat"
    done < "$work_dir/states.tsv"
    "$python" verify_rest3.py \
        "$work_dir/processed.top" "$work_dir/states.tsv" "$work_dir"
fi

replica_count=$(awk 'NR > 1 {count++} END {print count + 0}' "$work_dir/states.tsv")
echo "Built $replica_count $method replicas: $work_dir/000 ..."
