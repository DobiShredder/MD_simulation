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

run_stage() {
    local label=$1
    local output=$2
    local restart=$3
    shift 3

    if (( dry_run )); then
        printf '+ '
        printf '%q ' "$@"
        printf '\n'
        return
    fi

    local identity_options=()
    if [[ "$output" == ratchet.out ]]; then
        identity_options+=(--input plumed.dat)
    fi
    "${PYTHON:-python3}" ../helpers/input_identity.py \
        --record ".$output.identity.json" --stage "$label" "${identity_options[@]}" -- "$@"

    local completion_state
    completion_state=$("${PYTHON:-python3}" ../helpers/input_identity.py \
        --check-completion ".$output.identity.json")
    if [[ "$completion_state" == complete ]]; then
        echo "Skipping completed stage: $label"
        return
    fi

    echo "Running: $label"
    if ! "$@"; then
        die "$label failed. Expected output (if created): work/$output"
    fi
    local required_output
    for required_output in "$output" "$restart"; do
        if [[ ! -s "$required_output" ]]; then
            die "$label output was not created: work/$required_output"
        fi
    done
    "${PYTHON:-python3}" ../helpers/input_identity.py \
        --finish-completion ".$output.identity.json"
    echo "Completed: $label (work/$output)"
}

if (( dry_run )); then
    echo "Dry run: planned sampling commands; no engine execution"
fi

if (( ! ${dry_run:-0} )) &&
        [[ ${original_args[0]:-} != -h && ${original_args[0]:-} != --help && ${original_args[0]:-} != --dry-run ]] &&
        [[ ${MD_WRITER_PARENT:-} != "$PPID" || ${MD_WRITER_ENTRY:-} != "$0" ]]; then
    exec "${PYTHON:-python3}" helpers/writer_guard.py \
        --registry "../work" --read "inputs" --read "../work" --write "work" -- "$0" "${original_args[@]}"
fi

engine=${AMBER_ENGINE:-pmemd.cuda}
topology=../work/system.parm7
coordinates=../work/system.rst7

if (( ! dry_run )) && ! command -v "$engine" >/dev/null 2>&1; then
    die "AMBER engine not found: $engine"
fi
if [[ ! -s "$topology" || ! -s "$coordinates" ]]; then
    die "Run ../prepare.sh first."
fi
if (( ! dry_run )) && [[ -e work/ratchet.out ]]; then
    die "Ratchet MD output already exists: work/ratchet.out"
fi

if (( ! dry_run )); then
    "${PYTHON:-python3}" helpers/input_identity.py --verify work
    source_options=()
    for source_input in inputs/*.in; do
        source_options+=(--input "$source_input")
    done
    source_options+=(--input inputs/plumed.dat --input "$topology" --input "$coordinates")
    "${PYTHON:-python3}" helpers/input_identity.py \
        --record work/.source.identity.json --stage "run source inputs" \
        "${source_options[@]}" --value="$engine"
    mkdir -p work/inputs
    cp "$topology" work/system.parm7
    cp "$coordinates" work/system.rst7
    cp inputs/*.in work/inputs/
    cp inputs/plumed.dat work/plumed.dat
fi
if (( dry_run )); then
    echo "Planned working directory: work"
else
    cd work
fi

run_stage "solvent minimization" min-solvent.out min-solvent.rst7 \
    "$engine" -O -i inputs/min-solvent.in -o min-solvent.out \
    -p system.parm7 -c system.rst7 -r min-solvent.rst7 -ref system.rst7

run_stage "whole-system minimization" min-all.out min-all.rst7 \
    "$engine" -O -i inputs/min-all.in -o min-all.out \
    -p system.parm7 -c min-solvent.rst7 -r min-all.rst7

run_stage "NVT heating" heat.out heat.rst7 \
    "$engine" -O -i inputs/heat.in -o heat.out \
    -p system.parm7 -c min-all.rst7 -r heat.rst7 -x heat.nc \
    -inf heat.info -ref min-all.rst7

run_stage "NPT equilibration" equil.out equil.rst7 \
    "$engine" -O -i inputs/equil.in -o equil.out \
    -p system.parm7 -c heat.rst7 -r equil.rst7 -x equil.nc \
    -inf equil.info -ref heat.rst7

if (( ! dry_run )); then
    final_density=$(awk '
    /A V E R A G E S/ { exit }
    /Density/ { density = $3 }
    END { print density }
' equil.out)
    if [[ -z "$final_density" ]] || ! awk \
        -v density="$final_density" \
        'BEGIN { exit !(density >= 0.90 && density <= 1.10) }'; then
        die "NPT density is outside 0.90-1.10 g/cm^3: ${final_density:-missing}"
    fi
    echo "NPT final density: ${final_density} g/cm^3"
fi

run_stage "1 ns ratchet MD" ratchet.out ratchet.rst7 \
    "$engine" -O -i inputs/ratchet.in -o ratchet.out \
    -p system.parm7 -c equil.rst7 -r ratchet.rst7 \
    -x ratchet.nc -inf ratchet.info

if (( ! dry_run )); then
    if [[ ! -s ratchet.nc ]]; then
        die "Ratchet MD trajectory was not created: work/ratchet.nc"
    fi
    echo "Ratchet MD trajectory: work/ratchet.nc"
fi
