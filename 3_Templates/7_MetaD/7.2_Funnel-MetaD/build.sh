#!/usr/bin/env bash
set -euo pipefail

dry_run=0
config=config.toml

show_help() {
    cat <<'EOF'
Usage: ./build.sh [--config FILE] [--dry-run] COMPLEX.pdb

Build a protein-ligand AMBER system and resolve the configured funnel geometry.

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
    existing=$(find "$work_dir" -type f \( -name '.*.complete' -o -name 'production.out' -o -name 'HILLS' -o -name 'KERNELS' -o -name 'DELTAFS' \) -print -quit)
    if [[ -n "$existing" ]]; then
        die "Existing simulation result was found: $existing"
    fi
fi

if (( dry_run )); then
    echo "+ $python helpers/generate_inputs.py $config $work_dir/inputs"
    echo "+ first-pass tleap in $work_dir/.build_tmp.XXXXXX"
    echo "+ count waters and calculate salt formula units"
    echo "+ $tleap -f inputs/tleap.final.in"
    echo "+ $python helpers/setup_funnel.py $config system.parm7 system.rst7 $work_dir"
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

readarray -t ligand_files < <("$python" - "$config" <<'PY'
import sys
sys.path.insert(0, "helpers")
from pathlib import Path
from config_utils import load_config

build = load_config(Path(sys.argv[1]))["build"]
print(build["ligand_mol2"])
print(build["ligand_frcmod"])
PY
)
if [[ ${#ligand_files[@]} -ne 2 ]]; then
    die "Could not read ligand_mol2 and ligand_frcmod from $config"
fi
for ligand_file in "${ligand_files[@]}"; do
    if [[ ! -s "$ligand_file" ]]; then
        die "Ligand parameter file not found: $ligand_file"
    fi
done
cp "${ligand_files[0]}" "$work_dir/ligand.mol2"
cp "${ligand_files[1]}" "$work_dir/ligand.frcmod"
"$python" - "$config" "$work_dir/ligand.mol2" <<'PY'
import sys
sys.path.insert(0, "helpers")
from pathlib import Path
from config_utils import load_config
import parmed

build = load_config(Path(sys.argv[1]))["build"]
ligand = parmed.load_file(sys.argv[2])
names = {residue.name for residue in ligand.residues}
expected_name = build["ligand_residue_name"]
if names != {expected_name}:
    raise SystemExit(
        f"Ligand MOL2 residue name mismatch: expected {expected_name}, found {sorted(names)}"
    )
observed_charge = sum(float(atom.charge) for atom in ligand.atoms)
expected_charge = int(build["ligand_net_charge"])
if abs(observed_charge - expected_charge) > 1.0e-4:
    raise SystemExit(
        f"Ligand MOL2 charge mismatch: expected {expected_charge}, found {observed_charge:.6f}"
    )
PY

"$python" helpers/generate_inputs.py "$config" "$work_dir/inputs"
build_tmp=$(mktemp -d "$work_dir/.build_tmp.XXXXXX")
cp "$work_dir/input.pdb" "$build_tmp/input.pdb"
mv "$work_dir/inputs/tleap.solvate.in" "$build_tmp/tleap.solvate.in"

echo "Solvating the MetaD system to determine the water count."
if ! (cd "$build_tmp"; "$tleap" -f tleap.solvate.in > leap.solvate.log 2>&1); then
    die "Initial tleap solvation failed: $build_tmp/leap.solvate.log"
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
"$python" helpers/generate_inputs.py "$config" "$work_dir/inputs" --salt-pairs "$salt_pairs"

echo "Building the final MetaD system ($water_count waters, $salt_pairs salt formula units)."
if ! (cd "$work_dir"; "$tleap" -f inputs/tleap.final.in > leap.log 2>&1); then
    die "Final tleap build failed: $work_dir/leap.log"
fi
for output in system.parm7 system.rst7 system.pdb resolved_config.toml; do
    if [[ ! -s "$work_dir/$output" ]]; then
        die "Build output was not created: $work_dir/$output"
    fi
done

echo "Preparing funnel geometry: $config; topology: $work_dir/system.parm7; output: $work_dir"
"$python" helpers/setup_funnel.py \
    "$config" "$work_dir/system.parm7" "$work_dir/system.rst7" "$work_dir"

remove_build_tmp

echo "MetaD topology and generated inputs: $work_dir"
