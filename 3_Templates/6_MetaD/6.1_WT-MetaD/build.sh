#!/usr/bin/env bash
set -euo pipefail

original_args=("$@")

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
if (( ! ${dry_run:-0} )) && [[ ${MD_WRITER_PARENT:-} != "$PPID" || ${MD_WRITER_ENTRY:-} != "$0" ]]; then
    exec "${PYTHON:-python3}" helpers/writer_guard.py \
        --registry "$work_dir" --read "$input" --read "$config" \
        --write "$work_dir" -- "$0" "${original_args[@]}"
fi
python=${PYTHON:-python3}

# Unknown config keys are usually typos; warn before any expensive step.
"$python" helpers/check_config_keys.py "$config" helpers/config_keys.txt
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

# A rebuild must not mix new inputs with topology/restart files from an older build.
if (( ! dry_run )) && [[ -d "$work_dir" ]]; then
    existing_build=$(find "$work_dir" -type f \
        \( -name '*.parm7' -o -name '*.rst7' \) -print -quit)
    if [[ -n "$existing_build" ]]; then
        die "Build output already exists and was retained: $existing_build. For a new build, set WORK_DIR to a new directory or move the old build aside (for example: mv $work_dir $work_dir.previous)."
    fi
fi

if [[ -d "$work_dir" ]]; then
    existing=$(find "$work_dir" -type f \( -name '.*.complete' -o -name 'production.out' -o -name 'HILLS' -o -name 'KERNELS' -o -name 'DELTAFS' \) -print -quit)
    if [[ -n "$existing" ]]; then
        die "Existing simulation result was found: $existing"
    fi
fi

if (( dry_run )); then
    echo "+ write $work_dir/cv.dat from [collective_variable] definitions"
    echo "+ $python helpers/generate_inputs.py $config $work_dir/inputs"
    echo "+ first-pass tleap in $work_dir/.build_tmp.XXXXXX"
    echo "+ count waters and calculate salt formula units"
    echo "+ $tleap -f inputs/tleap.final.in"
    echo "+ record topology atom count"
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

# build.sh reads the final topology with parmed after tleap.
if ! "$python" -c "import parmed" >/dev/null 2>&1; then
    die "Python package parmed is required for the MetaD build (see requirements.txt): $python"
fi

mkdir -p "$work_dir/inputs"
cp "$input" "$work_dir/input.pdb"
cp "$config" "$work_dir/source_config.toml"

# run.sh and helpers/generate_plumed.py read the PLUMED CV actions from work/cv.dat.
"$python" - "$config" "$work_dir/cv.dat" <<'PY'
import sys
sys.path.insert(0, "helpers")
from pathlib import Path
from config_utils import load_config, section

config_path, cv_path = sys.argv[1], Path(sys.argv[2])
try:
    cv = section(load_config(Path(config_path)), "collective_variable")
except ValueError as error:
    raise SystemExit(f"Config error in build CV setup ({config_path}): {error}") from None
definitions = cv.get("definitions")
if not isinstance(definitions, str) or not definitions.strip():
    raise SystemExit(
        f"Config error in build CV setup ({config_path}): "
        "[collective_variable] definitions must contain the PLUMED CV actions"
    )
cv_path.write_text(definitions.strip() + "\n", encoding="utf-8")
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
from config_utils import load_config, nonnegative_float, section

try:
    build = section(load_config(Path(sys.argv[1])), "build")
    # load_config converts the public salt_concentration (mM) to molar.
    print(nonnegative_float(build, "salt_concentration_molar"))
except ValueError as error:
    raise SystemExit(f"Config error in build salt setup ({sys.argv[1]}): {error}") from None
PY
)
salt_pairs=$(awk -v waters="$water_count" -v concentration="$salt_concentration" 'BEGIN {printf "%d", waters * concentration / 55.5 + 0.5}')
"$python" helpers/generate_inputs.py "$config" "$work_dir/inputs" --salt-pairs "$salt_pairs"

echo "Building the final MetaD system ($water_count waters, $salt_pairs salt formula units)."
if ! (cd "$work_dir"; "$tleap" -f inputs/tleap.final.in > tleap.stdout.log 2>&1); then
    die "Final tleap build failed. See $work_dir/tleap.stdout.log and $work_dir/leap.log"
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

remove_build_tmp

echo "MetaD topology and generated inputs: $work_dir"
