#!/usr/bin/env bash
set -euo pipefail

source ./helpers/grompp_utils.bash

method=rest3
config=config.toml
dry_run=0
keep_intermediates=0

show_help() {
    cat <<EOF
Usage: ./build.sh [--config FILE] [--dry-run] [--keep-intermediates] INPUT.pdb

Build the solvated system, generate the $method state schedule, and create one
engine input directory per replica. T-REMD uses AMBER; REST2/REST3 use GROMACS.

Options:
  --config FILE  Read settings from FILE instead of config.toml.
  --dry-run      Print the planned build without running external programs.
  --keep-intermediates
                 Keep the temporary build directory after a successful build.
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
        --keep-intermediates)
            keep_intermediates=1
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
gmx=$("$python" helpers/config_utils.py "$config" equilibration_engine GROMACS gmx)
plumed=${PLUMED:-plumed}
build_tmp=""
build_log=""
current_stage=initialization

log_command() {
    local stage=$1
    shift
    current_stage=$stage
    {
        printf '%s stage=%q command=' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$stage"
        printf '%q ' "$@"
        printf '\n'
    } >> "$build_log"
}

log_event() {
    local stage=$1
    local status=$2
    shift 2
    printf '%s stage=%q status=%d %s\n' \
        "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$stage" "$status" "$*" >> "$build_log"
}

report_build_tmp() {
    status=$?
    trap - EXIT
    if (( status != 0 )) && [[ -n "$build_tmp" && -d "$build_tmp" ]]; then
        message="Temporary build files retained: $build_tmp"
        echo "$message" >&2
        if [[ -n "$build_log" ]]; then
            log_event "$current_stage" "$status" "temporary_directory=$build_tmp"
        fi
    fi
    exit "$status"
}

finish_build_tmp() {
    if (( keep_intermediates )); then
        echo "Temporary build files retained: $build_tmp"
        log_event cleanup 0 "kept=true temporary_directory=$build_tmp"
        return
    fi
    if [[ "$build_tmp" != "$work_dir"/.build_tmp.* ]]; then
        die "Refusing to remove unexpected temporary path: $build_tmp"
    fi
    rm -rf -- "$build_tmp"
    log_event cleanup 0 "kept=false"
    build_tmp=""
}

trap report_build_tmp EXIT

# A rebuild must not mix new inputs with topology/restart files from an older build.
if (( ! dry_run )) && [[ -d "$work_dir" ]]; then
    existing_build=$(find "$work_dir" -type f \
        \( -name '*.parm7' -o -name '*.rst7' \) -print -quit)
    if [[ -n "$existing_build" ]]; then
        die "Build output already exists and was retained: $existing_build. Use a new work directory for a new build."
    fi
fi

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
    if ! command -v "$gmx" >/dev/null 2>&1; then
        die "GROMACS not found: $gmx"
    fi
    if ! command -v "$plumed" >/dev/null 2>&1; then
        die "PLUMED not found: $plumed"
    fi
fi

if (( dry_run )); then
    echo "Method: $method"
    echo "Input structure: $input"
    echo "Config: $config"
    echo "GROMACS: $gmx"
    echo "Planned output: $work_dir/states.tsv and $work_dir/NNN replica directories"
    exit 0
fi

mkdir -p "$work_dir/inputs"
build_log="$work_dir/build.log"
: > "$build_log"
echo "Build diagnostics: $build_log"
build_tmp=$(mktemp -d "$work_dir/.build_tmp.XXXXXX")
log_event build 0 "method=$method input=$input config=$config temporary_directory=$build_tmp"
log_event versions 0 "gromacs=$("$gmx" --version 2>&1 | head -n 1) plumed=$("$plumed" info --version 2>&1 | head -n 1) parmed=$("$python" -c 'import parmed; print(parmed.__version__)')"

cp "$input" "$work_dir/input.pdb"
log_command generate-solvation-input "$python" helpers/generate_inputs.py "$method" "$config" "$work_dir/inputs"
"$python" helpers/generate_inputs.py "$method" "$config" "$work_dir/inputs"
cp "$work_dir/input.pdb" "$build_tmp/input.pdb"
mv "$work_dir/inputs/tleap.solvate.in" "$build_tmp/tleap.solvate.in"

echo "Solvating the input structure to determine the water count."
if ! (cd "$build_tmp" && "$tleap" -f tleap.solvate.in > leap.solvate.log 2>&1); then
    die "Initial tleap solvation failed. See log: $build_tmp/leap.solvate.log"
fi
cp "$build_tmp/leap.solvate.log" "$work_dir/leap.solvate.log"
log_event solvation 0 "input=$build_tmp/tleap.solvate.in output=$build_tmp/solvated.pdb log=$work_dir/leap.solvate.log"
water_count=$("$python" helpers/count_waters.py "$build_tmp/solvated.pdb")
salt_concentration=$("$python" - "$config" <<'PY'
import sys
sys.path.insert(0, "helpers")
from pathlib import Path
from config_utils import load_config
print(load_config(Path(sys.argv[1]))["build"]["salt_concentration_molar"])
PY
)
salt_pairs=$(awk -v waters="$water_count" -v concentration="$salt_concentration" 'BEGIN {printf "%d", waters * concentration / 55.5 + 0.5}')
"$python" helpers/generate_inputs.py "$method" "$config" "$work_dir/inputs" --salt-pairs "$salt_pairs"

echo "Building the AMBER system ($water_count waters, $salt_pairs salt formula units)."
if ! (cd "$work_dir" && "$tleap" -f inputs/tleap.final.in > leap.log 2>&1); then
    die "Final tleap build failed. See log: $work_dir/leap.log"
fi
log_event final-tleap 0 "input=$work_dir/inputs/tleap.final.in outputs=$work_dir/system.parm7,$work_dir/system.rst7,$work_dir/system.pdb"

echo "Generating $method replica states: $config -> $work_dir/states.tsv"
log_command generate-states "$python" helpers/generate_states.py "$method" "$config" "$work_dir/system.parm7" "$work_dir"
"$python" helpers/generate_states.py "$method" "$config" "$work_dir/system.parm7" "$work_dir"
"$python" helpers/generate_inputs.py "$method" "$config" "$work_dir/inputs" \
    --salt-pairs "$salt_pairs" --states "$work_dir/states.tsv"
log_event generate-states 0 "output=$work_dir/states.tsv"
echo "Converting AMBER topology: $work_dir/system.parm7 -> $work_dir/topol.top, $work_dir/system.gro"
log_command convert-topology "$python" helpers/convert_topology.py "$work_dir/system.parm7" "$work_dir/system.rst7" "$work_dir/topol.top" "$work_dir/system.gro"
"$python" helpers/convert_topology.py "$work_dir/system.parm7" "$work_dir/system.rst7" \
    "$work_dir/topol.top" "$work_dir/system.gro"
helper_dir=helpers
# ParmEd can emit CMAP numbers longer than GROMACS 2024.x can safely parse.
"$python" "$helper_dir/scale_cmap.py" "$work_dir/topol.top" "$work_dir/topol.top" 1.0
log_event convert-topology 0 "outputs=$work_dir/topol.top,$work_dir/system.gro"
log_command preprocess "$gmx" grompp -f inputs/energy_check.mdp -p "$work_dir/topol.top" -c "$work_dir/system.gro" -pp "$build_tmp/processed.top" -o "$build_tmp/preprocess.tpr"
if ! run_grompp "$build_tmp/grompp_preprocess.log" \
    "$gmx" grompp -f "inputs/energy_check.mdp" \
    -p "$work_dir/topol.top" -c "$work_dir/system.gro" \
    -pp "$build_tmp/processed.top" -o "$build_tmp/preprocess.tpr"; then
    die "Processed topology generation failed: $build_tmp/grompp_preprocess.log"
fi
"$python" "$helper_dir/scale_cmap.py" "$work_dir/topol.top" "$build_tmp/processed.top" 1.0

"$python" helpers/generate_rest3_topologies.py "$build_tmp/processed.top" "$work_dir/states.tsv" "$work_dir"
while IFS=$'\t' read -r replica _; do
    if [[ "$replica" == replica ]]; then
        continue
    fi
    printf 'energy: ENERGY\nPRINT ARG=energy STRIDE=5000 FILE=plumed_energy.dat\n' > "$work_dir/$replica/plumed.dat"
done < "$work_dir/states.tsv"
"$python" helpers/verify_rest3.py \
    "$build_tmp/processed.top" "$work_dir/states.tsv" "$work_dir"

echo "Checking unscaled and scale-one energies: $work_dir/system.gro; logs: $build_tmp/energy_check"
energy_dir="$build_tmp/energy_check"
mkdir -p "$energy_dir"
for variant in unscaled scale_one; do
    log_event energy-check 0 "variant=$variant raw_directory=$energy_dir"
    if [[ "$variant" == unscaled ]]; then
        topology="$work_dir/topol.top"
    else
        topology="$work_dir/000/topol.top"
    fi
    if ! run_grompp "$energy_dir/$variant.grompp.log" \
        "$gmx" grompp \
        -f "inputs/energy_check.mdp" \
        -p "$topology" \
        -c "$work_dir/system.gro" \
        -o "$energy_dir/$variant.tpr"; then
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
        < "inputs/energy_selection.txt" \
        > "$energy_dir/$variant.energy.log" 2>&1; then
        die "Potential-energy extraction failed: $energy_dir/$variant.energy.log"
    fi
done
"$python" "$helper_dir/compare_energy.py" \
    "$energy_dir/unscaled.xvg" \
    "$energy_dir/scale_one.xvg" \
    0.1 \
    --output "$work_dir/energy_check.tsv"
log_event energy-check 0 "status=pass output=$work_dir/energy_check.tsv"

replica_count=$(awk 'NR > 1 {count++} END {print count + 0}' "$work_dir/states.tsv")
topology_args=(--topology "$work_dir/topol.top")
while IFS=$'\t' read -r replica _; do
    if [[ "$replica" == "replica" ]]; then
        continue
    fi
    topology_args+=(--topology "$work_dir/$replica/topol.top")
done < "$work_dir/states.tsv"

for output in "$work_dir/system.gro" "$work_dir/topol.top" "$work_dir/states.tsv" \
    "$work_dir/resolved_config.toml" "$work_dir/energy_check.tsv"; do
    if [[ ! -s "$output" ]]; then
        die "Final build output is missing or empty: $output"
    fi
done

echo "Completed: REST energy check ($work_dir/energy_check.tsv)"
log_command build-summary "$python" helpers/build_provenance.py --output "$work_dir/build_summary.toml"
"$python" helpers/build_provenance.py \
    --output "$work_dir/build_summary.toml" \
    --method "$method" \
    --gromacs "$gmx" \
    --plumed "$plumed" \
    --python "$python" \
    --resolved-config "$work_dir/resolved_config.toml" \
    --base-topology "$work_dir/topol.top" \
    --states "$work_dir/states.tsv" \
    --energy-table "$work_dir/energy_check.tsv" \
    --warning-log "$build_tmp/grompp_preprocess.log" \
    --warning-log "$energy_dir/unscaled.grompp.log" \
    --warning-log "$energy_dir/scale_one.grompp.log" \
    "${topology_args[@]}"
if [[ ! -s "$work_dir/build_summary.toml" ]]; then
    die "Final build summary missing or empty: $work_dir/build_summary.toml"
fi
log_event build-summary 0 "output=$work_dir/build_summary.toml energy_table=$work_dir/energy_check.tsv"

finish_build_tmp

echo "Built $replica_count $method replicas: $work_dir/000 ..."
