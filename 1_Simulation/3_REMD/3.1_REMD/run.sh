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

stage_status() {
    local stage=$1
    local complete=0
    local existing=0
    local replica

    while IFS=$'\t' read -r replica _; do
        if [[ "$replica" == replica ]]; then
            continue
        fi
        if [[ -s "work/$replica/$stage.out" && -s "work/$replica/$stage.rst7" ]]; then
            complete=$((complete + 1))
        fi
        if [[ -e "work/$replica/$stage.out" || -e "work/$replica/$stage.rst7" ]]; then
            existing=$((existing + 1))
        fi
    done < work/states.tsv

    if (( complete == replica_count )); then
        echo complete
    elif (( existing == 0 )); then
        echo missing
    else
        echo partial
    fi
}

run_replica_stage() {
    local stage=$1
    local input_restart=$2
    local status
    local replica

    status=$(stage_status "$stage")
    if [[ "$status" == complete ]]; then
        echo "Skipping completed stage: $stage"
        return
    fi
    if [[ "$status" == partial ]]; then
        echo "Warning: restarting incomplete stage for all replicas: $stage" >&2
    fi

    echo "Running: $stage"
    while IFS=$'\t' read -r replica _; do
        if [[ "$replica" == replica ]]; then
            continue
        fi
        replica_dir="work/$replica"
        if ! "$amber_engine" \
            -O \
            -i "$replica_dir/$stage.in" \
            -o "$replica_dir/$stage.out" \
            -p "$replica_dir/system.parm7" \
            -c "$replica_dir/$input_restart" \
            -r "$replica_dir/$stage.rst7" \
            -x "$replica_dir/$stage.nc" \
            -inf "$replica_dir/$stage.info"; then
            die "$stage failed: $replica_dir/$stage.out"
        fi
    done < work/states.tsv
}

amber_engine=${AMBER_ENGINE:-pmemd.cuda}
amber_mpi_engine=${AMBER_MPI_ENGINE:-pmemd.cuda.MPI}
mpi_launcher=${MPI_LAUNCHER:-mpirun}

if [[ ! -s work/states.tsv ]]; then
    die "Run ./build.sh first."
fi
replica_count=$(awk 'NR > 1 {count++} END {print count + 0}' work/states.tsv)

if (( dry_run )); then
    printf '+ %q -O -i %q -o %q -p %q -c %q -r %q -x %q -inf %q\n' \
        "$amber_engine" work/000/minimize.in work/000/minimize.out \
        work/000/system.parm7 work/000/system.rst7 work/000/minimize.rst7 \
        work/000/minimize.nc work/000/minimize.info
    printf '+ %q -np %q %q -ng %q -groupfile %q -rem 1 -remlog %q\n' \
        "$mpi_launcher" "$replica_count" "$amber_mpi_engine" "$replica_count" \
        work/production.group work/exchange.log
    exit 0
fi

for executable in "$amber_engine" "$amber_mpi_engine" "$mpi_launcher"; do
    if ! command -v "$executable" >/dev/null 2>&1; then
        die "Executable not found: $executable"
    fi
done

if find work/[0-9][0-9][0-9] -maxdepth 1 \
    \( -name 'production.out' -o -name 'production.rst7' \) \
    -print -quit 2>/dev/null | grep -q .; then
    die "Production output already exists in work."
fi

run_replica_stage minimize system.rst7
run_replica_stage heat minimize.rst7
run_replica_stage equilibrate heat.rst7

group_file=work/production.group
: > "$group_file"
while IFS=$'\t' read -r replica _; do
    if [[ "$replica" == replica ]]; then
        continue
    fi
    replica_dir="work/$replica"
    echo "-O -i $replica_dir/production.in -o $replica_dir/production.out -p $replica_dir/system.parm7 -c $replica_dir/equilibrate.rst7 -r $replica_dir/production.rst7 -x $replica_dir/production.nc -inf $replica_dir/production.info" \
        >> "$group_file"
done < work/states.tsv

echo "Running: 1 ns T-REMD production"
if ! "$mpi_launcher" \
    -np "$replica_count" \
    "$amber_mpi_engine" \
    -ng "$replica_count" \
    -groupfile "$group_file" \
    -rem 1 \
    -remlog work/exchange.log; then
    die "T-REMD production failed: work/exchange.log"
fi

echo "Completed 1 ns T-REMD: work"
