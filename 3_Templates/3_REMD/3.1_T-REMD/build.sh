#!/usr/bin/env bash
set -euo pipefail

method=remd
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
build_tmp=""

report_build_tmp() {
    status=$?
    trap - EXIT
    if (( status != 0 )) && [[ -n "$build_tmp" && -d "$build_tmp" ]]; then
        echo "Temporary build files retained: $build_tmp" >&2
    fi
    exit "$status"
}

remove_build_tmp() {
    if [[ "$build_tmp" != "$work_dir"/.build_tmp.* ]]; then
        die "Refusing to remove unexpected temporary path: $build_tmp"
    fi
    rm -rf -- "$build_tmp"
    build_tmp=""
}

trap report_build_tmp EXIT
tleap=${TLEAP:-tleap}

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
"$python" helpers/generate_inputs.py "$method" "$config" "$work_dir/inputs"
build_tmp=$(mktemp -d "$work_dir/.build_tmp.XXXXXX")
cp "$work_dir/input.pdb" "$build_tmp/input.pdb"
mv "$work_dir/inputs/tleap.solvate.in" "$build_tmp/tleap.solvate.in"

echo "Solvating the input structure to determine the water count."
if ! (cd "$build_tmp" && "$tleap" -f tleap.solvate.in > leap.solvate.log 2>&1); then
    die "Initial tleap solvation failed. See log: $build_tmp/leap.solvate.log"
fi
cp "$build_tmp/leap.solvate.log" "$work_dir/leap.solvate.log"
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

"$python" helpers/generate_states.py "$method" "$config" "$work_dir/system.parm7" "$work_dir"
"$python" helpers/generate_inputs.py "$method" "$config" "$work_dir/inputs" \
    --salt-pairs "$salt_pairs" --states "$work_dir/states.tsv"

replica_count=$(awk 'NR > 1 {count++} END {print count + 0}' "$work_dir/states.tsv")
remove_build_tmp

echo "Built $replica_count $method replicas: $work_dir/000 ..."
