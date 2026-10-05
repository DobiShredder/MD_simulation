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
        local output
        for output in "work/$replica/$stage."{out,rst7,nc,info} "work/$replica/restraint.$stage.dat"; do
            if [[ -e "$output" || -L "$output" ]]; then
                existing=$((existing + 1))
                break
            fi
        done
    done < work/states.tsv

    if [[ -f "work/.$stage.complete" ]] && (( complete == replica_count )); then
        while IFS=$'\t' read -r replica _; do
            if [[ "$replica" == replica ]]; then
                continue
            fi
            if ! "${PYTHON:-python3}" helpers/input_identity.py \
                --check-completion "work/$replica/.$stage.identity.json" >/dev/null; then
                return 1
            fi
        done < work/states.tsv
        echo complete
    elif (( existing == 0 )) && [[ ! -e "work/.$stage.complete" && ! -L "work/.$stage.complete" ]]; then
        echo missing
    else
        echo partial
    fi
}

run_window_stage() {
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
        die "Partial $stage output retained in work. Files were preserved. Start a new tutorial copy."
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
        for output in "$replica_dir/$stage.out" "$replica_dir/$stage.rst7"; do
            if [[ ! -s "$output" ]]; then
                die "$stage output was not created: $output"
            fi
        done
        "${PYTHON:-python3}" helpers/input_identity.py \
            --finish-completion "$replica_dir/.$stage.identity.json" --directory "$replica_dir"
    done < work/states.tsv
    touch "work/.$stage.complete"
    echo "Completed: $stage (work)"
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
if (( replica_count < 2 || replica_count % 2 != 0 )); then
    die "Replica exchange requires at least two and an even number of states: work/states.tsv ($replica_count states)"
fi

if (( dry_run )); then
    echo "Dry run: planned REUS commands; no engine execution"
    echo "Preproduction engine cwd: work/000 (repeated for every replica)"
    printf '+ %q -O -i %q -o %q -p %q -c %q -r %q -x %q -inf %q\n' \
        "$amber_engine" minimize.in minimize.out \
        system.parm7 system.rst7 minimize.rst7 \
        minimize.nc minimize.info
    printf '+ %q -np %q %q -ng %q -groupfile %q -rem 3 -remlog %q\n' \
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
if find work/[0-9][0-9][0-9] -maxdepth 1 \
    \( -name 'production.out' -o -name 'production.rst7' \) \
    -print -quit 2>/dev/null | grep -q .; then
    die "Production output already exists in work."
fi

run_window_stage minimize system.rst7
run_window_stage heat minimize.rst7
run_window_stage equilibrate heat.rst7

production_identity=(--record work/.production-input.identity.json --stage "replica production inputs"
    --input work/states.tsv --value="$amber_mpi_engine" --output work/production.group --output work/exchange.log --output work/.production.complete)
while IFS=$'\t' read -r replica _; do
    if [[ "$replica" == replica ]]; then
        continue
    fi
    replica_dir="work/$replica"
    production_identity+=(--input "$replica_dir/system.parm7"
        --input "$replica_dir/equilibrate.rst7" --input "$replica_dir/production.template.in"
        --output "$replica_dir/production.out" --output "$replica_dir/production.rst7"
        --output "$replica_dir/production.nc" --output "$replica_dir/production.info")
    if [[ -s "$replica_dir/distance.RST" ]]; then
        production_identity+=(--input "$replica_dir/distance.RST" --output "$replica_dir/restraint.production.dat")
    fi
done < work/states.tsv
"${PYTHON:-python3}" helpers/input_identity.py "${production_identity[@]}"

for output in work/production.group work/exchange.log work/.production.complete \
    work/[0-9][0-9][0-9]/production.{out,rst7,nc,info} \
    work/[0-9][0-9][0-9]/restraint.production.dat; do
    if [[ -e "$output" || -L "$output" ]]; then
        die "Production output already exists or is partial: $output. Files were preserved. Start a new tutorial copy."
    fi
done

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
    "${PYTHON:-python3}" helpers/input_identity.py \
        --record "$replica_dir/.production.engine.identity.json" --stage "production engine input" \
        --input "$replica_dir/production.in" --input "$replica_dir/distance.RST" \
        --input "$replica_dir/system.parm7"
    echo "-O -i $replica_dir/production.in -o $replica_dir/production.out -p $replica_dir/system.parm7 -c $replica_dir/equilibrate.rst7 -r $replica_dir/production.rst7 -x $replica_dir/production.nc -inf $replica_dir/production.info" \
        >> "$group_file"
done < work/states.tsv

echo "Running: 1 ns REUS production"
if ! "$mpi_launcher" \
    -np "$replica_count" \
    "$amber_mpi_engine" \
    -ng "$replica_count" \
    -groupfile "$group_file" \
    -rem 3 \
    -remlog work/exchange.log; then
    die "REUS production failed. Inspect terminal output; expected diagnostics (if created): work/exchange.log and work/*/production.out"
fi

while IFS=$'\t' read -r replica _; do
    if [[ "$replica" == replica ]]; then
        continue
    fi
    for output in "work/$replica/production.out" "work/$replica/production.rst7" \
        "work/$replica/production.nc" "work/$replica/production.info"; do
        if [[ ! -s "$output" ]]; then
            die "Production output was not created: $output"
        fi
    done
done < work/states.tsv

touch work/.production.complete

echo "Completed 1 ns REUS: work"
