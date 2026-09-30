#!/usr/bin/env bash
set -euo pipefail

show_help() {
    cat <<'EOF'
Usage: ./build.sh [--config FILE] [--dry-run] PROTEIN.pdb

Build RBFE complex/solvent systems from a reviewed protein PDB and the
precharged ligand A/B parameters configured in config.toml.

Options:
  --config FILE  Read settings from FILE instead of config.toml.
  --dry-run      Print the planned build without running external programs.
  -h, --help     Show this help message and exit.
EOF
}

if [[ "${1:-}" == -h || "${1:-}" == --help ]]; then
    show_help
    exit 0
fi

config=config.toml
dry_run=0
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
build_dir="$work_dir/build"
tleap=${TLEAP:-tleap}
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

# A rebuild must not mix new inputs with topology/restart files from an older build.
if (( ! dry_run )) && [[ -d "$work_dir" ]]; then
    existing_build=$(find "$work_dir" -type f \
        \( -name '*.parm7' -o -name '*.rst7' \) -print -quit)
    if [[ -n "$existing_build" ]]; then
        die "Build output already exists and was retained: $existing_build. Use a new work directory for a new build."
    fi
fi

if [[ -d "$work_dir" ]]; then
    existing=$(find "$work_dir" -type f \( -name '.*.complete' -o -name '*.out' \) -print -quit)
    if [[ -n "$existing" ]]; then
        die "Existing simulation results were found: $existing"
    fi
fi

if (( dry_run )); then
    echo "+ $python helpers/prepare_fep_systems.py $config $input $build_dir"
    echo "+ $tleap -f tleap.complex.solvate.in"
    echo "+ $tleap -f tleap.solvent.solvate.in"
    echo "+ count waters and calculate salt formula units"
    echo "+ $tleap -f tleap.complex.final.in"
    echo "+ $tleap -f tleap.solvent.final.in"
    echo "+ $python helpers/generate_inputs.py $config $work_dir inputs"
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
if ! "$python" -c 'import parmed' >/dev/null 2>&1; then
    die "ParmEd is required in the selected Python environment."
fi

mkdir -p "$build_dir"
build_tmp=$(mktemp -d "$work_dir/.build_tmp.XXXXXX")
echo "Preparing FEP systems: $config, $input -> $build_tmp"
"$python" helpers/prepare_fep_systems.py "$config" "$input" "$build_tmp"

for environment in complex solvent; do
    echo "Solvating the $environment system to determine its water count."
    if ! (cd "$build_tmp"; "$tleap" -f "tleap.$environment.solvate.in" > "tleap.$environment.solvate.log" 2>&1); then
        die "$environment solvation failed: $build_tmp/tleap.$environment.solvate.log"
    fi
done

cp "$build_tmp/tleap.complex.solvate.log" "$build_dir/tleap.complex.solvate.log"
cp "$build_tmp/tleap.solvent.solvate.log" "$build_dir/tleap.solvent.solvate.log"
complex_waters=$("$python" helpers/count_waters.py "$build_tmp/complex.solvated.pdb")
solvent_waters=$("$python" helpers/count_waters.py "$build_tmp/solvent.solvated.pdb")
salt_concentration=$("$python" - "$config" <<'PY'
import sys
sys.path.insert(0, "helpers")
from pathlib import Path
from config_utils import load_config
print(load_config(Path(sys.argv[1]))["build"]["salt_concentration_molar"])
PY
)
complex_pairs=$(awk -v waters="$complex_waters" -v concentration="$salt_concentration" 'BEGIN {printf "%d", waters * concentration / 55.5 + 0.5}')
solvent_pairs=$(awk -v waters="$solvent_waters" -v concentration="$salt_concentration" 'BEGIN {printf "%d", waters * concentration / 55.5 + 0.5}')

"$python" helpers/prepare_fep_systems.py "$config" "$input" "$build_dir" \
    --complex-salt-pairs "$complex_pairs" \
    --solvent-salt-pairs "$solvent_pairs"

for environment in complex solvent; do
    echo "Building the final $environment system."
    if ! (cd "$build_dir"; "$tleap" -f "tleap.$environment.final.in" > "tleap.$environment.log" 2>&1); then
        die "$environment topology build failed: $build_dir/tleap.$environment.log"
    fi
    for suffix in parm7 rst7; do
        if [[ ! -s "$build_dir/$environment.$suffix" ]]; then
            die "Build output was not created: $build_dir/$environment.$suffix"
        fi
    done
done

echo "Generating FEP window inputs: $config -> $work_dir"
"$python" helpers/generate_inputs.py "$config" "$work_dir" inputs
remove_build_tmp

echo "FEP systems and windows: $work_dir"
