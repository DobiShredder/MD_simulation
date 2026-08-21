#!/usr/bin/env bash
set -euo pipefail

dry_run=0
allow_unverified=0
while (( $# > 0 )); do
    case "$1" in
        --dry-run)
            dry_run=1
            ;;
        --allow-unverified)
            allow_unverified=1
            ;;
        *)
            echo "Usage: $0 [--dry-run] [--allow-unverified]" >&2
            exit 2
            ;;
    esac
    shift
done
if (( ! dry_run && ! allow_unverified )); then
    echo "Usage: $0 --allow-unverified" >&2
    exit 2
fi

die() {
    echo "Error: $*" >&2
    exit 1
}

engine=${AMBER_ENGINE:-pmemd.cuda}
work_dir=work
topology=system.parm7

if (( ! dry_run )) && ! command -v "$engine" >/dev/null 2>&1; then
    die "AMBER engine not found: $engine"
fi
if (( ! dry_run )) && [[ "$(basename "$engine")" != "pmemd.cuda" ]]; then
    die "Amber 26 LiGaMD3 supports only the serial GPU pmemd.cuda engine: $engine"
fi
for input in "$work_dir/system.parm7" "$work_dir/system.rst7" \
    "$work_dir/inputs/gamd_prepare.in" "$work_dir/inputs/production.in"; do
    if [[ ! -s "$input" ]]; then
        die "Run build.sh first: $input"
    fi
done

if (( dry_run )); then
    printf '+ (cd %q && %q -O -i inputs/minimize.in -o minimize.out -p system.parm7 -c system.rst7 -r minimize.rst7 -inf minimize.info)\n' "$work_dir" "$engine"
    printf '+ (cd %q && %q -O -i inputs/heat.in -o heat.out -p system.parm7 -c minimize.rst7 -r heat.rst7 -inf heat.info -x heat.nc -ref minimize.rst7)\n' "$work_dir" "$engine"
    printf '+ (cd %q && %q -O -i inputs/equilibrate.in -o equilibrate.out -p system.parm7 -c heat.rst7 -r equilibrate.rst7 -inf equilibrate.info -x equilibrate.nc)\n' "$work_dir" "$engine"
    printf '+ (cd %q && %q -O -i inputs/gamd_prepare.in -o gamd_prepare.out -p system.parm7 -c equilibrate.rst7 -r gamd_prepare.rst7 -inf gamd_prepare.info -x gamd_prepare.nc -gamd gamd_prepare.gamd.log)\n' "$work_dir" "$engine"
    printf '+ (cd %q && %q -O -i inputs/production.in -o production.out -p system.parm7 -c gamd_prepare.rst7 -r production.rst7 -inf production.info -x production.nc -gamd production.gamd.log)\n' "$work_dir" "$engine"
    exit 0
fi

cp inputs/minimize.in "$work_dir/inputs/minimize.in"
cp inputs/equilibrate.in "$work_dir/inputs/equilibrate.in"
sed 's/@RANDOM_SEED@/42001/g' inputs/heat.in.template > "$work_dir/inputs/heat.in"

stage_state() {
    local output_file=$1
    local restart_file=$2

    if [[ -s "$output_file" && -s "$restart_file" ]]; then
        echo complete
    elif [[ ! -e "$output_file" && ! -e "$restart_file" ]]; then
        echo missing
    else
        echo partial
    fi
}

run_preparation_stage() {
    local stage=$1
    local input_file=$2
    local input_restart=$3
    shift 3

    local state
    state=$(stage_state "$stage.out" "$stage.rst7")
    if [[ "$state" == complete ]]; then
        echo "Skipping: $stage outputs already exist."
        return
    fi
    if [[ "$state" == partial ]]; then
        echo "Warning: incomplete $stage outputs found; rerunning the stage." >&2
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
    if [[ ! -s "$stage.out" || ! -s "$stage.rst7" ]]; then
        die "$stage outputs were not created."
    fi
}

cd "$work_dir"

run_preparation_stage minimize inputs/minimize.in system.rst7
run_preparation_stage heat inputs/heat.in minimize.rst7 \
    -x heat.nc \
    -ref minimize.rst7
run_preparation_stage equilibrate inputs/equilibrate.in heat.rst7 \
    -x equilibrate.nc

gamd_state=$(stage_state gamd_prepare.out gamd_prepare.rst7)
if [[ "$gamd_state" == complete && -s gamd_prepare.gamd.log && -s gamd_prepare.gamd.rst ]]; then
    echo "Skipping: gamd_prepare outputs already exist."
else
    if [[ "$gamd_state" != missing || -e gamd_prepare.gamd.log || -e gamd_prepare.gamd.rst ]]; then
        echo "Warning: incomplete gamd_prepare outputs found; rerunning the stage." >&2
    fi
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
    cp gamd-restart.dat gamd_prepare.gamd.rst
fi

if compgen -G 'production.*' >/dev/null; then
    die "Production output already exists in $work_dir. Remove it only if you intend to restart production."
fi

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

echo "1 ns LiGaMD3 production completed: $work_dir/production.nc"
