#!/usr/bin/env bash
set -euo pipefail

dry_run=0
config=config.toml

show_help() {
    cat <<'EOF'
Usage: ./build.sh [--config FILE] [--dry-run] INPUT.pdb

Build an explicit-solvent AMBER system and WT-MetaD CV context.

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
        --dry-run) dry_run=1; shift ;;
        -h|--help) show_help; exit 0 ;;
        *) break ;;
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

if [[ -d "$work_dir" ]]; then
    existing=$(find "$work_dir" -type f \( -name '.*.complete' -o -name 'production.out' -o -name 'HILLS' -o -name 'KERNELS' -o -name 'DELTAFS' \) -print -quit)
    if [[ -n "$existing" ]]; then
        die "Existing simulation result was found: $existing"
    fi
fi

if (( dry_run )); then
    echo "+ $python generate_inputs.py $config $work_dir/inputs"
    echo "+ $tleap -f inputs/tleap.solvate.in"
    echo "+ count waters and calculate salt formula units"
    echo "+ $tleap -f inputs/tleap.final.in"
    echo "+ record topology atom count and collective-variable definitions"
    exit 0
fi

for required in "$input" "$config"; do
    if [[ ! -s "$required" ]]; then
        die "Required build input not found: $required"
    fi
done
for executable in "$python" "$tleap"; do
    if ! command -v "$executable" >/dev/null 2>&1; then
        die "Executable not found: $executable"
    fi
done

mkdir -p "$work_dir/inputs"
cp "$input" "$work_dir/input.pdb"
cp "$config" "$work_dir/source_config.toml"

cv_file=$("$python" - "$config" <<'PY'
import sys
sys.path.insert(0, ".")
from pathlib import Path
from config_utils import load_config

print(load_config(Path(sys.argv[1]))["collective_variable"]["definitions_file"])
PY
)
if [[ ! -s "$cv_file" ]]; then
    die "Collective-variable definition file not found: $cv_file"
fi
cp "$cv_file" "$work_dir/cv.dat"

"$python" generate_inputs.py "$config" "$work_dir/inputs"

echo "Solvating the MetaD system to determine the water count."
if ! (cd "$work_dir"; "$tleap" -f inputs/tleap.solvate.in > leap.solvate.log 2>&1); then
    die "Initial tleap solvation failed: $work_dir/leap.solvate.log"
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
"$python" generate_inputs.py "$config" "$work_dir/inputs" --salt-pairs "$salt_pairs"

echo "Building the final MetaD system ($water_count waters, $salt_pairs salt formula units)."
if ! (cd "$work_dir"; "$tleap" -f inputs/tleap.final.in > leap.log 2>&1); then
    die "Final tleap build failed: $work_dir/leap.log"
fi
for output in system.parm7 system.rst7 system.pdb resolved_config.toml; do
    if [[ ! -s "$work_dir/$output" ]]; then
        die "Build output was not created: $work_dir/$output"
    fi
done

"$python" - "$work_dir/system.parm7" "$work_dir/atom_count.txt" <<'PY'
import sys
from pathlib import Path
import parmed

topology = parmed.load_file(sys.argv[1])
Path(sys.argv[2]).write_text(f"{len(topology.atoms)}\n", encoding="ascii")
PY

echo "MetaD topology and generated inputs: $work_dir"
