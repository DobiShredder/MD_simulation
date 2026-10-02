#!/usr/bin/env bash
set -euo pipefail

original_args=("$@")

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

if (( ! ${dry_run:-0} )) &&
        [[ ${original_args[0]:-} != -h && ${original_args[0]:-} != --help && ${original_args[0]:-} != --dry-run ]] &&
        [[ ${MD_WRITER_PARENT:-} != "$PPID" || ${MD_WRITER_ENTRY:-} != "$0" ]]; then
    exec "${PYTHON:-python3}" helpers/writer_guard.py \
        --registry "work" --read "inputs" --write "work" -- "$0" "${original_args[@]}"
fi

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
    "${PYTHON:-python3}" helpers/input_identity.py --verify "$work_dir"
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

    local identity_options=()
    if [[ -s "$directory/disang.rest" ]]; then
        identity_options+=(--input "$directory/disang.rest")
    fi
    "${PYTHON:-python3}" helpers/input_identity.py \
        --record "$directory/.$stage.identity.json" --stage "$calculation - $stage" \
        --directory "$directory" "${identity_options[@]}" -- "${command[@]}"

    if [[ -s "$output_file" && -s "$restart_file" ]]; then
        reused_stage_count=$((reused_stage_count + 1))
        return
    fi
    if [[ -e "$output_file" || -e "$restart_file" ]]; then
        echo "Warning: incomplete $stage outputs found; rerunning $calculation." >&2
    fi

    if ! (
        cd "$directory"
        "${command[@]}"
    ); then
        die "$stage calculation failed: $output_file"
    fi
    local output
    for output in "$output_file" "$restart_file"; do
        if [[ ! -s "$output" ]]; then
            die "$calculation - $stage output was not created: $output"
        fi
    done
    if [[ "$trajectory" == yes && ! -s "$directory/$stage.nc" ]]; then
        die "$calculation - $stage trajectory was not created: $directory/$stage.nc"
    fi
}

if (( dry_run )); then
    echo "Dry run: planned FEP commands; no engine execution"
fi

reused_stage_count=0
if (( ! dry_run )); then
    echo "Running: ABFE window workflows (minimization, heating, equilibration, production): work"
fi

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

if (( ! dry_run )); then
    if (( reused_stage_count > 0 )); then
        echo "Reused completed stages: $reused_stage_count (work)"
    fi
    echo "ABFE production completed: work/restraint, work/charge, work/vdw"
fi
