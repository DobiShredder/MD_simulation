#!/usr/bin/env bash
set -euo pipefail

dry_run=0
config=config.toml

show_help() {
    cat <<'EOF'
Usage: ./build.sh [--config FILE] [--dry-run] INPUT.pdb

Build the shared ff19SB/OPC topology used by all umbrella windows.

Options:
  --config FILE  Read settings from FILE instead of config.toml.
  --dry-run      Print the planned build without running external programs.
  -h, --help     Show this help message and exit.
EOF
}

while [[ $# -gt 0 ]]; do
    case "$1" in
        --dry-run)
            dry_run=1
            shift
            ;;
        --config)
            if [[ $# -lt 2 ]]; then
                echo "Error: --config requires a file." >&2
                exit 2
            fi
            config=$2
            shift 2
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
tleap=${TLEAP:-tleap}
python=${PYTHON:-python3}

if [[ -d "$work_dir" ]]; then
    existing_result=$(find "$work_dir" -type f \( -name '.*.complete' -o -name '*.out' \) -print -quit)
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
    if ! command -v "$tleap" >/dev/null 2>&1; then
        die "tleap not found: $tleap"
    fi
    if ! command -v "$python" >/dev/null 2>&1; then
        die "Python not found: $python"
    fi
fi

if (( dry_run )); then
    printf '+ %q generate_inputs.py %q %q\n' "$python" "$config" "$work_dir/inputs"
    printf '+ %q -f %q\n' "$tleap" "$work_dir/inputs/tleap.solvate.in"
    echo '+ python3 ../../common/count_waters.py work/solvated.pdb'
    echo '+ python3 generate_inputs.py config.toml work/inputs --salt-pairs N'
    printf '+ %q -f %q\n' "$tleap" "$work_dir/inputs/tleap.final.in"
    exit 0
fi

mkdir -p "$work_dir/inputs"
cp "$input" "$work_dir/input.pdb"
"$python" generate_inputs.py "$config" "$work_dir/inputs"

echo "Solvating the input structure to determine the water count."
if ! (
    cd "$work_dir"
    "$tleap" -f inputs/tleap.solvate.in > leap.solvate.log 2>&1
); then
    die "Initial tleap solvation failed. See log: $work_dir/leap.solvate.log"
fi

water_count=$("$python" ../../common/count_waters.py "$work_dir/solvated.pdb")
salt_concentration=$("$python" - "$config" <<'PY'
import sys
sys.path.insert(0, "../../common")
from pathlib import Path
from config_utils import load_config
print(load_config(Path(sys.argv[1]))["build"]["salt_concentration_molar"])
PY
)
salt_pairs=$(awk -v waters="$water_count" -v concentration="$salt_concentration" \
    'BEGIN { printf "%d", waters * concentration / 55.5 + 0.5 }')

"$python" generate_inputs.py "$config" "$work_dir/inputs" --salt-pairs "$salt_pairs"

echo "Building the final solvated system ($water_count waters, $salt_pairs salt formula units)."
if ! (
    cd "$work_dir"
    "$tleap" -f inputs/tleap.final.in > leap.log 2>&1
); then
    die "Final tleap build failed. See log: $work_dir/leap.log"
fi

for output in system.parm7 system.rst7 system.pdb resolved_config.toml; do
    if [[ ! -s "$work_dir/$output" ]]; then
        die "Build output was not created: $work_dir/$output"
    fi
done

echo "AMBER topology and restart: $work_dir/system.parm7, $work_dir/system.rst7"
