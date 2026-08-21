#!/usr/bin/env bash
set -euo pipefail

dry_run=0
config=config.toml

show_help() {
    cat <<'EOF'
Usage: ./build_metad.sh METHOD [--config FILE] [--dry-run] INPUT.pdb

Build an explicit-solvent AMBER system and the method-specific PLUMED context.

Arguments:
  METHOD         wt-metad, funnel-metad, opes-metad, or opes-expanded.
  INPUT.pdb      Reviewed protein or protein-ligand coordinate file.

Options:
  --config FILE  Read settings from FILE instead of config.toml.
  --dry-run      Print the planned build without running external programs.
  -h, --help     Show this help message and exit.
EOF
}

if [[ $# -lt 1 ]]; then
    show_help >&2
    exit 2
fi
method=$1
shift
case "$method" in
    wt-metad|funnel-metad|opes-metad|opes-expanded) ;;
    -h|--help) show_help; exit 0 ;;
    *) echo "Error: unknown method: $method" >&2; exit 2 ;;
esac

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
    echo "+ $python generate_inputs.py $method $config $work_dir/inputs"
    echo "+ $tleap -f inputs/tleap.solvate.in"
    echo "+ count waters and calculate salt formula units"
    echo "+ $tleap -f inputs/tleap.final.in"
    if [[ "$method" == funnel-metad ]]; then
        echo "+ $python setup_funnel.py $config system.parm7 system.rst7 $work_dir"
    else
        echo "+ record topology atom count and collective-variable definitions"
    fi
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

if [[ "$method" == funnel-metad ]]; then
    readarray -t ligand_files < <("$python" - "$config" <<'PY'
import sys
sys.path.insert(0, ".")
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
sys.path.insert(0, ".")
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
elif [[ "$method" != opes-expanded ]]; then
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
fi

"$python" generate_inputs.py "$method" "$config" "$work_dir/inputs"

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
"$python" generate_inputs.py "$method" "$config" "$work_dir/inputs" --salt-pairs "$salt_pairs"

echo "Building the final MetaD system ($water_count waters, $salt_pairs salt formula units)."
if ! (cd "$work_dir"; "$tleap" -f inputs/tleap.final.in > leap.log 2>&1); then
    die "Final tleap build failed: $work_dir/leap.log"
fi
for output in system.parm7 system.rst7 system.pdb resolved_config.toml; do
    if [[ ! -s "$work_dir/$output" ]]; then
        die "Build output was not created: $work_dir/$output"
    fi
done

if [[ "$method" == funnel-metad ]]; then
    "$python" setup_funnel.py \
        "$config" "$work_dir/system.parm7" "$work_dir/system.rst7" "$work_dir"
else
    "$python" - "$work_dir/system.parm7" "$work_dir/atom_count.txt" <<'PY'
import sys
from pathlib import Path
import parmed

topology = parmed.load_file(sys.argv[1])
Path(sys.argv[2]).write_text(f"{len(topology.atoms)}\n", encoding="ascii")
PY
fi

echo "MetaD topology and generated inputs: $work_dir"
