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
        echo "Dry run: $label (work/$output)"
        printf '+ '
        printf '%q ' "$@"
        printf '\n'
        return
    fi

    "${PYTHON:-python3}" ../helpers/input_identity.py \
        --record ".$output.identity.json" --stage "$label" -- "$@"

    local completion_state
    completion_state=$("${PYTHON:-python3}" ../helpers/input_identity.py \
        --check-completion ".$output.identity.json")
    if [[ "$completion_state" == complete ]]; then
        echo "Skipping completed stage: $label (work/$output)"
        return
    fi

    echo "Running: $label"
    if ! "$@"; then
        die "$label failed; expected engine output: work/$output (may be absent); see engine diagnostics above"
    fi
    if [[ ! -s "$output" ]]; then
        die "$label output was not created: work/$output"
    fi
    if [[ ! -s "$restart" ]]; then
        die "$label restart was not created: work/$restart"
    fi
    if [[ "$output" == production.out && ! -s production.nc ]]; then
        die "$label trajectory was not created: work/production.nc"
    fi
    "${PYTHON:-python3}" ../helpers/input_identity.py \
        --finish-completion ".$output.identity.json"
    echo "Completed: $label (work/$output)"
}

if (( ! ${dry_run:-0} )) &&
        [[ ${original_args[0]:-} != -h && ${original_args[0]:-} != --help && ${original_args[0]:-} != --dry-run ]] &&
        [[ ${MD_WRITER_PARENT:-} != "$PPID" || ${MD_WRITER_ENTRY:-} != "$0" ]]; then
    exec "${PYTHON:-python3}" helpers/writer_guard.py \
        --registry ".." --read "inputs" --read "../2_Topology_Build/work" --write "work" -- "$0" "${original_args[@]}"
fi

engine=${AMBER_ENGINE:-pmemd.cuda}
topology=../2_Topology_Build/work/system.parm7
coordinates=../2_Topology_Build/work/system.rst7

if (( ! dry_run )) && ! command -v "$engine" >/dev/null 2>&1; then
    die "AMBER engine not found: $engine"
fi
if [[ ! -s "$topology" || ! -s "$coordinates" ]]; then
    die "Run preflight: topology or restart missing: $topology, $coordinates. Run ../2_Topology_Build/run.sh first."
fi
if (( ! dry_run )) && [[ -e work/production.out ]]; then
    die "Production output already exists: work/production.out"
fi

if (( ! dry_run )); then
    "${PYTHON:-python3}" helpers/input_identity.py --verify work
    source_options=()
    for source_input in inputs/*.in; do
        source_options+=(--input "$source_input")
    done
    source_options+=(--input ../2_Topology_Build/work/system.parm7 --input ../2_Topology_Build/work/system.rst7)
    "${PYTHON:-python3}" helpers/input_identity.py \
        --record work/.source.identity.json --stage "run source inputs" \
        "${source_options[@]}" --value="$engine"
    mkdir -p work/inputs
    cp "$topology" work/system.parm7
    cp "$coordinates" work/system.rst7
    cp inputs/*.in work/inputs/
fi
cd work

run_stage "environment minimization" min-environment.out min-environment.rst7 \
    "$engine" -O -i inputs/min-environment.in -o min-environment.out \
    -p system.parm7 -c system.rst7 -r min-environment.rst7 -ref system.rst7

run_stage "whole-system minimization" min-all.out min-all.rst7 \
    "$engine" -O -i inputs/min-all.in -o min-all.out \
    -p system.parm7 -c min-environment.rst7 -r min-all.rst7

run_stage "NVT heating" heat.out heat.rst7 \
    "$engine" -O -i inputs/heat.in -o heat.out \
    -p system.parm7 -c min-all.rst7 -r heat.rst7 -x heat.nc \
    -inf heat.info -ref min-all.rst7

run_stage "NPT equilibration" equil.out equil.rst7 \
    "$engine" -O -i inputs/equil.in -o equil.out \
    -p system.parm7 -c heat.rst7 -r equil.rst7 -x equil.nc \
    -inf equil.info -ref heat.rst7

run_stage "1 ns production" production.out production.rst7 \
    "$engine" -O -i inputs/production.in -o production.out \
    -p system.parm7 -c equil.rst7 -r production.rst7 \
    -x production.nc -inf production.info

echo "Production trajectory: work/production.nc"
