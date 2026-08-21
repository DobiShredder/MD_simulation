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
    for action in ECV_MULTITHERMAL OPES_EXPANDED; do
        if ! "$plumed" manual --action "$action" >/dev/null 2>&1; then
            die "PLUMED action $action is unavailable. Rebuild PLUMED 2.10 with the opes module."
        fi
    done
fi
if [[ ! -s "$work_dir/system.parm7" || ! -s "$work_dir/system.rst7" ]]; then
    die "Run build.sh first: $work_dir"
fi
if [[ ! -s "$work_dir/atom_count.txt" ]]; then
    die "Run build.sh first: $work_dir/atom_count.txt"
fi

if (( dry_run )); then
    for stage in minimize heat equilibrate; do
        printf '+ (cd %q && %q -O -i inputs/%s.in -o %s.out -p system.parm7 -c PREVIOUS.rst7 -r %s.rst7 -inf %s.info)\n' \
            "$work_dir" "$engine" "$stage" "$stage" "$stage" "$stage"
    done
    printf '+ (cd %q && %q -O -i inputs/production.in -o production.out -p system.parm7 -c equilibrate.rst7 -r production.rst7 -inf production.info -x production.nc)\n' "$work_dir" "$engine"
    exit 0
fi

render_plumed_input() {
    local output=$1
    local data_file=$2
    local state_file=$3
    local colvar_file=$4
    sed \
        -e 's/@RESTART@//' \
        -e 's/@STATE_RFILE@//' \
        -e "s/FILE=DELTAFS/FILE=$data_file/" \
        -e "s/STATE_WFILE=opes.state/STATE_WFILE=$state_file/" \
        -e "s/FILE=COLVAR/FILE=$colvar_file/" \
        inputs/plumed.dat.template > "$output"
}

mkdir -p "$work_dir/inputs"
cp inputs/minimize.in "$work_dir/inputs/minimize.in"
sed 's/@RANDOM_SEED@/74001/g' inputs/heat.in.template > "$work_dir/inputs/heat.in"
sed 's/@RANDOM_SEED@/74002/g' inputs/equilibrate.in.template > "$work_dir/inputs/equilibrate.in"

parse_input=plumed.parse.dat
parse_data=plumed.parse.DELTAFS
parse_state=plumed.parse.state
parse_colvar=plumed.parse.COLVAR
render_plumed_input "$work_dir/$parse_input" "$parse_data" "$parse_state" "$parse_colvar"
atom_count=$(<"$work_dir/atom_count.txt")
(
    cd "$work_dir"
    "$plumed" driver --plumed "$parse_input" --parse-only --natoms "$atom_count"
)
for path in "$parse_input" "$parse_data" "$parse_state" "$parse_colvar"; do
    if [[ -e "$work_dir/$path" ]]; then
        unlink "$work_dir/$path"
    fi
done

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

run_stage minimize system.rst7
run_stage heat minimize.rst7 -x heat.nc -ref minimize.rst7
run_stage equilibrate heat.rst7 -x equilibrate.nc

for output in production.out production.rst7 production.info production.nc; do
    if [[ -e "$work_dir/$output" ]]; then
        die "Production output already exists: $work_dir/$output"
    fi
done

sed 's/@RANDOM_SEED@/74101/g' inputs/production.in.template > "$work_dir/production.in"
render_plumed_input "$work_dir/plumed.dat" "DELTAFS" opes.state COLVAR

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
for output in production.out production.rst7 production.nc COLVAR DELTAFS opes.state; do
    if [[ ! -s "$work_dir/$output" ]]; then
        die "Production output was not created: $work_dir/$output"
    fi
done

echo "1 ns OPES Expanded production completed: $work_dir/production.nc"
