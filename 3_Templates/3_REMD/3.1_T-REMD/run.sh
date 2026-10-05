#!/usr/bin/env bash
set -euo pipefail

original_args=("$@")

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
if (( ! ${dry_run:-0} )) && [[ ${MD_WRITER_PARENT:-} != "$PPID" || ${MD_WRITER_ENTRY:-} != "$0" ]]; then
    exec "${PYTHON:-python3}" helpers/writer_guard.py \
        --registry "$work_dir" --write "$work_dir" -- "$0" "${original_args[@]}"
fi
if (( ! dry_run )); then
    "${PYTHON:-python3}" helpers/input_identity.py --verify "$work_dir"
fi
states_file="$work_dir/states.tsv"
resolved_config="$work_dir/resolved_config.toml"

read_value() {
    local key=$1
    awk -F' = ' -v key="$key" '$1 == key {gsub(/"/, "", $2); value=$2} END {print value}' \
        "$resolved_config"
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
            if [[ ! -s "$work_dir/$replica/$stage.$suffix" ]]; then
                if [[ "$require_complete" == --require-complete ]]; then
                    die "$stage output is incomplete: $work_dir/$replica/$stage.$suffix; existing files were preserved."
                fi
                return 1
            fi
        done
    done < "$states_file"
    if [[ "$stage" == production.* && ! -s "$work_dir/exchange.${stage#production.}.log" ]]; then
        if [[ "$require_complete" == --require-complete ]]; then
            die "$stage output is incomplete: $work_dir/exchange.${stage#production.}.log; existing files were preserved."
        fi
        return 1
    fi
}

stage_status() {
    local stage=$1 replica suffix
    local marker="$work_dir/.$stage.complete"
    if [[ -f "$marker" ]] && stage_outputs_complete "$stage"; then
        echo complete
        return
    fi
    if [[ -e "$marker" ]]; then
        echo partial
        return
    fi
    if [[ "$stage" == production.* && -e "$work_dir/exchange.${stage#production.}.log" ]]; then
        echo partial
        return
    fi
    while IFS=$'\t' read -r replica _; do
        if [[ "$replica" == replica ]]; then
            continue
        fi
        for suffix in out rst7 nc info; do
            if [[ -e "$work_dir/$replica/$stage.$suffix" ]]; then
                echo partial
                return
            fi
        done
    done < "$states_file"
    echo missing
}

mark_stage_complete() {
    local stage=$1
    stage_outputs_complete "$stage" --require-complete
    touch "$work_dir/.$stage.complete"
    echo "Completed: $stage ($work_dir)"
}

check_stage_identity() {
    local stage=$1
    local input_restart=$2
    local input_name=$3
    local record_suffix=${4:-complete}
    local marker="$work_dir/.$stage.complete"
    local identity_options=(--input "$states_file" --input "$work_dir/system.parm7"
        --value="$amber_engine" --value="$amber_mpi_engine" --value "${AMBER_OPTIONS:-}")
    local replica replica_dir input_coordinates suffix
    while IFS=$'\t' read -r replica _; do
        if [[ "$replica" == replica ]]; then
            continue
        fi
        replica_dir="$work_dir/$replica"
        input_coordinates="$replica_dir/$input_restart"
        if [[ "$input_restart" == system.rst7 ]]; then
            input_coordinates="$work_dir/system.rst7"
        fi
        identity_options+=(--input "$replica_dir/$input_name" --input "$input_coordinates")
        if [[ "$stage" == heat ]]; then
            identity_options+=(--value="-ref=$input_coordinates")
        fi
        if [[ -s "$replica_dir/distance.RST" ]]; then
            identity_options+=(--input "$replica_dir/distance.RST")
        fi
        for suffix in out rst7 nc info; do
            identity_options+=(--output "$replica_dir/$stage.$suffix")
        done
        identity_options+=(--output "$replica_dir/restraint.$stage.dat" --output "$replica_dir/gamd.$stage.log")
    done < "$states_file"
    if [[ "$stage" == production.* ]]; then
        identity_options+=(--output "$work_dir/exchange.${stage#production.}.log")
    fi
    "${PYTHON:-python3}" helpers/input_identity.py \
        --record "$work_dir/.$stage.$record_suffix.identity.json" --stage "$stage" \
        --marker "$marker" "${identity_options[@]}"
}

run_replica_stage() {
    local stage=$1
    local input_restart=$2
    local status
    local replica
    local replica_dir

    check_stage_identity "$stage" "$input_restart" "$stage.in"
    status=$(stage_status "$stage")
    if [[ "$status" == complete ]]; then
        echo "Skipping completed stage: $stage"
        return
    fi
    if [[ "$status" == partial ]]; then
        die "Incomplete $stage outputs found in $work_dir; existing .out, .rst7, .nc, and .info files were preserved. Use a new WORK_DIR or resolve the partial stage."
    fi

    echo "Running: $stage"
    while IFS=$'\t' read -r replica _; do
        if [[ "$replica" == replica ]]; then
            continue
        fi
        replica_dir="$work_dir/$replica"
        input_coordinates="$replica_dir/$input_restart"
        if [[ "$input_restart" == "system.rst7" ]]; then
            input_coordinates="$work_dir/system.rst7"
        fi
        local reference=()
        if [[ "$stage" == heat ]]; then
            reference=(-ref "$input_coordinates")
        fi
        if ! "$amber_engine" \
            "${amber_options[@]}" \
            -O \
            -i "$replica_dir/$stage.in" \
            -o "$replica_dir/$stage.out" \
            -p "$work_dir/system.parm7" \
            -c "$input_coordinates" \
            -r "$replica_dir/$stage.rst7" \
            -x "$replica_dir/$stage.nc" \
            -inf "$replica_dir/$stage.info" "${reference[@]}"; then
            die "$stage failed: $replica_dir/$stage.out"
        fi
    done < "$states_file"
    mark_stage_complete "$stage"
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
        echo "-O -i $replica_dir/production.in -o $replica_dir/$segment_name.out -p $work_dir/system.parm7 -c $replica_dir/$input_restart -r $replica_dir/$segment_name.rst7 -x $replica_dir/$segment_name.nc -inf $replica_dir/$segment_name.info" \
            >> "$group_file"
    done < "$states_file"
}

if [[ ! -s "$states_file" || ! -s "$resolved_config" ]]; then
    die "Run ./build.sh first."
fi

amber_engine=$("${PYTHON:-python3}" helpers/config_utils.py "$resolved_config" engine AMBER_ENGINE pmemd.cuda)
amber_mpi_engine=$("${PYTHON:-python3}" helpers/config_utils.py "$resolved_config" mpi_engine AMBER_MPI_ENGINE pmemd.cuda.MPI)
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
if (( replica_count < 2 || replica_count % 2 != 0 )); then
    die "Replica exchange requires at least two and an even number of states: $states_file ($replica_count states)"
fi
mpi_processes=${MPI_PROCESSES:-$replica_count}
read -r -a mpi_options <<< "${MPI_OPTIONS:-}"
read -r -a amber_options <<< "${AMBER_OPTIONS:-}"

if [[ "$mpi_processes" -ne "$replica_count" ]]; then
    die "MPI_PROCESSES must equal the replica count: $replica_count"
fi

if (( dry_run )); then
    echo "Dry run: planned replica commands; no engine execution"
    if (( ! production_only )); then
        printf '+ %q -O -i %q -o %q -p %q -c %q -r %q -x %q -inf %q\n' \
            "$amber_engine" "$work_dir/000/minimize.in" "$work_dir/000/minimize.out" \
            "$work_dir/system.parm7" "$work_dir/system.rst7" \
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
    echo "Preparation output: $work_dir/<replica>/equilibrate.rst7"
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
    if (( segment == 1 )); then
        input_restart=equilibrate.rst7
    else
        printf -v input_restart 'production.%03d.rst7' "$((segment - 1))"
    fi
    check_stage_identity "$segment_name" "$input_restart" "production.in"
    status=$(stage_status "$segment_name")
    if [[ "$status" == complete ]]; then
        echo "Skipping completed stage: $segment_name ($work_dir)"
        continue
    fi
    if [[ "$status" == partial ]]; then
        die "Partial production output detected: $segment_name"
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
    mark_stage_complete "$segment_name"
done

echo "Completed T-REMD production: $work_dir"
