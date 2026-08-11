#!/usr/bin/env bash
set -euo pipefail

dry_run=0
if [[ "${1:-}" == "--dry-run" ]]; then
    dry_run=1
    shift
fi

if [[ $# -ne 0 ]]; then
    echo "Usage: $0 [--dry-run]" >&2
    exit 2
fi

die() {
    echo "Error: $*" >&2
    exit 1
}

input_pdb="structure/chignolin.pdb"
states_file="inputs/states.tsv"
work_dir=${WORK_DIR:-"work"}
tleap=${TLEAP:-tleap}
python_bin=${PYTHON:-python3}

for input_file in "$input_pdb" "$states_file"; do
    if [[ ! -s "$input_file" ]]; then
        die "Required input not found: $input_file"
    fi
done

if (( ! dry_run )); then
    if ! command -v "$tleap" >/dev/null 2>&1; then
        die "tleap not found: $tleap"
    fi
    if ! "$python_bin" -c "import parmed" >/dev/null 2>&1; then
        die "ParmEd is required: $python_bin -m pip install parmed"
    fi
fi

window_count=$(awk 'NR > 1 {count++} END {print count + 0}' "$states_file")
if [[ "$window_count" -ne 19 ]]; then
    die "states.tsv must contain 19 windows: $window_count"
fi

if (( dry_run )); then
    echo "Generating ff19SB/TIP3P systems for 19 REUS windows."
    echo "CV: :1@CA–:10@CA, 6–24 Å, 1 Å spacing"
    echo "Output directories: $work_dir/000 ... 018"
    exit 0
fi

echo "Generating ff19SB/TIP3P systems for 19 REUS windows."
mkdir -p "$work_dir"
cp "$input_pdb" "$work_dir/input.pdb"
cp inputs/tleap.in "$work_dir/tleap.in"

if ! (
    cd "$work_dir"
    "$tleap" \
        -f tleap.in \
        > leap.log 2>&1
); then
    die "tleap failed. See log: $work_dir/leap.log"
fi

for output in system.parm7 system.rst7; do
    if [[ ! -s "$work_dir/$output" ]]; then
        die "AMBER build Output not found: $work_dir/$output"
    fi
done

"$python_bin" "make_restraints.py" \
    "$work_dir/system.parm7" \
    "$work_dir/system.rst7" \
    "$states_file" \
    "$work_dir"

while IFS=$'\t' read -r replica _ seed; do
    if [[ "$replica" == "replica" ]]; then
        continue
    fi

    replica_dir="$work_dir/$replica"
    cp "$work_dir/system.parm7" "$replica_dir/system.parm7"
    cp "$work_dir/system.rst7" "$replica_dir/system.rst7"

    for stage in minimize heat equilibrate; do
        sed \
            -e "s|@SEED@|$seed|g" \
            -e "s|@DISANG@|distance.RST|g" \
            -e "s|@DUMPAVE@|restraint.$stage.dat|g" \
            "inputs/$stage.in" \
            > "$replica_dir/$stage.in"
    done

    sed \
        -e "s|@SEED@|$seed|g" \
        -e "s|@DISANG@|$replica_dir/distance.RST|g" \
        "inputs/production.in" \
        > "$replica_dir/production.template.in"
done < "$states_file"

cp "$states_file" "$work_dir/states.tsv"
echo "REUS topologies, restraints, and inputs: $work_dir"
