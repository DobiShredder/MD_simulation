#!/usr/bin/env bash
set -euo pipefail

config=config.toml
dry_run=0

show_help() {
    cat <<'EOF'
Usage: ./build.sh [--config FILE] [--dry-run] ORIENTED-PROTEIN.pdb

Pack a membrane-oriented protein into user-supplied Lipid21 bilayer patches and
build an ff19SB/Lipid21/OPC AMBER system.

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
        *) break ;;
    esac
done
if [[ $# -ne 1 ]]; then
    show_help >&2
    exit 2
fi

die() { echo "Error: $*" >&2; exit 1; }
input=$1
work_dir=${WORK_DIR:-work}
python=${PYTHON:-python3}
tleap=${TLEAP:-tleap}

if [[ -d "$work_dir" ]]; then
    existing=$(find "$work_dir" -type f \( -name '.*.complete' -o -name '*.out' \) -print -quit)
    if [[ -n "$existing" ]]; then
        die "Existing simulation results were found: $existing"
    fi
fi
if (( dry_run )); then
    echo "Input oriented protein: $input"
    echo "Config: $config"
    echo "Planned output: $work_dir/system.parm7 and $work_dir/system.rst7"
    exit 0
fi
if [[ ! -s "$input" ]]; then
    die "Input PDB not found: $input"
fi
if [[ ! -s "$config" ]]; then
    die "Config file not found: $config"
fi
if ! command -v "$python" >/dev/null 2>&1; then
    die "Python not found: $python"
fi
if ! command -v "$tleap" >/dev/null 2>&1; then
    die "tleap not found: $tleap"
fi
if ! "$python" -c 'import numpy' >/dev/null 2>&1; then
    die "NumPy is required."
fi

mkdir -p "$work_dir/inputs"
cp "$input" "$work_dir/input.pdb"
"$python" generate_inputs.py "$config" "$work_dir/inputs"
parameter_file="$work_dir/build_parameters.tsv"
composition=$(awk -F '\t' '$1=="composition" {print $2}' "$parameter_file")
popc=$(awk -F '\t' '$1=="popc" {print $2}' "$parameter_file")
pope=$(awk -F '\t' '$1=="pope" {print $2}' "$parameter_file")
cholesterol=$(awk -F '\t' '$1=="cholesterol" {print $2}' "$parameter_file")
xy_padding=$(awk -F '\t' '$1=="xy_padding" {print $2}' "$parameter_file")
water_padding=$(awk -F '\t' '$1=="water_padding" {print $2}' "$parameter_file")
protein_lipid_distance=$(awk -F '\t' '$1=="protein_lipid_distance" {print $2}' "$parameter_file")

echo "Packing the oriented protein into the configured bilayer."
"$python" build_membrane.py "$work_dir/input.pdb" "$popc" "$pope" "$cholesterol" \
    "$work_dir/system-coordinates.pdb" --composition "$composition" \
    --xy-padding "$xy_padding" --water-padding "$water_padding" \
    --protein-lipid-distance "$protein_lipid_distance"
"$python" generate_inputs.py "$config" "$work_dir/inputs" --coordinate "$work_dir/system-coordinates.pdb"

if ! (cd "$work_dir" && "$tleap" -f inputs/tleap.in > leap.log 2>&1); then
    die "tleap failed. See log: $work_dir/leap.log"
fi
"$python" apply_config.py "$config" "$work_dir"
for output in system.parm7 system.rst7 system.pdb resolved_config.toml; do
    if [[ ! -s "$work_dir/$output" ]]; then
        die "Build output was not created: $work_dir/$output"
    fi
done
echo "Membrane topology and restart: $work_dir/system.parm7, $work_dir/system.rst7"
