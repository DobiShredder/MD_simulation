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

refuse_existing_results() {
    local directory=$1
    local existing_result=""
    if [[ -d "$directory" ]]; then
        existing_result=$(find "$directory" -type f \
            \( -name '.*.complete' -o -name 'min.out' -o -name 'heat.out' \
               -o -name 'equil.out' -o -name 'production.out' \) -print -quit)
    fi
    if [[ -n "$existing_result" ]]; then
        die "Existing simulation results were found: $existing_result. Use a new WORK_DIR or remove the previous calculation results before rebuilding windows."
    fi
}

# User settings and input/output paths
window_file=${WINDOW_FILE:-"windows.tsv"}
seed_dir=${SEED_DIR:-"../rmd/work/seeds"}
seed_metadata="$seed_dir/seeds.tsv"
topology=${TOPOLOGY:-"../work/system.parm7"}
work_dir=${WORK_DIR:-"work"}

refuse_existing_results "$work_dir"
window_root="$work_dir"

# Read window settings
if [[ ! -s "$window_file" ]]; then
    die "window settings not found: $window_file"
fi

window_rows=()
previous_center=""

while read -r center_angstrom force_kcal_mol_angstrom2 extra_field; do
    if [[ -z "${center_angstrom:-}" ]]; then
        continue
    fi

    if [[ "$center_angstrom" == \#* ]]; then
        continue
    fi

    if [[ -n "${extra_field:-}" ]]; then
        die "${window_file} must contain exactly two columns: CENTER_A and FORCE."
    fi

    if [[ ! "$center_angstrom" =~ ^[0-9]+([.][0-9]+)?$ ]]; then
        die "Window center must be numeric: $center_angstrom"
    fi

    if [[ ! "$force_kcal_mol_angstrom2" =~ ^[0-9]+([.][0-9]+)?$ ]]; then
        die "Window force constant must be numeric: $force_kcal_mol_angstrom2"
    fi

    if ! awk \
        -v center="$center_angstrom" \
        -v force="$force_kcal_mol_angstrom2" \
        'BEGIN { exit !(center > 0 && force > 0) }'; then
        die "Window center and force constant must be positive:" \
            "$center_angstrom $force_kcal_mol_angstrom2"
    fi

    if [[ -n "$previous_center" ]]; then
        if ! awk \
            -v previous="$previous_center" \
            -v center="$center_angstrom" \
            'BEGIN { exit !(center > previous) }'; then
            die "Window centers must be unique and increasing: $previous_center -> $center_angstrom"
        fi
    fi

    window_rows+=("$center_angstrom $force_kcal_mol_angstrom2")
    previous_center=$center_angstrom
done < "$window_file"

if (( ${#window_rows[@]} == 0 )); then
    die "No windows found in ${window_file}."
fi

# Check seeds and the shared topology
if (( ! dry_run )); then
    if [[ ! -s "$topology" ]]; then
        die "shared topology not found: $topology"
    fi

    if [[ ! -s "$seed_metadata" ]]; then
        die "seed metadata not found: $seed_metadata"
    fi

    if [[ -e "$window_root" ]]; then
        die "Window output already exists: $window_root"
    fi

    for row_index in "${!window_rows[@]}"; do
        window_number=$((row_index + 1))
        printf -v window_id '%03d' "$window_number"

        metadata_line_number=$((row_index + 2))
        metadata_row=$(awk \
            -v line="$metadata_line_number" \
            'NR == line { print $1, $2, $3 }' \
            "$seed_metadata")

        if [[ -z "$metadata_row" ]]; then
            die "$window_id is missing from ${seed_metadata}."
        fi

        read -r metadata_window metadata_center _ <<< "$metadata_row"

        if [[ "$metadata_window" != "$window_number" ]]; then
            die "Window order in ${seed_metadata} differs from windows.tsv: $window_id"
        fi

        read -r configured_center _ <<< "${window_rows[$row_index]}"

        if ! awk \
            -v configured="$configured_center" \
            -v observed="$metadata_center" \
            'BEGIN {
                difference = configured - observed
                if (difference < 0) difference = -difference
                exit !(difference < 1e-6)
            }'; then
            die "$window_id center differs from seed metadata: $configured_center vs $metadata_center"
        fi

        seed_restart="$seed_dir/seed_${window_id}.rst7"

        if [[ ! -s "$seed_restart" ]]; then
            die "seed restart not found: $seed_restart"
        fi
    done
fi

# Dry run reports the number of files and output paths without creating them.
if (( dry_run )); then
    echo "shared topology: $topology"
    echo "Seed directory: $seed_dir"
    echo "Umbrella windows to create: ${#window_rows[@]} ($window_root)"
    exit 0
fi

# Generate topology, seed, restraint, and metadata for each window.
mkdir -p "$window_root"

for row_index in "${!window_rows[@]}"; do
    read -r center_angstrom force_kcal_mol_angstrom2 <<< "${window_rows[$row_index]}"

    window_number=$((row_index + 1))
    printf -v window_id '%03d' "$window_number"
    window_dir="$window_root/$window_id"

    mkdir -p "$window_dir"
    cp "$topology" "$window_dir/system.parm7"
    cp "$seed_dir/seed_${window_id}.rst7" "$window_dir/seed.rst7"

    sed \
        -e "s/CENTER/$center_angstrom/g" \
        -e "s/FORCE/$force_kcal_mol_angstrom2/g" \
        "inputs/restraint.RST.template" \
        > "$window_dir/restraint.RST"

    printf 'window\tcenter_A\tforce_kcal_mol_A2\n%s\t%s\t%s\n' \
        "$window_id" \
        "$center_angstrom" \
        "$force_kcal_mol_angstrom2" \
        > "$window_dir/window.tsv"
done

echo "Created ${#window_rows[@]} umbrella windows using the same topology:" \
    "$window_root"
