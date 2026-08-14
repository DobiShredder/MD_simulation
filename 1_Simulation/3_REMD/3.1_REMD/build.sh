#!/usr/bin/env bash
set -euo pipefail

dry_run=0
positional_arguments=()

while [[ $# -gt 0 ]]; do
    case "$1" in
        --dry-run)
            dry_run=1
            ;;
        -*)
            echo "Usage: $0 [--dry-run] INPUT.pdb [states.tsv]" >&2
            exit 2
            ;;
        *)
            positional_arguments+=("$1")
            ;;
    esac
    shift
done

if (( ${#positional_arguments[@]} < 1 || ${#positional_arguments[@]} > 2 )); then
    echo "Usage: $0 [--dry-run] INPUT.pdb [states.tsv]" >&2
    exit 2
fi

die() {
    echo "Error: $*" >&2
    exit 1
}

refuse_existing_results() {
    local directory=$1
    local existing_result=""
    if [[ -d "$directory" ]]; then
        existing_result=$(find "$directory" -type f \
            \( -name '.*.complete' -o -name 'min*.out' -o -name 'minimize.gro' \
               -o -name 'heat*.out' -o -name 'equil*.out' -o -name 'equilibrate.gro' \
               -o -name 'equilibrate.cpt' -o -name 'gamd_prepare.out' \
               -o -name 'production*.out' -o -name 'production*.gro' \
               -o -name 'production*.cpt' \) -print -quit)
    fi
    if [[ -n "$existing_result" ]]; then
        die "Existing simulation results were found: $existing_result. Use a new WORK_DIR or remove the previous calculation results before rebuilding."
    fi
}

validate_states() {
    local expected_header=$'replica\ttemperature_K\tseed'
    local actual_header

    IFS= read -r actual_header < "$states_file"
    if [[ "$actual_header" != "$expected_header" ]]; then
        die "Invalid state-table header: $expected_header"
    fi

    if ! awk -F '\t' '
        NR == 1 { next }
        NF != 3 { exit 1 }
        $1 !~ /^[0-9][0-9][0-9]$/ { exit 1 }
        $2 !~ /^[0-9]+([.][0-9]+)?$/ || $2 <= 0 { exit 1 }
        $3 !~ /^[0-9]+$/ || $3 <= 0 { exit 1 }
        seen[$1]++ { exit 1 }
        count == 0 && $1 != "000" { exit 1 }
        count > 0 && $2 <= previous_temperature { exit 1 }
        { previous_temperature = $2; count++ }
        END { if (count < 2) exit 1 }
    ' "$states_file"; then
        die "State table requires at least two unique replicas starting at 000, increasing positive temperatures, and positive integer seeds: $states_file"
    fi
}

input_pdb=${positional_arguments[0]}
states_file=${positional_arguments[1]:-"inputs/states.tsv"}
work_dir=${WORK_DIR:-"work"}
tleap=${TLEAP:-tleap}

refuse_existing_results "$work_dir"

if [[ ! -s "$input_pdb" ]]; then
    die "prepared PDB not found: $input_pdb"
fi

if [[ ! -s "$states_file" ]]; then
    die "replica table not found: $states_file"
fi

validate_states

if (( ! dry_run )); then
    if ! command -v "$tleap" >/dev/null 2>&1; then
        die "tleap not found: $tleap"
    fi
fi

replica_count=$(awk 'NR > 1 {count++} END {print count + 0}' "$states_file")
last_replica=$(awk 'END {print $1}' "$states_file")

if (( dry_run )); then
    echo "Generating ff19SB/TIP3P systems for $replica_count replicas."
    printf '%q -f %q\n' "$tleap" "inputs/tleap.in"
    echo "State table: $states_file"
    echo "Output directories: $work_dir/000 ... $last_replica"
    exit 0
fi

echo "Generating ff19SB/TIP3P systems for $replica_count replicas."
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

while IFS=$'\t' read -r replica temperature_kelvin seed; do
    if [[ "$replica" == "replica" ]]; then
        continue
    fi

    replica_dir="$work_dir/$replica"
    mkdir -p "$replica_dir"

    cp "$work_dir/system.parm7" "$replica_dir/system.parm7"
    cp "$work_dir/system.rst7" "$replica_dir/system.rst7"

    sed \
        -e "s/@TEMP@/$temperature_kelvin/g" \
        -e "s/@SEED@/$seed/g" \
        "inputs/heat.in" \
        > "$replica_dir/heat.in"

    sed \
        -e "s/@TEMP@/$temperature_kelvin/g" \
        -e "s/@SEED@/$seed/g" \
        "inputs/equilibrate.in" \
        > "$replica_dir/equilibrate.in"

    sed \
        -e "s/@TEMP@/$temperature_kelvin/g" \
        -e "s/@SEED@/$seed/g" \
        "inputs/production.in" \
        > "$replica_dir/production.in"

    cp "inputs/minimize.in" "$replica_dir/minimize.in"
done < "$states_file"

cp "$states_file" "$work_dir/states.tsv"
echo "Replica inputs and topologies: $work_dir"
