#!/usr/bin/env bash
set -euo pipefail

original_args=("$@")

dry_run=0
config=config.toml

show_help() {
    cat <<'EOF'
Usage: ./build.sh [--config FILE] [--dry-run] COMPLEX.pdb

Build an protein/GAFF2 explicit-solvent AMBER system from a reviewed complex PDB
and the ligand MOL2/frcmod paths in config.toml.

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
if (( ! ${dry_run:-0} )) && [[ ${MD_WRITER_PARENT:-} != "$PPID" || ${MD_WRITER_ENTRY:-} != "$0" ]]; then
    exec "${PYTHON:-python3}" helpers/writer_guard.py \
        --registry "$work_dir" --read "$input" --read "$config" \
        --write "$work_dir" -- "$0" "${original_args[@]}"
fi
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
    printf '+ %q helpers/generate_inputs.py %q %q\n' "$python" "$config" "$work_dir/inputs"
    echo "+ first-pass tleap in $work_dir/.build_tmp.XXXXXX"
    echo "+ $python helpers/count_waters.py $work_dir/.build_tmp.XXXXXX/solvated.pdb"
    echo '+ python3 helpers/generate_inputs.py config.toml work/inputs --salt-pairs N'
    printf '+ %q -f %q\n' "$tleap" "$work_dir/inputs/tleap.final.in"
    exit 0
fi

mkdir -p "$work_dir/inputs"
cp "$input" "$work_dir/input.pdb"
"$python" helpers/generate_inputs.py "$config" "$work_dir/inputs"
build_tmp=$(mktemp -d "$work_dir/.build_tmp.XXXXXX")
cp "$work_dir/input.pdb" "$build_tmp/input.pdb"
mv "$work_dir/inputs/tleap.solvate.in" "$build_tmp/tleap.solvate.in"
# Both LEaP passes read the same generated ligand parameters.
mkdir -p "$build_tmp/inputs"
cp "$work_dir/inputs/ligand.mol2" "$work_dir/inputs/ligand.frcmod" "$build_tmp/inputs/"

echo "Solvating the input structure to determine the water count."
if ! (
    cd "$build_tmp"
    "$tleap" -f tleap.solvate.in > leap.solvate.log 2>&1
); then
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
salt_pairs=$(awk -v waters="$water_count" -v concentration="$salt_concentration" \
    'BEGIN { printf "%d", waters * concentration / 55.5 + 0.5 }')

"$python" helpers/generate_inputs.py "$config" "$work_dir/inputs" --salt-pairs "$salt_pairs"
for parameter in ligand.mol2 ligand.frcmod; do
    if ! cmp -s "$build_tmp/inputs/$parameter" "$work_dir/inputs/$parameter"; then
        die "Final build: ligand parameter changed between LEaP passes: $parameter. Files were preserved; see $build_tmp/leap.solvate.log"
    fi
done

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

remove_build_tmp

echo "Protein-ligand topology and restart: $work_dir/system.parm7, $work_dir/system.rst7"
