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

if (( ! ${dry_run:-0} )) &&
        [[ ${original_args[0]:-} != -h && ${original_args[0]:-} != --help && ${original_args[0]:-} != --dry-run ]] &&
        [[ ${MD_WRITER_PARENT:-} != "$PPID" || ${MD_WRITER_ENTRY:-} != "$0" ]]; then
    exec "${PYTHON:-python3}" helpers/writer_guard.py \
        --registry "work" --read "inputs" --write "work" -- "$0" "${original_args[@]}"
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
        for output in "work/$replica/$stage."{out,rst7,nc,info}; do
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

run_replica_stage() {
    local stage=$1
    local input_restart=$2
    check_replica_inputs "$stage" "$input_restart"
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
    mark_stage_complete "$stage"
}

check_replica_inputs() {
    local stage=$1 input_restart=$2 replica replica_dir
    while IFS=$'\t' read -r replica _; do
        if [[ "$replica" == replica ]]; then
            continue
        fi
        replica_dir="work/$replica"
        identity=(--record "$replica_dir/.$stage.identity.json" --stage "$stage replica $replica"
            --directory "$replica_dir" --marker "work/.$stage.complete")
        if [[ -s "$replica_dir/distance.RST" ]]; then
            identity+=(--input "$replica_dir/distance.RST" --output "$replica_dir/restraint.$stage.dat")
        fi
        "${PYTHON:-python3}" helpers/input_identity.py "${identity[@]}" -- "$amber_engine" \
            -O -i "$stage.in" -o "$stage.out" -p system.parm7 -c "$input_restart" \
            -r "$stage.rst7" -x "$stage.nc" -inf "$stage.info"
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
    echo "Dry run: planned replica commands; no engine execution"
    printf '+ %q -O -i %q -o %q -p %q -c %q -r %q -x %q -inf %q\n' \
        "$amber_engine" work/000/minimize.in work/000/minimize.out \
        work/000/system.parm7 work/000/system.rst7 work/000/minimize.rst7 \
        work/000/minimize.nc work/000/minimize.info
    printf '+ %q -np %q %q -ng %q -groupfile %q -rem 1 -remlog %q\n' \
        "$mpi_launcher" "$replica_count" "$amber_mpi_engine" "$replica_count" \
        work/production.group work/exchange.log
    exit 0
fi

"${PYTHON:-python3}" helpers/input_identity.py --verify work
source_identity=(--record work/.source.identity.json --stage "replica source inputs"
    --input work/states.tsv --value="$amber_engine" --value="$amber_mpi_engine")
for input in inputs/*.in work/[0-9][0-9][0-9]/system.parm7 work/[0-9][0-9][0-9]/system.rst7 \
        work/[0-9][0-9][0-9]/*.in work/[0-9][0-9][0-9]/distance.RST; do
    if [[ "$input" == */production.in && -f "${input%.in}.template.in" ]]; then
        continue
    fi
    if [[ -f "$input" ]]; then
        source_identity+=(--input "$input")
    fi
done
"${PYTHON:-python3}" helpers/input_identity.py "${source_identity[@]}"

for executable in "$amber_engine" "$amber_mpi_engine" "$mpi_launcher"; do
    if ! command -v "$executable" >/dev/null 2>&1; then
        die "Executable not found: $executable"
    fi
done

# Reject retained output before running any stage or rewriting generated input.
missing_stage=""
for stage in minimize heat equilibrate production; do
    status=$(stage_status "$stage")
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

run_replica_stage minimize system.rst7
run_replica_stage heat minimize.rst7
run_replica_stage equilibrate heat.rst7

production_identity=(--record work/.production-input.identity.json --stage "replica production inputs"
    --input work/states.tsv --value="$amber_mpi_engine" --output work/.production.complete --output work/production.group --output work/exchange.log)
while IFS=$'\t' read -r replica _; do
    if [[ "$replica" == replica ]]; then
        continue
    fi
    replica_dir="work/$replica"
    production_identity+=(--input "$replica_dir/system.parm7"
        --input "$replica_dir/equilibrate.rst7" --input "$replica_dir/production.in"
        --output "$replica_dir/production.out" --output "$replica_dir/production.rst7"
        --output "$replica_dir/production.nc" --output "$replica_dir/production.info")
    if [[ -s "$replica_dir/distance.RST" ]]; then
        production_identity+=(--input "$replica_dir/distance.RST" --output "$replica_dir/restraint.production.dat")
    fi
done < work/states.tsv
"${PYTHON:-python3}" helpers/input_identity.py "${production_identity[@]}"

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

mark_stage_complete production
echo "Completed 1 ns T-REMD: work"
