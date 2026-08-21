#!/usr/bin/env bash
set -euo pipefail

dry_run=0
preparation_only=0
production_only=0
segment_range=""
while [[ $# -gt 0 ]]; do
case "$1" in
    --dry-run) dry_run=1; shift ;;
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
    -h|--help)
        cat <<'EOF'
Usage: ./run.sh [--preparation-only | --production-only] [--segments START-END] [--dry-run]

Run preproduction for every window and AMBER multidimensional REUS production.

Options:
  --preparation-only  Run every window through equilibration and stop.
  --production-only   Run exchange production from completed equilibration.
  --segments RANGE    Run an inclusive 1-based production segment range.
  --dry-run      Print the replica-exchange command without running it.
  -h, --help     Show this help message and exit.
EOF
        exit 0
        ;;
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
amber_engine=${AMBER_ENGINE:-pmemd.cuda}
amber_mpi_engine=${AMBER_MPI_ENGINE:-pmemd.cuda.MPI}
mpi_launcher=${MPI_LAUNCHER:-mpirun}
replica_count=$(awk 'NR > 1 {count++} END {print count + 0}' "$states_file")
mpi_processes=${MPI_PROCESSES:-$replica_count}
production_segments=$(awk -F' = ' '$1 == "production_segments" {value=$2} END {print value}' "$work_dir/resolved_config.toml")
production_segments=${production_segments:-1}
segment_start=1; segment_end=$production_segments
if [[ -n "$segment_range" ]]; then
    if [[ ! "$segment_range" =~ ^([1-9][0-9]*)-([1-9][0-9]*)$ ]]; then
        die "--segments must use START-END"
    fi
    segment_start=${BASH_REMATCH[1]}
    segment_end=${BASH_REMATCH[2]}
    if (( segment_start > segment_end || segment_end > production_segments )); then
        die "Segment range is outside 1-$production_segments"
    fi
fi

read -r -a mpi_options <<< "${MPI_OPTIONS:-}"
read -r -a amber_options <<< "${AMBER_OPTIONS:-}"

if [[ ! -s "$states_file" ]]; then
    die "Run build.sh first: $states_file"
fi
if [[ "$mpi_processes" -ne "$replica_count" ]]; then
    die "MPI_PROCESSES must equal the window count: $replica_count"
fi

if (( ! dry_run )); then
    for executable in "$amber_engine" "$amber_mpi_engine" "$mpi_launcher"; do
        if ! command -v "$executable" >/dev/null 2>&1; then
            die "Executable not found: $executable"
        fi
    done
fi

source completion_helpers.sh

run_stage() {
    local stage=$1
    local input_restart=$2
    local replica
    local replica_dir

    echo "Running $stage stage."

    while IFS=$'\t' read -r replica _; do
        if [[ "$replica" == "replica" ]]; then
            continue
        fi
        replica_dir="$work_dir/$replica"

        if ! (
            cd "$replica_dir"
            "$amber_engine" \
                "${amber_options[@]}" \
                -O \
                -i "$stage.in" \
                -o "$stage.out" \
                -p system.parm7 \
                -c "$input_restart" \
                -r "$stage.rst7" \
                -x "$stage.nc" \
                -inf "$stage.info"
        ); then
            die "$stage Calculation failed: $replica_dir/$stage.out"
        fi
    done < "$states_file"
    mark_stage_complete "$stage"
}

run_stage_if_needed() {
    local stage=$1
    local input_restart=$2
    local state
    state=$(stage_state "$stage")
    if [[ "$state" == complete ]]; then
        return
    fi
    if [[ "$state" == partial ]]; then
        echo "Warning: removing partial $stage output from all windows and restarting the stage." >&2
        remove_stage_outputs "$stage"
    fi
    run_stage "$stage" "$input_restart"
}

write_group_file() {
    local segment=$1
    local input_restart=$2
    local group_file=$3
    local segment_name
    local replica
    local replica_dir
    local dump_file

    segment_name=$(printf 'production.%03d' "$segment")
    : > "$group_file"

    while IFS=$'\t' read -r replica _; do
        if [[ "$replica" == "replica" ]]; then
            continue
        fi
        replica_dir="$work_dir/$replica"
        dump_file="$replica_dir/restraint.$segment_name.dat"

        sed \
            -e "s|@DUMPAVE@|$dump_file|g" \
            "$replica_dir/production.template.in" \
            > "$replica_dir/$segment_name.in"

        printf '%s\n' \
            "-O -i $replica_dir/$segment_name.in -o $replica_dir/$segment_name.out -p $replica_dir/system.parm7 -c $replica_dir/$input_restart -r $replica_dir/$segment_name.rst7 -x $replica_dir/$segment_name.nc -inf $replica_dir/$segment_name.info" \
            >> "$group_file"
    done < "$states_file"
}

if (( dry_run )); then
    echo "Engine: $amber_engine"
    echo "Replica exchange engine: $amber_mpi_engine"
    echo "$replica_count configured windows"
    if (( ! production_only )); then
        printf '+ %q -O -i %q -o %q -p %q -c %q -r %q\n' \
            "$amber_engine" "$work_dir/000/minimize.in" \
            "$work_dir/000/minimize.out" "$work_dir/000/system.parm7" \
            "$work_dir/000/system.rst7" "$work_dir/000/minimize.rst7"
    fi
    if (( ! preparation_only )); then
        for ((segment = segment_start; segment <= segment_end; segment++)); do
            printf -v segment_name 'production.%03d' "$segment"
            printf '+'
            printf ' %q' "$mpi_launcher" "${mpi_options[@]}" -np "$mpi_processes" "$amber_mpi_engine" "${amber_options[@]}" -ng "$replica_count" -groupfile "$work_dir/$segment_name.group" -rem 3
            printf '\n'
        done
    fi
    exit 0
fi

if (( ! production_only )); then
    run_stage_if_needed minimize system.rst7
    run_stage_if_needed heat minimize.rst7
    run_stage_if_needed equilibrate heat.rst7
fi
if (( preparation_only )); then
    exit 0
fi
if [[ "$(stage_state equilibrate)" != complete ]]; then
    die "Completed equilibration output is required for production."
fi
if (( segment_start > 1 )); then
    previous_segment=$(printf 'production.%03d' "$((segment_start - 1))")
    if [[ "$(stage_state "$previous_segment")" != complete ]]; then
        die "Previous production segment is incomplete: $previous_segment"
    fi
fi

for segment in $(seq "$segment_start" "$segment_end"); do
    segment_name=$(printf 'production.%03d' "$segment")
    state=$(stage_state "$segment_name")
    if [[ "$state" == complete ]]; then
        continue
    fi
    if [[ "$state" == partial ]]; then
        die "Partial production output detected: $segment_name"
    fi

    if [[ "$segment" -eq 1 ]]; then
        input_restart=equilibrate.rst7
    else
        input_restart=$(printf 'production.%03d.rst7' "$((segment - 1))")
    fi

    group_file="$work_dir/$segment_name.group"
    exchange_log="$work_dir/exchange.$(printf '%03d' "$segment").log"
    write_group_file "$segment" "$input_restart" "$group_file"

    echo "Running REUS production segment $segment/$production_segments."

    if ! "$mpi_launcher" \
        "${mpi_options[@]}" \
        -np "$mpi_processes" \
        "$amber_mpi_engine" \
        "${amber_options[@]}" \
        -ng "$replica_count" \
        -groupfile "$group_file" \
        -rem 3 \
        -remlog "$exchange_log"; then
        die "REUS segment $segment Run failed: $exchange_log"
    fi
    mark_stage_complete "$segment_name"
done

echo "Completed REUS production: $work_dir"
