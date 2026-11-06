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

# Print existing files as work/... paths, relative to the tutorial directory.
retained_files() {
    local names=()
    local name
    for name in "$@"; do
        if [[ -e "$name" || -L "$name" ]]; then
            names+=("work/$name")
        fi
    done
    echo "${names[*]}"
}

# Stop with the retained stage files and the manual recovery command.
die_retained() {
    local label=$1
    local reason=$2
    shift 2
    local retained
    retained=$(retained_files "$@")
    if [[ -z "$retained" ]]; then
        die "${reason}No $label output was written; rerun ./run.sh after fixing the cause."
    fi
    die "${reason}Partial $label output is retained: $retained. Move these files out of work (for example: mkdir -p work.failed && mv $retained work.failed/) and rerun ./run.sh."
}

show_engine_log() {
    local engine_output=$1
    if [[ -s "$engine_output" ]]; then
        echo "Last 20 lines of work/$engine_output:" >&2
        tail -n 20 "$engine_output" >&2
    fi
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

    # Engine files without completion evidence are kept for manual inspection.
    local stage_files=()
    local index
    for ((index = 1; index < $#; index++)); do
        case "${!index}" in
            -o|-r|-x|-inf)
                index=$((index + 1))
                stage_files+=("${!index}")
                ;;
        esac
    done
    if [[ ! -e ".$output.success.json" && -n "$(retained_files "${stage_files[@]}")" ]]; then
        die_retained "$label" "" "${stage_files[@]}"
    fi

    local completion_state
    completion_state=$("${PYTHON:-python3}" ../helpers/input_identity.py \
        --check-completion ".$output.identity.json")
    if [[ "$completion_state" == complete ]]; then
        echo "Skipping completed stage: $label (work/$output)"
        return
    fi

    echo "Running: $label"
    if ! "$@"; then
        show_engine_log "$output"
        die_retained "$label" "$label failed; engine output: work/$output. " "${stage_files[@]}"
    fi
    if [[ ! -s "$output" ]]; then
        die_retained "$label" "$label output was not created: work/$output. " "${stage_files[@]}"
    fi
    if [[ ! -s "$restart" ]]; then
        die_retained "$label" "$label restart was not created: work/$restart. " "${stage_files[@]}"
    fi
    if [[ "$output" == production.out && ! -s production.nc ]]; then
        die_retained "$label" "$label trajectory was not created: work/production.nc. " "${stage_files[@]}"
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
# A partial production run is reported by run_stage with recovery steps.
if (( ! dry_run )) && [[ -e work/production.out && -e work/.production.out.success.json ]]; then
    die "Production output already exists: work/production.out. To start again, move work aside (for example: mv work work.old) and rerun ./run.sh."
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
    for source_input in "$topology" "$coordinates" inputs/*.in; do
        filename=${source_input##*/}
        if [[ "$source_input" == inputs/* ]]; then
            destination="work/inputs/$filename"
        else
            destination="work/$filename"
        fi
        if [[ -e "$destination" ]]; then
            if ! cmp -s "$source_input" "$destination"; then
                die "Run preflight: copied input differs and was retained: $destination. Move work aside (for example: mv work work.old) and rerun ./run.sh."
            fi
        else
            cp "$source_input" "$destination"
        fi
    done
    cd work
elif [[ -d work ]]; then
    cd work
fi

# Water and bulk ions relax before lipids are released.
run_stage "solvent minimization" min-solvent.out min-solvent.rst7 \
    "$engine" \
    -O \
    -i inputs/min-solvent.in \
    -o min-solvent.out \
    -p system.parm7 \
    -c system.rst7 \
    -r min-solvent.rst7 \
    -inf min-solvent.info \
    -ref system.rst7

run_stage "lipid minimization" min-lipid.out min-lipid.rst7 \
    "$engine" \
    -O \
    -i inputs/min-lipid.in \
    -o min-lipid.out \
    -p system.parm7 \
    -c min-solvent.rst7 \
    -r min-lipid.rst7 \
    -inf min-lipid.info \
    -ref system.rst7

run_stage "NVT heating" heat.out heat.rst7 \
    "$engine" \
    -O \
    -i inputs/heat.in \
    -o heat.out \
    -p system.parm7 \
    -c min-lipid.rst7 \
    -r heat.rst7 \
    -x heat.nc \
    -inf heat.info \
    -ref min-lipid.rst7

# Preserve velocities and the heated reference while narrowing the atom mask.
run_stage "heavy-atom NPT equilibration" equil-heavy.out equil-heavy.rst7 \
    "$engine" \
    -O \
    -i inputs/equil-heavy.in \
    -o equil-heavy.out \
    -p system.parm7 \
    -c heat.rst7 \
    -r equil-heavy.rst7 \
    -x equil-heavy.nc \
    -inf equil-heavy.info \
    -ref heat.rst7

run_stage "backbone NPT equilibration" equil-backbone.out equil-backbone.rst7 \
    "$engine" \
    -O \
    -i inputs/equil-backbone.in \
    -o equil-backbone.out \
    -p system.parm7 \
    -c equil-heavy.rst7 \
    -r equil-backbone.rst7 \
    -x equil-backbone.nc \
    -inf equil-backbone.info \
    -ref heat.rst7

run_stage "unrestrained NPT equilibration" equil.out equil.rst7 \
    "$engine" \
    -O \
    -i inputs/equil.in \
    -o equil.out \
    -p system.parm7 \
    -c equil-backbone.rst7 \
    -r equil.rst7 \
    -x equil.nc \
    -inf equil.info

run_stage "1 ns production" production.out production.rst7 \
    "$engine" -O -i inputs/production.in -o production.out \
    -p system.parm7 -c equil.rst7 -r production.rst7 \
    -x production.nc -inf production.info

echo "Production trajectory: work/production.nc"
