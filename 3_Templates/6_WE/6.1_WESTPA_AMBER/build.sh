#!/usr/bin/env bash
set -euo pipefail

config=config.toml
dry_run=0

show_help() {
    cat <<'EOF'
Usage: ./build.sh [--config FILE] [--dry-run] INPUT.pdb

Build an ff19SB/OPC system, equilibrated WESTPA basis state, and block configs.

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
tleap=${TLEAP:-tleap}
python=${PYTHON:-python3}

if [[ -d "$work_dir" ]]; then
    existing=$(find "$work_dir" -type f \( -name 'west.h5' -o -name '.block.*.complete' \) -print -quit)
    if [[ -n "$existing" ]]; then
        die "Existing WESTPA production state was found: $existing"
    fi
fi

if (( dry_run )); then
    echo "+ $python generate_inputs.py $config $work_dir/inputs"
    echo "+ $tleap -f inputs/tleap.solvate.in"
    echo "+ count waters and calculate salt formula units"
    echo "+ $tleap -f inputs/tleap.final.in"
    echo "+ $python configure_we.py $config $work_dir"
    echo "+ AMBER_ENGINE minimization, heating, and equilibration"
    exit 0
fi

for required in "$input" "$config"; do
    if [[ ! -s "$required" ]]; then
        die "Required input not found: $required"
    fi
done
for executable in "$tleap" "$python"; do
    if ! command -v "$executable" >/dev/null 2>&1; then
        die "Executable not found: $executable"
    fi
done

configured_engine=$("$python" - "$config" <<'PY'
import sys
sys.path.insert(0, "../../common")
from pathlib import Path
from config_utils import load_config
print(load_config(Path(sys.argv[1]))["run"]["engine"])
PY
)
engine=${AMBER_ENGINE:-$configured_engine}
cpptraj=${CPPTRAJ:-cpptraj}
for executable in "$engine" "$cpptraj"; do
    if ! command -v "$executable" >/dev/null 2>&1; then
        die "Executable not found: $executable"
    fi
done

if [[ -f "$work_dir/.system.complete" ]]; then
    for required in "$work_dir/system.parm7" "$work_dir/system.rst7" "$work_dir/common_files/system.parm7" "$work_dir/source_config.toml"; do
        if [[ ! -s "$required" ]]; then
            die "Completed topology build is missing an output: $required"
        fi
    done
    if ! cmp -s "$input" "$work_dir/input.pdb"; then
        die "The input PDB differs from the completed build. Use a new WORK_DIR."
    fi
    if ! cmp -s "$config" "$work_dir/source_config.toml"; then
        die "The config differs from the completed build. Use a new WORK_DIR."
    fi
    echo "Using the completed WE topology build: $work_dir"
else
    mkdir -p "$work_dir/inputs"
    cp "$input" "$work_dir/input.pdb"
    "$python" generate_inputs.py "$config" "$work_dir/inputs"

    echo "Solvating the basis system to determine the water count."
    if ! (cd "$work_dir"; "$tleap" -f inputs/tleap.solvate.in > leap.solvate.log 2>&1); then
        die "Initial tleap solvation failed: $work_dir/leap.solvate.log"
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
    salt_pairs=$(awk -v waters="$water_count" -v concentration="$salt_concentration" 'BEGIN {printf "%d", waters * concentration / 55.5 + 0.5}')
    "$python" generate_inputs.py "$config" "$work_dir/inputs" --salt-pairs "$salt_pairs"

    echo "Building the final basis system ($water_count waters, $salt_pairs salt formula units)."
    if ! (cd "$work_dir"; "$tleap" -f inputs/tleap.final.in > leap.log 2>&1); then
        die "Final tleap build failed: $work_dir/leap.log"
    fi
    for required in "$work_dir/system.parm7" "$work_dir/system.rst7" "$work_dir/system.pdb"; do
        if [[ ! -s "$required" ]]; then
            die "Topology build output was not created: $required"
        fi
    done
    "$python" configure_we.py "$config" "$work_dir"

    mkdir -p "$work_dir/common_files" "$work_dir/bstates"
    cp "$work_dir/system.parm7" "$work_dir/common_files/system.parm7"
    touch "$work_dir/.system.complete"
fi

mkdir -p "$work_dir/common_files" "$work_dir/bstates"

if [[ ! -f "$work_dir/.minimize.complete" ]]; then
    rm -f -- "$work_dir/minimize.out" "$work_dir/minimize.rst7"
    echo "Running: WE basis-state minimization"
    if ! (cd "$work_dir"; "$engine" -O -i inputs/minimize.in -o minimize.out \
        -p system.parm7 -c system.rst7 -r minimize.rst7); then
        die "Basis-state minimization failed: $work_dir/minimize.out"
    fi
    if [[ ! -s "$work_dir/minimize.out" || ! -s "$work_dir/minimize.rst7" ]]; then
        die "Basis-state minimization output is incomplete: $work_dir"
    fi
    touch "$work_dir/.minimize.complete"
elif [[ ! -s "$work_dir/minimize.rst7" ]]; then
    die "Completed minimization is missing its restart: $work_dir/minimize.rst7"
fi
cp "$work_dir/minimize.rst7" "$work_dir/common_files/reference.rst7"

if [[ ! -f "$work_dir/.heat.complete" ]]; then
    rm -f -- "$work_dir/heat.out" "$work_dir/heat.rst7" "$work_dir/heat.info" "$work_dir/heat.nc"
    echo "Running: WE basis-state heating"
    if ! (cd "$work_dir"; "$engine" -O -i inputs/heat.in -o heat.out \
        -p system.parm7 -c minimize.rst7 -r heat.rst7 -x heat.nc \
        -inf heat.info -ref minimize.rst7); then
        die "Basis-state heating failed: $work_dir/heat.out"
    fi
    for output in heat.out heat.rst7 heat.nc heat.info; do
        if [[ ! -s "$work_dir/$output" ]]; then
            die "Basis-state heating output is incomplete: $work_dir/$output"
        fi
    done
    touch "$work_dir/.heat.complete"
elif [[ ! -s "$work_dir/heat.rst7" || ! -s "$work_dir/heat.nc" ]]; then
    die "Completed heating is missing its restart or trajectory: $work_dir"
fi

if [[ ! -f "$work_dir/.equilibrate.complete" ]]; then
    rm -f -- "$work_dir/equilibrate.out" "$work_dir/equilibrate.info" "$work_dir/equilibrate.nc" "$work_dir/bstates/basis.rst7"
    echo "Running: WE basis-state equilibration"
    if ! (cd "$work_dir"; "$engine" -O -i inputs/equilibrate.in -o equilibrate.out \
        -p system.parm7 -c heat.rst7 -r bstates/basis.rst7 \
        -x equilibrate.nc -inf equilibrate.info); then
        die "Basis-state equilibration failed: $work_dir/equilibrate.out"
    fi
    for output in equilibrate.out equilibrate.nc equilibrate.info bstates/basis.rst7; do
        if [[ ! -s "$work_dir/$output" ]]; then
            die "Basis-state equilibration output is incomplete: $work_dir/$output"
        fi
    done
    touch "$work_dir/.equilibrate.complete"
elif [[ ! -s "$work_dir/bstates/basis.rst7" || ! -s "$work_dir/equilibrate.nc" ]]; then
    die "Completed equilibration is missing its restart or trajectory: $work_dir"
fi

for output in "$work_dir/common_files/system.parm7" "$work_dir/common_files/reference.rst7" "$work_dir/bstates/basis.rst7" "$work_dir/configs/west.001.cfg"; do
    if [[ ! -s "$output" ]]; then
        die "WE build output was not created: $output"
    fi
done

WORK_DIR="$work_dir" CPPTRAJ="$cpptraj" \
    ./westpa_scripts/calc_pcoord.sh "$work_dir/bstates/basis.rst7" > "$work_dir/basis_pcoord.txt"
touch "$work_dir/.basis.complete"
echo "WESTPA basis state and block configs: $work_dir"
