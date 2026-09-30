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

stage_outputs_complete() {
    local stage=$1 replica suffix
    local require_complete=${2:-}
    local required=(out rst7 info)
    if [[ "$stage" != minimize ]]; then
        required+=(nc)
    fi
    while IFS=$'\t' read -r replica _; do
        if [[ "$replica" == replica ]]; then
            continue
        fi
        for suffix in "${required[@]}"; do
            if [[ ! -s "work/$replica/$stage.$suffix" ]]; then
                if [[ "$require_complete" == --require-complete ]]; then
                    die "$stage output is incomplete: work/$replica/$stage.$suffix; existing files were preserved."
                fi
                return 1
            fi
        done
        if [[ "$stage" == production ]]; then
            for suffix in gamd.production.log restraint.production.dat; do
                if [[ ! -s "work/$replica/$suffix" ]]; then
                    if [[ "$require_complete" == --require-complete ]]; then
                        die "$stage output is incomplete: work/$replica/$suffix; existing files were preserved."
                    fi
                    return 1
                fi
            done
        fi
    done < work/states.tsv
    if [[ "$stage" == production && ! -s work/exchange.log ]]; then
        if [[ "$require_complete" == --require-complete ]]; then
            die "$stage output is incomplete: work/exchange.log; existing files were preserved."
        fi
        return 1
    fi
}

stage_status() {
    local stage=$1 replica output
    local marker="work/.$stage.complete"
    if [[ -f "$marker" ]] && stage_outputs_complete "$stage"; then
        echo complete
        return
    fi
    if [[ -e "$marker" ]]; then
        echo partial
        return
    fi
    if [[ "$stage" == production && -e work/exchange.log ]]; then
        echo partial
        return
    fi
    while IFS=$'\t' read -r replica _; do
        if [[ "$replica" == replica ]]; then
            continue
        fi
        for output in "work/$replica/$stage."{out,rst7,nc,info} \
            "work/$replica/gamd.$stage.log" "work/$replica/restraint.$stage.dat"; do
            if [[ -e "$output" ]]; then
                echo partial
                return
            fi
        done
    done < work/states.tsv
    echo missing
}

mark_stage_complete() {
    local stage=$1
    stage_outputs_complete "$stage" --require-complete
    touch "work/.$stage.complete"
    echo "Completed: $stage (work)"
}

run_window_stage() {
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
        die "Partial $stage output retained in work. Inspect the files before retrying."
    fi

    echo "Running: $stage"
    while IFS=$'\t' read -r replica _; do
        if [[ "$replica" == replica ]]; then
            continue
        fi
        replica_dir="work/$replica"
        if ! (
            cd "$replica_dir"
            "$amber_engine" \
                -O \
                -i "$stage.in" \
                -o "$stage.out" \
                -p system.parm7 \
                -c "$input_restart" \
                -r "$stage.rst7" \
                -x "$stage.nc" \
                -inf "$stage.info"
        ); then
            die "$stage failed: $replica_dir/$stage.out"
        fi
    done < work/states.tsv
    mark_stage_complete "$stage"
}

gamd_state_status() {
    local existing=0 complete=0 output
    for output in "${gamd_required[@]}"; do
        if [[ -e "$output" ]]; then
            existing=$((existing + 1))
        fi
        if [[ -s "$output" ]]; then
            complete=$((complete + 1))
        fi
    done
    if [[ -f work/.gamd_prepare.complete && "$complete" -eq "${#gamd_required[@]}" ]]; then
        echo complete
    elif [[ -e work/.gamd_prepare.complete || "$existing" -ne 0 || -e "work/$gamd_reference_replica/restraint.gamd_prepare.dat" ]]; then
        echo partial
    else
        echo missing
    fi
}

prepare_gamd_state() {
    local reference_dir="work/$gamd_reference_replica"
    local replica replica_dir output
    local status
    status=$(gamd_state_status)
    if [[ "$status" == complete ]]; then
        echo "Skipping completed stage: GaMD parameter preparation"
        return
    fi
    if [[ "$status" == partial ]]; then
        die "Partial GaMD preparation output retained: $reference_dir"
    fi
    echo "Running: GaMD parameter preparation in window $gamd_reference_replica"
    if ! (
        cd "$reference_dir"
        "$amber_engine" \
            -O \
            -i gamd_prepare.in \
            -o gamd_prepare.out \
            -p system.parm7 \
            -c equilibrate.rst7 \
            -r gamd_prepare.rst7 \
            -x gamd_prepare.nc \
            -inf gamd_prepare.info \
            -gamd gamd.prepare.log
    ); then
        die "GaMD parameter preparation failed: $reference_dir/gamd_prepare.out"
    fi
    for output in gamd_prepare.out gamd_prepare.rst7 gamd_prepare.nc gamd_prepare.info gamd.prepare.log gamd-restart.dat; do
        if [[ ! -s "$reference_dir/$output" ]]; then
            die "GaMD preparation output is incomplete: $reference_dir/$output"
        fi
    done
    while IFS=$'\t' read -r replica _; do
        if [[ "$replica" == replica ]]; then
            continue
        fi
        replica_dir="work/$replica"
        if [[ "$replica" != "$gamd_reference_replica" ]]; then
            cp "$reference_dir/gamd-restart.dat" "$replica_dir/gamd-restart.dat"
        fi
        cp "$replica_dir/equilibrate.rst7" "$replica_dir/production_start.rst7"
    done < work/states.tsv
    for output in "${gamd_required[@]}"; do
        if [[ ! -s "$output" ]]; then
            die "GaMD preparation output is incomplete: $output"
        fi
    done
    touch work/.gamd_prepare.complete
    echo "Completed: shared GaMD parameter preparation (work)"
}

amber_engine=${AMBER_ENGINE:-pmemd.cuda}
amber_mpi_engine=${AMBER_MPI_ENGINE:-pmemd.cuda.MPI}
mpi_launcher=${MPI_LAUNCHER:-mpirun}
replica_count=20
gamd_reference_replica=009

if [[ ! -s work/states.tsv ]]; then
    die "Run ./build.sh first."
fi
gamd_required=(
    "work/$gamd_reference_replica/gamd_prepare.out"
    "work/$gamd_reference_replica/gamd_prepare.rst7"
    "work/$gamd_reference_replica/gamd_prepare.nc"
    "work/$gamd_reference_replica/gamd_prepare.info"
    "work/$gamd_reference_replica/gamd.prepare.log"
)
while IFS=$'\t' read -r replica _; do
    if [[ "$replica" == replica ]]; then
        continue
    fi
    gamd_required+=("work/$replica/gamd-restart.dat" "work/$replica/production_start.rst7")
done < work/states.tsv

if (( dry_run )); then
    echo "Dry run: planned replica commands; no engine execution"
    printf '+ %q -O -i %q -o %q -p %q -c %q -r %q -x %q -inf %q\n' \
        "$amber_engine" work/000/minimize.in work/000/minimize.out \
        work/000/system.parm7 work/000/system.rst7 work/000/minimize.rst7 \
        work/000/minimize.nc work/000/minimize.info
    printf '+ %q -np %q %q -ng %q -groupfile %q -rem 3 -remlog %q\n' \
        "$mpi_launcher" "$replica_count" "$amber_mpi_engine" "$replica_count" \
        work/production.group work/exchange.log
    exit 0
fi

for executable in "$amber_engine" "$amber_mpi_engine" "$mpi_launcher"; do
    if ! command -v "$executable" >/dev/null 2>&1; then
        die "Executable not found: $executable"
    fi
done
# Reject retained output before running any stage or rewriting generated input.
missing_stage=""
for stage in minimize heat equilibrate gamd_prepare production; do
    if [[ "$stage" == gamd_prepare ]]; then
        status=$(gamd_state_status)
    else
        status=$(stage_status "$stage")
    fi
    if [[ "$status" == partial ]]; then
        die "Partial or unmarked $stage output retained in work; inspect the files before retrying."
    fi
    if [[ "$status" == missing ]]; then
        missing_stage=$stage
    elif [[ -n "$missing_stage" ]]; then
        die "Completed $stage has a missing prerequisite: $missing_stage in work."
    fi
done
if [[ "$(stage_status production)" == complete ]]; then
    echo "Skipping completed production: work"
    exit 0
fi

run_window_stage minimize system.rst7
run_window_stage heat minimize.rst7
run_window_stage equilibrate heat.rst7
prepare_gamd_state

group_file=work/production.group
: > "$group_file"
while IFS=$'\t' read -r replica _; do
    if [[ "$replica" == replica ]]; then
        continue
    fi
    replica_dir="work/$replica"
    sed \
        -e "s|@DUMPAVE@|$replica_dir/restraint.production.dat|g" \
        "$replica_dir/production.template.in" \
        > "$replica_dir/production.in"
    echo "-O -i $replica_dir/production.in -o $replica_dir/production.out -p $replica_dir/system.parm7 -c $replica_dir/production_start.rst7 -r $replica_dir/production.rst7 -x $replica_dir/production.nc -inf $replica_dir/production.info -gamd $replica_dir/gamd.production.log" \
        >> "$group_file"
done < work/states.tsv

echo "Running: 1 ns GaREUS production"
if ! "$mpi_launcher" \
    -np "$replica_count" \
    "$amber_mpi_engine" \
    -ng "$replica_count" \
    -groupfile "$group_file" \
    -rem 3 \
    -remlog work/exchange.log; then
    die "GaREUS production failed: work/exchange.log"
fi

mark_stage_complete production
echo "Completed 1 ns GaREUS: work"
