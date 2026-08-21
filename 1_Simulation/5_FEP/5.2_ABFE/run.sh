#!/usr/bin/env bash
set -euo pipefail

dry_run=0
if [[ "${1:-}" == "--dry-run" && $# -eq 1 ]]; then
    dry_run=1
elif [[ $# -ne 0 ]]; then
    echo "Usage: $0 [--dry-run]" >&2
    exit 2
fi

die() {
    echo "Error: $*" >&2
    exit 1
}

work_dir=work
states_file="$work_dir/states.tsv"
engine=${AMBER_ENGINE:-pmemd.cuda}

if [[ ! -s "$states_file" ]]; then
    die "Run build.sh first: $states_file"
fi
if (( ! dry_run )) && ! command -v "$engine" >/dev/null 2>&1; then
    die "AMBER engine not found: $engine"
fi
if (( ! dry_run )) && [[ "$(basename "$engine")" != "pmemd.cuda" ]]; then
    die "ACES26 soft-core inputs must run with pmemd.cuda: $engine"
fi

if (( ! dry_run )); then
    production_output=$(find "$work_dir" -type f \
        \( -name 'production.out' -o -name 'production.rst7' \
           -o -name 'production.info' -o -name 'production.nc' \) \
        -print -quit)
    if [[ -n "$production_output" ]]; then
        die "Production output already exists: $production_output"
    fi
fi

run_stage() {
    local directory=$1
    local stage=$2
    local input_restart=$3
    local trajectory=$4
    local calculation=$5

    local output_file="$directory/$stage.out"
    local restart_file="$directory/$stage.rst7"
    local command=(
        "$engine" -O
        -i "$stage.in"
        -o "$stage.out"
        -p system.parm7
        -c "$input_restart"
        -r "$stage.rst7"
        -inf "$stage.info"
    )
    if [[ "$trajectory" == yes ]]; then
        command+=(-x "$stage.nc")
    fi

    if (( dry_run )); then
        printf '+ (cd %q && ' "$directory"
        printf '%q ' "${command[@]}"
        printf ')\n'
        return
    fi

    if [[ -s "$output_file" && -s "$restart_file" ]]; then
        echo "Skipping: $calculation - $stage outputs already exist."
        return
    fi
    if [[ -e "$output_file" || -e "$restart_file" ]]; then
        echo "Warning: incomplete $stage outputs found; rerunning $calculation." >&2
    fi

    echo "Running: $calculation - $stage"
    if ! (
        cd "$directory"
        "${command[@]}"
    ); then
        die "$stage calculation failed: $output_file"
    fi
    if [[ ! -s "$output_file" || ! -s "$restart_file" ]]; then
        die "$stage outputs were not created: $directory"
    fi
}

while IFS=$'\t' read -r method_stage environment window lambda seed directory; do
    if [[ "$method_stage" == stage ]]; then
        continue
    fi
    interaction=${method_stage##*_}
    calculation="ABFE $interaction/$environment window $window (lambda=$lambda)"
    run_stage "$directory" minimize system.rst7 no "$calculation"
    run_stage "$directory" heat minimize.rst7 yes "$calculation"
    run_stage "$directory" equilibrate heat.rst7 yes "$calculation"
    run_stage "$directory" production equilibrate.rst7 yes "$calculation"
done < "$states_file"

echo "ABFE production completed: work/restraint, work/charge, work/vdw"
