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

show_engine_output() {
    local output=$1
    if [[ -s "$output" ]]; then
        echo "Last 20 lines of $work_dir/$output:" >&2
        tail -n 20 "$output" >&2
    fi
}

# Partial output is never removed or overwritten; the user moves it out of work.
# Called after cd work, so paths are relative to work.
die_partial() {
    local reason=$1
    local label=$2
    shift 2
    local leftover_files=()
    local path
    for path in "$@"; do
        if [[ -e "$path" ]]; then
            leftover_files+=("$work_dir/$path")
        fi
    done
    if (( ${#leftover_files[@]} == 0 )); then
        die "${reason}No $label output was written. Fix the cause and rerun $rerun_command."
    fi
    die "${reason}Partial $label output is retained: ${leftover_files[*]}. Move these files out of $work_dir (for example: mkdir -p $work_dir.failed && mv ${leftover_files[*]} $work_dir.failed/) and rerun $rerun_command."
}

# Stop when a stage left output without completion evidence.
refuse_partial() {
    local label=$1
    local evidence=$2
    shift 2
    local path
    if [[ -e "$evidence" ]]; then
        return
    fi
    for path in "$@"; do
        if [[ -e "$path" ]]; then
            die_partial "" "$label" "$@"
        fi
    done
}

engine=${AMBER_ENGINE:-pmemd.cuda}
work_dir=work
rerun_command="./run.sh"

if (( ! ${dry_run:-0} )) &&
        [[ ${original_args[0]:-} != -h && ${original_args[0]:-} != --help && ${original_args[0]:-} != --dry-run ]] &&
        [[ ${MD_WRITER_PARENT:-} != "$PPID" || ${MD_WRITER_ENTRY:-} != "$0" ]]; then
    exec "${PYTHON:-python3}" helpers/writer_guard.py \
        --registry "work" --read "inputs" --write "work" -- "$0" "${original_args[@]}"
fi

topology=system.parm7

if (( ! dry_run )) && ! command -v "$engine" >/dev/null 2>&1; then
    die "AMBER engine not found: $engine"
fi
if [[ ! -s "$work_dir/system.parm7" || ! -s "$work_dir/system.rst7" ]]; then
    die "Run build.sh first: $work_dir"
fi

if (( dry_run )); then
    echo "Dry run: planned GaMD commands; no engine execution"
    printf '+ (cd %q && %q -O -i inputs/minimize.in -o minimize.out -p system.parm7 -c system.rst7 -r minimize.rst7 -inf minimize.info)\n' "$work_dir" "$engine"
    printf '+ (cd %q && %q -O -i inputs/heat.in -o heat.out -p system.parm7 -c minimize.rst7 -r heat.rst7 -inf heat.info -x heat.nc -ref minimize.rst7)\n' "$work_dir" "$engine"
    printf '+ (cd %q && %q -O -i inputs/equilibrate.in -o equilibrate.out -p system.parm7 -c heat.rst7 -r equilibrate.rst7 -inf equilibrate.info -x equilibrate.nc)\n' "$work_dir" "$engine"
    printf '+ (cd %q && %q -O -i inputs/gamd_prepare.in -o gamd_prepare.out -p system.parm7 -c equilibrate.rst7 -r gamd_prepare.rst7 -inf gamd_prepare.info -x gamd_prepare.nc -gamd gamd_prepare.gamd.log)\n' "$work_dir" "$engine"
    printf '+ (cd %q && %q -O -i inputs/production.in -o production.out -p system.parm7 -c gamd_prepare.rst7 -r production.rst7 -inf production.info -x production.nc -gamd production.gamd.log)\n' "$work_dir" "$engine"
    exit 0
fi

mkdir -p "$work_dir/inputs"
"${PYTHON:-python3}" helpers/input_identity.py --verify "$work_dir"
source_options=(--input "$work_dir/system.parm7" --input "$work_dir/system.rst7")
for source_input in inputs/*; do
    if [[ -f "$source_input" ]]; then
        source_options+=(--input "$source_input")
    fi
done
"${PYTHON:-python3}" helpers/input_identity.py \
    --record "$work_dir/.source.identity.json" --stage "run source inputs" \
    "${source_options[@]}" --value="$engine" --output "$work_dir/gamd-restart.dat"

cp inputs/minimize.in "$work_dir/inputs/minimize.in"
cp inputs/equilibrate.in "$work_dir/inputs/equilibrate.in"
cp inputs/gamd_prepare.in "$work_dir/inputs/gamd_prepare.in"
cp inputs/production.in "$work_dir/inputs/production.in"
sed 's/@RANDOM_SEED@/41001/g' inputs/heat.in.template > "$work_dir/inputs/heat.in"

run_preparation_stage() {
    local stage=$1
    local input_file=$2
    local input_restart=$3
    shift 3

    local state
    local stage_outputs=("$stage.out" "$stage.rst7" "$stage.info" "$stage.nc")
    "${PYTHON:-python3}" ../helpers/input_identity.py \
        --record ".$stage.identity.json" --stage "$stage" -- \
        "$engine" -O -i "$input_file" -o "$stage.out" -p "$topology" \
        -c "$input_restart" -r "$stage.rst7" -inf "$stage.info" "$@"
    refuse_partial "$stage" ".$stage.success.json" "${stage_outputs[@]}"
    state=$("${PYTHON:-python3}" ../helpers/input_identity.py \
        --check-completion ".$stage.identity.json")
    if [[ "$state" == complete ]]; then
        echo "Skipping: $stage outputs already exist."
        return
    fi

    echo "Running: $stage"
    if ! "$engine" \
        -O \
        -i "$input_file" \
        -o "$stage.out" \
        -p "$topology" \
        -c "$input_restart" \
        -r "$stage.rst7" \
        -inf "$stage.info" \
        "$@"; then
        show_engine_output "$stage.out"
        die_partial "$stage calculation failed. " "$stage" "${stage_outputs[@]}"
    fi
    local output
    for output in "$stage.out" "$stage.rst7"; do
        if [[ ! -s "$output" ]]; then
            die_partial "$stage output was not created: $work_dir/$output. " "$stage" "${stage_outputs[@]}"
        fi
    done
    "${PYTHON:-python3}" ../helpers/input_identity.py \
        --finish-completion ".$stage.identity.json"
    echo "Completed: $stage ($work_dir/$stage.out)"
}

cd "$work_dir"

run_preparation_stage minimize inputs/minimize.in system.rst7
run_preparation_stage heat inputs/heat.in minimize.rst7 \
    -x heat.nc \
    -ref minimize.rst7
run_preparation_stage equilibrate inputs/equilibrate.in heat.rst7 \
    -x equilibrate.nc

"${PYTHON:-python3}" ../helpers/input_identity.py \
    --record .gamd_prepare.identity.json --stage "GaMD parameter preparation" \
    --output gamd_prepare.gamd.rst --output gamd-restart.dat -- \
    "$engine" -O -i inputs/gamd_prepare.in -o gamd_prepare.out -p "$topology" \
    -c equilibrate.rst7 -r gamd_prepare.rst7 -inf gamd_prepare.info \
    -x gamd_prepare.nc -gamd gamd_prepare.gamd.log

prepare_outputs=(
    gamd_prepare.out gamd_prepare.rst7 gamd_prepare.info gamd_prepare.nc
    gamd_prepare.gamd.log gamd_prepare.gamd.rst gamd-restart.dat
)
refuse_partial gamd_prepare .gamd_prepare.success.json "${prepare_outputs[@]}"
gamd_state=$("${PYTHON:-python3}" ../helpers/input_identity.py \
    --check-completion .gamd_prepare.identity.json)
if [[ "$gamd_state" == complete && -s gamd_prepare.gamd.log && -s gamd_prepare.gamd.rst ]]; then
    echo "Skipping: gamd_prepare outputs already exist."
else
    echo "Running: gamd_prepare"
    if ! "$engine" \
        -O \
        -i inputs/gamd_prepare.in \
        -o gamd_prepare.out \
        -p "$topology" \
        -c equilibrate.rst7 \
        -r gamd_prepare.rst7 \
        -inf gamd_prepare.info \
        -x gamd_prepare.nc \
        -gamd gamd_prepare.gamd.log; then
        show_engine_output gamd_prepare.out
        die_partial "gamd_prepare calculation failed. " gamd_prepare "${prepare_outputs[@]}"
    fi
    if [[ ! -s gamd-restart.dat ]]; then
        die_partial "gamd_prepare state was not created: $work_dir/gamd-restart.dat. " \
            gamd_prepare "${prepare_outputs[@]}"
    fi
    for output in gamd_prepare.out gamd_prepare.rst7 gamd_prepare.gamd.log; do
        if [[ ! -s "$output" ]]; then
            die_partial "GaMD preparation output was not created: $work_dir/$output. " \
                gamd_prepare "${prepare_outputs[@]}"
        fi
    done
    cp gamd-restart.dat gamd_prepare.gamd.rst
    "${PYTHON:-python3}" ../helpers/input_identity.py \
        --finish-completion .gamd_prepare.identity.json --required-output gamd_prepare.gamd.rst
    echo "Completed: gamd_prepare ($work_dir/gamd_prepare.gamd.rst)"
fi

"${PYTHON:-python3}" ../helpers/input_identity.py \
    --record .production.identity.json --stage production --output .production.started \
    --input gamd_prepare.gamd.rst -- \
    "$engine" -O -i inputs/production.in -o production.out -p "$topology" \
    -c gamd_prepare.rst7 -r production.rst7 -inf production.info \
    -x production.nc -gamd production.gamd.log

if [[ -e .production.success.json ]]; then
    "${PYTHON:-python3}" ../helpers/input_identity.py \
        --check-completion .production.identity.json >/dev/null
    die "Production already completed: $work_dir/production.nc. Analyze it with python3 anal.py. To run a new production, move work aside (for example: mv work work.old) and rerun the build.sh and run.sh commands in README.md."
fi

# A failed production leaves its attempt record and the engine-modified GaMD state.
production_outputs=(
    production.out production.rst7 production.info production.nc
    production.gamd.log .production.started
)
for output in "${production_outputs[@]}"; do
    if [[ -e "$output" ]]; then
        die_partial "" production "${production_outputs[@]}" gamd-restart.dat
    fi
done
production_outputs+=(gamd-restart.dat)

"${PYTHON:-python3}" ../helpers/input_identity.py \
    --check-completion .production.identity.json >/dev/null
# Preserve an attempted production even when only its mutable GaMD state changed.
: > .production.started
cp gamd_prepare.gamd.rst gamd-restart.dat
echo "Running: production"
if ! "$engine" \
    -O \
    -i inputs/production.in \
    -o production.out \
    -p "$topology" \
    -c gamd_prepare.rst7 \
    -r production.rst7 \
    -inf production.info \
    -x production.nc \
    -gamd production.gamd.log; then
    show_engine_output production.out
    die_partial "production calculation failed. " production "${production_outputs[@]}"
fi

for output in production.out production.rst7 production.nc production.gamd.log; do
    if [[ ! -s "$output" ]]; then
        die_partial "Production output was not created: $work_dir/$output. " \
            production "${production_outputs[@]}"
    fi
done

"${PYTHON:-python3}" ../helpers/input_identity.py \
    --finish-completion .production.identity.json

echo "1 ns GaMD production completed: $work_dir/production.nc"
