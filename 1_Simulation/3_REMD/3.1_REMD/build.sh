#!/usr/bin/env bash
set -euo pipefail

if [[ $# -ne 1 ]]; then
    echo "Usage: $0 INPUT.pdb" >&2
    exit 2
fi

die() {
    echo "Error: $*" >&2
    exit 1
}

input_pdb=$1
states_file=inputs/states.tsv
tleap=${TLEAP:-tleap}

if [[ ! -s "$input_pdb" ]]; then
    die "Prepared PDB not found: $input_pdb"
fi
if [[ ! -s "$states_file" ]]; then
    die "Replica table not found: $states_file"
fi
if ! command -v "$tleap" >/dev/null 2>&1; then
    die "tleap not found: $tleap"
fi
if find work -name 'production.out' -print -quit 2>/dev/null | grep -q .; then
    die "Production output already exists in work. Remove it before rebuilding."
fi

expected_header=$'replica\ttemperature_K\tseed'
IFS= read -r actual_header < "$states_file"
if [[ "$actual_header" != "$expected_header" ]]; then
    die "Invalid state-table header: $states_file"
fi
if ! awk -F '\t' '
    NR == 1 { next }
    NF != 3 { exit 1 }
    $1 !~ /^[0-9][0-9][0-9]$/ { exit 1 }
    $2 !~ /^[0-9]+([.][0-9]+)?$/ || $2 <= 0 { exit 1 }
    $3 !~ /^[0-9]+$/ || $3 <= 0 { exit 1 }
    seen[$1]++ { exit 1 }
    count == 0 && $1 != "000" { exit 1 }
    count > 0 && $2 <= previous { exit 1 }
    { previous = $2; count++ }
    END { if (count < 2) exit 1 }
' "$states_file"; then
    die "Invalid replica table: $states_file"
fi

replica_count=$(awk 'NR > 1 {count++} END {print count + 0}' "$states_file")
echo "Generating ff19SB/TIP3P systems for $replica_count replicas."

mkdir -p work
cp "$input_pdb" work/input.pdb
cp inputs/tleap.in work/tleap.in

if ! (
    cd work
    "$tleap" -f tleap.in > leap.log 2>&1
); then
    die "tleap failed. See log: work/leap.log"
fi
if [[ ! -s work/system.parm7 || ! -s work/system.rst7 ]]; then
    die "Topology or restart was not created. See log: work/leap.log"
fi

while IFS=$'\t' read -r replica temperature_kelvin seed; do
    if [[ "$replica" == replica ]]; then
        continue
    fi

    replica_dir="work/$replica"
    mkdir -p "$replica_dir"
    cp work/system.parm7 work/system.rst7 "$replica_dir/"
    cp inputs/minimize.in "$replica_dir/minimize.in"

    for stage in heat equilibrate production; do
        sed \
            -e "s/@TEMP@/$temperature_kelvin/g" \
            -e "s/@SEED@/$seed/g" \
            "inputs/$stage.in" \
            > "$replica_dir/$stage.in"
    done
done < "$states_file"

cp "$states_file" work/states.tsv
echo "Replica inputs and topologies: work"
