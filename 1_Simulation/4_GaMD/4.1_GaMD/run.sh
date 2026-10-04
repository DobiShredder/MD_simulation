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

engine=${AMBER_ENGINE:-pmemd.cuda}
work_dir=work

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
    "${PYTHON:-python3}" ../helpers/input_identity.py \
        --record ".$stage.identity.json" --stage "$stage" -- \
        "$engine" -O -i "$input_file" -o "$stage.out" -p "$topology" \
        -c "$input_restart" -r "$stage.rst7" -inf "$stage.info" "$@"
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
        die "$stage calculation failed: $work_dir/$stage.out"
    fi
    local output
    for output in "$stage.out" "$stage.rst7"; do
        if [[ ! -s "$output" ]]; then
            die "$stage output was not created: $work_dir/$output"
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
        die "gamd_prepare calculation failed: $work_dir/gamd_prepare.out"
    fi
    if [[ ! -s gamd-restart.dat ]]; then
        die "gamd_prepare state was not created: $work_dir/gamd-restart.dat"
    fi
    for output in gamd_prepare.out gamd_prepare.rst7 gamd_prepare.gamd.log; do
        if [[ ! -s "$output" ]]; then
            die "GaMD preparation output was not created: $work_dir/$output"
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

if compgen -G 'production.*' >/dev/null; then
    die "Production output already exists in $work_dir. Remove it only if you intend to restart production."
fi

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
    die "production calculation failed: $work_dir/production.out"
fi

for output in production.out production.rst7 production.nc production.gamd.log; do
    if [[ ! -s "$output" ]]; then
        die "Production output was not created: $work_dir/$output"
    fi
done

"${PYTHON:-python3}" ../helpers/input_identity.py \
    --finish-completion .production.identity.json

echo "1 ns GaMD production completed: $work_dir/production.nc"
