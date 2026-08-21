#!/usr/bin/env bash
set -euo pipefail

show_help() {
    cat <<'EOF'
Usage: bash ../build_fep.sh METHOD [--config FILE] [--dry-run] INPUT.pdb

Build config-driven RBFE or ABFE complex/solvent systems and alchemical windows.
METHOD must be rbfe or abfe.

Options:
  --config FILE  Read settings from FILE instead of config.toml.
  --dry-run      Print the planned two-pass tleap build.
  -h, --help     Show this help message and exit.
EOF
}

if [[ "${1:-}" == -h || "${1:-}" == --help ]]; then
    show_help
    exit 0
fi
if [[ $# -lt 1 || ! "$1" =~ ^(rbfe|abfe)$ ]]; then
    show_help >&2
    exit 2
fi
method=$1
shift
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

if [[ -d "$work_dir" ]]; then
    existing=$(find "$work_dir" -type f \( -name '.*.complete' -o -name '*.out' \) -print -quit)
    if [[ -n "$existing" ]]; then
        die "Existing simulation results were found: $existing"
    fi
fi

if (( dry_run )); then
    echo "+ $python ../prepare_fep_systems.py $method $config $input $build_dir"
    echo "+ $tleap -f tleap.complex.solvate.in"
    echo "+ $tleap -f tleap.solvent.solvate.in"
    echo "+ count waters and calculate salt formula units"
    echo "+ $tleap -f tleap.complex.final.in"
    echo "+ $tleap -f tleap.solvent.final.in"
    echo "+ $python generate_inputs.py $config $work_dir inputs"
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
"$python" ../prepare_fep_systems.py "$method" "$config" "$input" "$build_dir"

for environment in complex solvent; do
    echo "Solvating the $environment system to determine its water count."
    if ! (cd "$build_dir"; "$tleap" -f "tleap.$environment.solvate.in" > "tleap.$environment.solvate.log" 2>&1); then
        die "$environment solvation failed: $build_dir/tleap.$environment.solvate.log"
    fi
done

complex_waters=$("$python" ../../common/count_waters.py "$build_dir/complex.solvated.pdb")
solvent_waters=$("$python" ../../common/count_waters.py "$build_dir/solvent.solvated.pdb")
salt_concentration=$("$python" - "$config" <<'PY'
import sys
sys.path.insert(0, "../../common")
from pathlib import Path
from config_utils import load_config
print(load_config(Path(sys.argv[1]))["build"]["salt_concentration_molar"])
PY
)
complex_pairs=$(awk -v waters="$complex_waters" -v concentration="$salt_concentration" 'BEGIN {printf "%d", waters * concentration / 55.5 + 0.5}')
solvent_pairs=$(awk -v waters="$solvent_waters" -v concentration="$salt_concentration" 'BEGIN {printf "%d", waters * concentration / 55.5 + 0.5}')

"$python" ../prepare_fep_systems.py "$method" "$config" "$input" "$build_dir" \
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

"$python" generate_inputs.py "$config" "$work_dir" inputs
echo "FEP systems and windows: $work_dir"
