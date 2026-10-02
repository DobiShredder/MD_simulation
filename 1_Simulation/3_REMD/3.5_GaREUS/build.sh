#!/usr/bin/env bash
set -euo pipefail

original_args=("$@")

if [[ $# -ne 1 ]]; then
    echo "Usage: $0 INPUT.pdb" >&2
    exit 2
fi

die() {
    echo "Error: $*" >&2
    exit 1
}

input_pdb=$1
states_file="inputs/states.tsv"
work_dir=work

if (( ! ${dry_run:-0} )) &&
        [[ ${original_args[0]:-} != -h && ${original_args[0]:-} != --help && ${original_args[0]:-} != --dry-run ]] &&
        [[ ${MD_WRITER_PARENT:-} != "$PPID" || ${MD_WRITER_ENTRY:-} != "$0" ]]; then
    exec "${PYTHON:-python3}" helpers/writer_guard.py \
        --registry "work" --read "$1" --read "inputs" --write "work" -- "$0" "${original_args[@]}"
fi


# A rebuild must not mix new inputs with topology/restart files from an older build.
if [[ -d "$work_dir" ]]; then
    existing_build=$(find "$work_dir" -type f \
        \( -name '*.parm7' -o -name '*.rst7' \) -print -quit)
    if [[ -n "$existing_build" ]]; then
        die "Build output already exists and was retained: $existing_build. Use a new work directory for a new build."
    fi
fi

tleap=${TLEAP:-tleap}
python_bin=${PYTHON:-python3}

if find "$work_dir" -type f -name 'production.out' -print -quit 2>/dev/null | grep -q .; then
    die "Production output already exists in $work_dir. Remove it before rebuilding."
fi

for input_file in "$input_pdb" "$states_file"; do
    if [[ ! -s "$input_file" ]]; then
        die "Required input not found: $input_file"
    fi
done

if ! command -v "$tleap" >/dev/null 2>&1; then
    die "tleap not found: $tleap"
fi
if ! "$python_bin" -c "import parmed" >/dev/null 2>&1; then
    die "ParmEd is required: $python_bin -m pip install parmed"
fi

window_count=$(awk 'NR > 1 {count++} END {print count + 0}' "$states_file")
if [[ "$window_count" -ne 20 ]]; then
    die "states.tsv must contain 20 windows: $window_count"
fi

echo "Generating ff19SB/OPC systems for 20 GaREUS windows."
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

echo "Generating window restraints: $work_dir/system.parm7; states: $states_file"
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
    if [[ ! -s "$replica_dir/distance.RST" ]]; then
        die "Window restraint generation did not create: $replica_dir/distance.RST"
    fi
    cp "$work_dir/system.parm7" "$replica_dir/system.parm7"
    cp "$work_dir/system.rst7" "$replica_dir/system.rst7"

    for stage in minimize heat equilibrate gamd_prepare; do
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
echo "GaREUS topologies, restraints, and inputs: $work_dir"
