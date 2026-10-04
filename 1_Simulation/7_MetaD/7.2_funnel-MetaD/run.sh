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

engine=${AMBER_ENGINE:-pmemd.cuda}
plumed=${PLUMED:-plumed}

if (( ! dry_run )); then
    for executable in "$engine" "$plumed"; do
        if ! command -v "$executable" >/dev/null 2>&1; then
            die "Executable not found: $executable"
        fi
    done
    for action in FUNNEL_PS FUNNEL; do
        if ! "$plumed" manual --action "$action" >/dev/null 2>&1; then
            die "PLUMED action $action is unavailable. Rebuild PLUMED 2.10 with the funnel module."
        fi
    done
fi
for input in system.parm7 system.rst7 funnel-reference.pdb plumed.dat atom_count.txt; do
    if [[ ! -s "$work_dir/$input" ]]; then
        die "Run build.sh first: $work_dir/$input"
    fi
done

if (( dry_run )); then
    echo "Dry run: planned sampling commands; no engine execution"
    for stage in minimize-solvent minimize-all heat equilibrate; do
        printf '+ (cd %q && %q -O -i inputs/%s.in -o %s.out -p system.parm7 -c PREVIOUS.rst7 -r %s.rst7 -inf %s.info)\n' \
            "$work_dir" "$engine" "$stage" "$stage" "$stage" "$stage"
    done
    printf '+ (cd %q && %q -O -i inputs/production.in -o production.out -p system.parm7 -c equilibrate.rst7 -r production.rst7 -inf production.info -x production.nc)\n' "$work_dir" "$engine"
    exit 0
fi

"${PYTHON:-python3}" helpers/input_identity.py --verify "$work_dir"
source_options=(--input "$work_dir/system.parm7" --input "$work_dir/system.rst7")
for source_input in inputs/*; do
    if [[ -f "$source_input" ]]; then
        source_options+=(--input "$source_input")
    fi
done
"${PYTHON:-python3}" helpers/input_identity.py \
    --record "$work_dir/.source.identity.json" --stage "run source inputs" \
    "${source_options[@]}" --value="$engine" --output "$work_dir/COLVAR" --output "$work_dir/HILLS" --output "$work_dir/KERNELS"

mkdir -p "$work_dir/inputs"
cp inputs/minimize-solvent.in "$work_dir/inputs/minimize-solvent.in"
cp inputs/minimize-all.in "$work_dir/inputs/minimize-all.in"
sed 's/@RANDOM_SEED@/72001/g' inputs/heat.in.template > "$work_dir/inputs/heat.in"
sed 's/@RANDOM_SEED@/72002/g' inputs/equilibrate.in.template > "$work_dir/inputs/equilibrate.in"

atom_count=$(<"$work_dir/atom_count.txt")
echo "Checking PLUMED input: $work_dir/plumed.dat"
if (
    cd "$work_dir"
    "$plumed" driver --plumed plumed.dat --parse-only --natoms "$atom_count"
); then
    echo "Completed: PLUMED input check"
else
    status=$?
    echo "Error: PLUMED input check failed: $work_dir/plumed.dat; inspect terminal diagnostics." >&2
    exit "$status"
fi
if [[ ! -s "$work_dir/FUNNEL_GRID" ]]; then
    die "PLUMED setup did not create the funnel grid: $work_dir/FUNNEL_GRID"
fi

run_stage() {
    local stage=$1
    local input_restart=$2
    shift 2
    local output_file="$work_dir/$stage.out"
    local restart_file="$work_dir/$stage.rst7"

    "${PYTHON:-python3}" helpers/input_identity.py \
        --record "$work_dir/.$stage.identity.json" --stage "$stage" \
        --directory "$work_dir" -- "$engine" -O -i "inputs/$stage.in" \
        -o "$stage.out" -p system.parm7 -c "$input_restart" \
        -r "$stage.rst7" -inf "$stage.info" "$@"

    local completion_state
    completion_state=$("${PYTHON:-python3}" helpers/input_identity.py \
        --check-completion "$work_dir/.$stage.identity.json")
    if [[ "$completion_state" == complete ]]; then
        echo "Skipping: $stage outputs already exist."
        return
    fi

    echo "Running: $stage"
    if ! (
        cd "$work_dir"
        "$engine" \
            -O \
            -i "inputs/$stage.in" \
            -o "$stage.out" \
            -p system.parm7 \
            -c "$input_restart" \
            -r "$stage.rst7" \
            -inf "$stage.info" \
            "$@"
    ); then
        die "$stage calculation failed: $output_file"
    fi
    local output
    for output in "$output_file" "$restart_file"; do
        if [[ ! -s "$output" ]]; then
            die "$stage output was not created: $output"
        fi
    done
    "${PYTHON:-python3}" helpers/input_identity.py \
        --finish-completion "$work_dir/.$stage.identity.json" --directory "$work_dir"
    echo "Completed: $stage ($output_file)"
}

run_stage minimize-solvent system.rst7 -ref system.rst7
run_stage minimize-all minimize-solvent.rst7
run_stage heat minimize-all.rst7 -x heat.nc -ref minimize-all.rst7
run_stage equilibrate heat.rst7 -x equilibrate.nc -ref heat.rst7

for output in production.out production.rst7 production.info production.nc; do
    if [[ -e "$work_dir/$output" ]]; then
        die "Production output already exists: $work_dir/$output"
    fi
done

sed 's/@RANDOM_SEED@/72101/g' inputs/production.in.template > "$work_dir/production.in"

production_identity_options=(--input "$work_dir/plumed.dat" --output "$work_dir/COLVAR" --output "$work_dir/HILLS")
if [[ -s "$work_dir/funnel-reference.pdb" ]]; then
    production_identity_options+=(--input "$work_dir/funnel-reference.pdb")
fi
"${PYTHON:-python3}" helpers/input_identity.py \
    --record "$work_dir/.production.identity.json" --stage production \
    --directory "$work_dir" "${production_identity_options[@]}" -- \
    "$engine" -O -i production.in -o production.out -p system.parm7 \
    -c equilibrate.rst7 -r production.rst7 -x production.nc -inf production.info

"${PYTHON:-python3}" helpers/input_identity.py \
    --check-completion "$work_dir/.production.identity.json" >/dev/null

echo "Running: production"
if ! (
    cd "$work_dir"
    "$engine" \
        -O \
        -i production.in \
        -o production.out \
        -p system.parm7 \
        -c equilibrate.rst7 \
        -r production.rst7 \
        -x production.nc \
        -inf production.info
); then
    die "production calculation failed: $work_dir/production.out"
fi
for output in production.out production.rst7 production.nc COLVAR HILLS; do
    if [[ ! -s "$work_dir/$output" ]]; then
        die "Production output was not created: $work_dir/$output"
    fi
done

"${PYTHON:-python3}" helpers/input_identity.py \
    --finish-completion "$work_dir/.production.identity.json" --directory "$work_dir" \
+    --required-output "$work_dir/COLVAR" --required-output "$work_dir/HILLS"

echo "1 ns Funnel MetaD production completed: $work_dir/production.nc"
