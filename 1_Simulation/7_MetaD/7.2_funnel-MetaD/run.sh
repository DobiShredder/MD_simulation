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
    for stage in minimize-solvent minimize-all heat equilibrate; do
        printf '+ (cd %q && %q -O -i inputs/%s.in -o %s.out -p system.parm7 -c PREVIOUS.rst7 -r %s.rst7 -inf %s.info)\n' \
            "$work_dir" "$engine" "$stage" "$stage" "$stage" "$stage"
    done
    printf '+ (cd %q && %q -O -i inputs/production.in -o production.out -p system.parm7 -c equilibrate.rst7 -r production.rst7 -inf production.info -x production.nc)\n' "$work_dir" "$engine"
    exit 0
fi

mkdir -p "$work_dir/inputs"
cp inputs/minimize-solvent.in "$work_dir/inputs/minimize-solvent.in"
cp inputs/minimize-all.in "$work_dir/inputs/minimize-all.in"
sed 's/@RANDOM_SEED@/72001/g' inputs/heat.in.template > "$work_dir/inputs/heat.in"
sed 's/@RANDOM_SEED@/72002/g' inputs/equilibrate.in.template > "$work_dir/inputs/equilibrate.in"

atom_count=$(<"$work_dir/atom_count.txt")
(
    cd "$work_dir"
    "$plumed" driver --plumed plumed.dat --parse-only --natoms "$atom_count"
)
if [[ ! -s "$work_dir/FUNNEL_GRID" ]]; then
    die "PLUMED setup did not create the funnel grid: $work_dir/FUNNEL_GRID"
fi

run_stage() {
    local stage=$1
    local input_restart=$2
    shift 2
    local output_file="$work_dir/$stage.out"
    local restart_file="$work_dir/$stage.rst7"

    if [[ -s "$output_file" && -s "$restart_file" ]]; then
        echo "Skipping: $stage outputs already exist."
        return
    fi
    if [[ -e "$output_file" || -e "$restart_file" ]]; then
        echo "Warning: incomplete $stage outputs found; rerunning the stage." >&2
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
    if [[ ! -s "$output_file" || ! -s "$restart_file" ]]; then
        die "$stage outputs were not created."
    fi
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

echo "1 ns Funnel MetaD production completed: $work_dir/production.nc"
