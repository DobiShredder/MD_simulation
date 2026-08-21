#!/usr/bin/env bash
set -euo pipefail

dry_run=0
preparation_only=0
production_only=0
segment_range=""
if [[ "${1:-}" == "-h" || "${1:-}" == "--help" ]]; then
    cat <<'EOF'
Usage: ./run.sh [--preparation-only | --production-only] [--segments START-END] [--dry-run]

Run AMBER preproduction and temperature replica-exchange production.

Options:
  --preparation-only  Run through equilibration and stop.
  --production-only   Run production from completed equilibration.
  --segments RANGE    Run an inclusive 1-based production segment range.
  --dry-run   Print representative AMBER and multipmemd commands.
  -h, --help  Show this help message and exit.
EOF
    exit 0
fi
while [[ $# -gt 0 ]]; do
    case "$1" in
        --preparation-only) preparation_only=1; shift ;;
        --production-only) production_only=1; shift ;;
        --segments)
            if [[ $# -lt 2 ]]; then
                echo "Error: --segments requires START-END." >&2
                exit 2
            fi
            segment_range=$2
            shift 2
            ;;
        --dry-run) dry_run=1; shift ;;
        *) echo "Error: unknown option: $1" >&2; exit 2 ;;
    esac
done
if (( preparation_only && production_only )); then
    echo "Error: --preparation-only and --production-only cannot be used together." >&2
    exit 2
fi

die() {
    echo "Error: $*" >&2
    exit 1
}

work_dir=${WORK_DIR:-work}
states_file="$work_dir/states.tsv"
resolved_config="$work_dir/resolved_config.toml"

read_value() {
    local key=$1
    awk -F' = ' -v key="$key" '$1 == key {gsub(/"/, "", $2); value=$2} END {print value}' \
        "$resolved_config"
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
        if [[ -s "$work_dir/$replica/$stage.out" && -s "$work_dir/$replica/$stage.rst7" ]]; then
            complete=$((complete + 1))
        fi
        if [[ -e "$work_dir/$replica/$stage.out" || -e "$work_dir/$replica/$stage.rst7" ]]; then
            existing=$((existing + 1))
        fi
    done < "$states_file"

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
    local replica_dir

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
        replica_dir="$work_dir/$replica"
        if ! "$amber_engine" \
            "${amber_options[@]}" \
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
    done < "$states_file"
}

write_group_file() {
    local segment_name=$1
    local input_restart=$2
    local group_file=$3
    local replica
    local replica_dir

    : > "$group_file"
    while IFS=$'\t' read -r replica _; do
        if [[ "$replica" == replica ]]; then
            continue
        fi
        replica_dir="$work_dir/$replica"
        echo "-O -i $replica_dir/production.in -o $replica_dir/$segment_name.out -p $replica_dir/system.parm7 -c $replica_dir/$input_restart -r $replica_dir/$segment_name.rst7 -x $replica_dir/$segment_name.nc -inf $replica_dir/$segment_name.info" \
            >> "$group_file"
    done < "$states_file"
}

if [[ ! -s "$states_file" || ! -s "$resolved_config" ]]; then
    die "Run ./build.sh first."
fi

amber_engine=${AMBER_ENGINE:-$(read_value engine)}
amber_mpi_engine=${AMBER_MPI_ENGINE:-$(read_value mpi_engine)}
mpi_launcher=${MPI_LAUNCHER:-mpirun}
production_segments=$(read_value production_segments)
segment_start=1
segment_end=$production_segments
if [[ -n "$segment_range" ]]; then
    if [[ ! "$segment_range" =~ ^([1-9][0-9]*)-([1-9][0-9]*)$ ]]; then
        die "--segments must use START-END"
    fi
    segment_start=${BASH_REMATCH[1]}; segment_end=${BASH_REMATCH[2]}
    if (( segment_start > segment_end || segment_end > production_segments )); then
        die "Segment range is outside 1-$production_segments"
    fi
fi
replica_count=$(awk 'NR > 1 {count++} END {print count + 0}' "$states_file")
mpi_processes=${MPI_PROCESSES:-$replica_count}
read -r -a mpi_options <<< "${MPI_OPTIONS:-}"
read -r -a amber_options <<< "${AMBER_OPTIONS:-}"

if [[ "$mpi_processes" -ne "$replica_count" ]]; then
    die "MPI_PROCESSES must equal the replica count: $replica_count"
fi

if (( dry_run )); then
    if (( ! production_only )); then
        printf '+ %q -O -i %q -o %q -p %q -c %q -r %q -x %q -inf %q\n' \
            "$amber_engine" "$work_dir/000/minimize.in" "$work_dir/000/minimize.out" \
            "$work_dir/000/system.parm7" "$work_dir/000/system.rst7" \
            "$work_dir/000/minimize.rst7" "$work_dir/000/minimize.nc" \
            "$work_dir/000/minimize.info"
    fi
    if (( ! preparation_only )); then
        for ((segment = segment_start; segment <= segment_end; segment++)); do
            printf -v segment_name 'production.%03d' "$segment"
            printf -v exchange_name 'exchange.%03d.log' "$segment"
            printf '+ %q -np %q %q -ng %q -groupfile %q -rem 1 -remlog %q\n' \
                "$mpi_launcher" "$replica_count" "$amber_mpi_engine" "$replica_count" \
                "$work_dir/$segment_name.group" "$work_dir/$exchange_name"
        done
    fi
    exit 0
fi

for executable in "$amber_engine" "$amber_mpi_engine" "$mpi_launcher"; do
    if ! command -v "$executable" >/dev/null 2>&1; then
        die "Executable not found: $executable"
    fi
done

if (( ! production_only )); then
    run_replica_stage minimize system.rst7
    run_replica_stage heat minimize.rst7
    run_replica_stage equilibrate heat.rst7
fi
if (( preparation_only )); then
    exit 0
fi
if [[ "$(stage_status equilibrate)" != complete ]]; then
    die "Completed equilibration output is required for production."
fi
if (( segment_start > 1 )); then
    printf -v previous_segment 'production.%03d' "$((segment_start - 1))"
    if [[ "$(stage_status "$previous_segment")" != complete ]]; then
        die "Previous production segment is incomplete: $previous_segment"
    fi
fi

for ((segment = segment_start; segment <= segment_end; segment++)); do
    printf -v segment_name 'production.%03d' "$segment"
    status=$(stage_status "$segment_name")
    if [[ "$status" == complete ]]; then
        continue
    fi
    if [[ "$status" == partial ]]; then
        die "Partial production output detected: $segment_name"
    fi

    if (( segment == 1 )); then
        input_restart=equilibrate.rst7
    else
        printf -v input_restart 'production.%03d.rst7' "$((segment - 1))"
    fi

    group_file="$work_dir/$segment_name.group"
    exchange_log="$work_dir/exchange.$(printf '%03d' "$segment").log"
    write_group_file "$segment_name" "$input_restart" "$group_file"

    echo "Running: T-REMD production segment $segment/$production_segments"
    if ! "$mpi_launcher" \
        "${mpi_options[@]}" \
        -np "$mpi_processes" \
        "$amber_mpi_engine" \
        "${amber_options[@]}" \
        -ng "$replica_count" \
        -groupfile "$group_file" \
        -rem 1 \
        -remlog "$exchange_log"; then
        die "T-REMD segment $segment failed: $exchange_log"
    fi
done

echo "Completed T-REMD production: $work_dir"
