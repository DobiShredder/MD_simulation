#!/usr/bin/env bash
set -euo pipefail

dry_run=0
preparation_only=0
production_only=0
segment_range=""

while [[ $# -gt 0 ]]; do
    case "$1" in
        --dry-run)
            dry_run=1
            ;;
        --preparation-only)
            preparation_only=1
            ;;
        --production-only)
            production_only=1
            ;;
        --segments)
            if [[ $# -lt 2 ]]; then
                echo "Error: --segments requires START-END." >&2
                exit 2
            fi
            shift
            segment_range=$1
            ;;
        -h|--help)
            cat <<'EOF'
Usage: ./run.sh [--preparation-only | --production-only] [--segments START-END] [--dry-run]

Run preproduction, shared GaMD preparation, and AMBER GaREUS production.

Options:
  --preparation-only  Run through shared GaMD parameter preparation and stop.
  --production-only   Run exchange production from the completed GaMD state.
  --segments RANGE    Run an inclusive 1-based production segment range.
  --dry-run   Print the replica-exchange command without running it.
  -h, --help  Show this help message and exit.
EOF
            exit 0
            ;;
        *)
            echo "Usage: $0 [--dry-run]" >&2
            exit 2
            ;;
    esac
    shift
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
amber_engine=$("${PYTHON:-python3}" helpers/config_utils.py "$work_dir/resolved_config.toml" engine AMBER_ENGINE pmemd.cuda)
amber_mpi_engine=$("${PYTHON:-python3}" helpers/config_utils.py "$work_dir/resolved_config.toml" mpi_engine AMBER_MPI_ENGINE pmemd.cuda.MPI)
mpi_launcher=${MPI_LAUNCHER:-mpirun}

if [[ ! -s "$states_file" || ! -s "$work_dir/resolved_config.toml" ]]; then
    die "Run ./build.sh first."
fi

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
gamd_reference_replica=$(awk -F' = ' '$1 == "reference_replica" {value=$2} END {printf "%03d", value}' "$work_dir/resolved_config.toml")
gamd_reference_replica=${gamd_reference_replica:-000}
read -r -a mpi_options <<< "${MPI_OPTIONS:-}"
read -r -a amber_options <<< "${AMBER_OPTIONS:-}"

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

source helpers/completion_helpers.sh

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

        input_coordinates="$input_restart"
        if [[ "$input_restart" == "system.rst7" ]]; then
            input_coordinates="../system.rst7"
        fi

        if ! (
            cd "$replica_dir"
            "$amber_engine" \
                "${amber_options[@]}" \
                -O \
                -i "$stage.in" \
                -o "$stage.out" \
                -p ../system.parm7 \
                -c "$input_coordinates" \
                -r "$stage.rst7" \
                -x "$stage.nc" \
                -inf "$stage.info"
        ); then
            die "$stage Calculation failed: $replica_dir/$stage.out"
        fi
    done < "$states_file"
}

run_stage_if_needed() {
    local stage=$1
    local input_restart=$2
    local completed

    local status
    status=$(stage_state "$stage")
    if [[ "$status" == complete ]]; then
        echo "Skipping completed stage: $stage ($work_dir)"
        return
    fi
    if [[ "$status" == partial ]]; then
        die "Partial $stage output detected and retained in $work_dir. Use a new WORK_DIR or resolve the partial stage."
    fi
    run_stage "$stage" "$input_restart"

    completed=$(completed_stage_count "$stage" --require-complete)
    if [[ "$completed" -ne "$replica_count" ]]; then
        die "$stage output is incomplete in $work_dir ($completed/$replica_count)."
    fi
    touch "$work_dir/.$stage.complete"
    echo "Completed: $stage ($work_dir)"
}

prepare_common_gamd_state() {
    local reference_dir="$work_dir/$gamd_reference_replica"
    local output replica replica_dir
    local required=(
        "$reference_dir/gamd_prepare.out"
        "$reference_dir/gamd_prepare.rst7"
        "$reference_dir/gamd_prepare.nc"
        "$reference_dir/gamd_prepare.info"
        "$reference_dir/gamd.prepare.log"
        "$reference_dir/gamd-restart.dat"
    )
    local completion_marker="$work_dir/.gamd_prepare.complete"
    local existing=0
    local complete=0
    for output in "${required[@]}"; do
        if [[ -e "$output" ]]; then
            existing=$((existing + 1))
        fi
        if [[ -s "$output" ]]; then
            complete=$((complete + 1))
        fi
    done
    if [[ -f "$completion_marker" && "$complete" -eq "${#required[@]}" ]]; then
        while IFS=$'\t' read -r replica _; do
            if [[ "$replica" == replica ]]; then
                continue
            fi
            for output in gamd-restart.dat production_start.rst7; do
                if [[ ! -s "$work_dir/$replica/$output" ]]; then
                    die "Incomplete shared GaMD preparation: $work_dir/$replica/$output"
                fi
            done
        done < "$states_file"
        echo "Skipping completed stage: shared GaMD parameter preparation ($work_dir)"
        return
    fi
    if [[ -e "$completion_marker" || "$existing" -ne 0 ]]; then
        die "Partial GaMD preparation output retained: $reference_dir"
    fi
    while IFS=$'\t' read -r replica _; do
        if [[ "$replica" == replica ]]; then
            continue
        fi
        if [[ -e "$work_dir/$replica/gamd-restart.dat" || -e "$work_dir/$replica/production_start.rst7" ]]; then
            die "Unmarked GaMD preparation output retained: $work_dir/$replica"
        fi
    done < "$states_file"
    if (( production_only )); then
        die "Completed shared GaMD preparation required for production: $completion_marker"
    fi
    echo "Preparing shared GaMD parameters in replica $gamd_reference_replica."
    if ! (
        cd "$reference_dir"
        "$amber_engine" \
            "${amber_options[@]}" \
            -O \
            -i gamd_prepare.in \
            -o gamd_prepare.out \
            -p ../system.parm7 \
            -c equilibrate.rst7 \
            -r gamd_prepare.rst7 \
            -x gamd_prepare.nc \
            -inf gamd_prepare.info \
            -gamd gamd.prepare.log
    ); then
        die "GaMD parameter preparation failed: $reference_dir/gamd_prepare.out"
    fi
    for output in "${required[@]}"; do
        if [[ ! -s "$output" ]]; then
            die "GaMD preparation output is incomplete: $output"
        fi
    done
    while IFS=$'\t' read -r replica _; do
        if [[ "$replica" == replica ]]; then
            continue
        fi
        replica_dir="$work_dir/$replica"
        if [[ "$replica" != "$gamd_reference_replica" ]]; then
            cp "$reference_dir/gamd-restart.dat" "$replica_dir/gamd-restart.dat"
        fi
        cp "$replica_dir/equilibrate.rst7" "$replica_dir/production_start.rst7"
        if ! cmp -s "$reference_dir/gamd-restart.dat" "$replica_dir/gamd-restart.dat"; then
            die "Could not place the shared GaMD state in replica: $replica_dir"
        fi
    done < "$states_file"
    touch "$completion_marker"
    echo "Completed: shared GaMD parameter preparation ($work_dir)"
}

write_group_file() {
    local segment=$1
    local input_restart=$2
    local group_file=$3
    local segment_name
    local replica
    local replica_dir
    local dump_file
    local gamd_log
    local group_command

    segment_name=$(printf 'production.%03d' "$segment")
    : > "$group_file"

    while IFS=$'\t' read -r replica _; do
        if [[ "$replica" == "replica" ]]; then
            continue
        fi
        replica_dir="$work_dir/$replica"
        dump_file="$replica_dir/restraint.$segment_name.dat"
        gamd_log="$replica_dir/gamd.$segment_name.log"

        sed \
            -e "s|@DUMPAVE@|$dump_file|g" \
            "$replica_dir/production.template.in" \
            > "$replica_dir/$segment_name.in"

        group_command="-O -i $replica_dir/$segment_name.in"
        group_command+=" -o $replica_dir/$segment_name.out"
        group_command+=" -p $work_dir/system.parm7"
        group_command+=" -c $replica_dir/$input_restart"
        group_command+=" -r $replica_dir/$segment_name.rst7"
        group_command+=" -x $replica_dir/$segment_name.nc"
        group_command+=" -inf $replica_dir/$segment_name.info"
        group_command+=" -gamd $gamd_log"

        printf '%s\n' "$group_command" >> "$group_file"
    done < "$states_file"
}

if (( dry_run )); then
    echo "Dry run: planned GaREUS commands; no engine execution"
    echo "Engine: $amber_engine"
    echo "Replica exchange engine: $amber_mpi_engine"
    echo "$replica_count configured windows with one shared GaMD state"
    if (( ! production_only )); then
        printf '+ %q -O -i %q -o %q -p %q -c %q -r %q\n' \
            "$amber_engine" "$work_dir/000/minimize.in" \
            "$work_dir/000/minimize.out" "$work_dir/system.parm7" \
            "$work_dir/system.rst7" "$work_dir/000/minimize.rst7"
    fi
    if (( ! preparation_only )); then
        for ((segment = segment_start; segment <= segment_end; segment++)); do
            printf -v segment_name 'production.%03d' "$segment"
            printf '+'
            printf ' %q' \
                "$mpi_launcher" \
                "${mpi_options[@]}" \
                -np "$mpi_processes" \
                "$amber_mpi_engine" \
                "${amber_options[@]}" \
                -ng "$replica_count" \
                -groupfile "$work_dir/$segment_name.group" \
                -rem 3
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
prepare_common_gamd_state
if (( preparation_only )); then
    echo "Preparation output: $work_dir/<replica>/production_start.rst7 and gamd-restart.dat"
    exit 0
fi
if [[ ! -f "$work_dir/.gamd_prepare.complete" ]]; then
    die "Completed shared GaMD preparation is required for production."
fi
if (( segment_start > 1 )); then
    previous_segment=$(printf 'production.%03d' "$((segment_start - 1))")
    if [[ "$(stage_state "$previous_segment" --require-gamd-log)" != complete ]]; then
        die "Previous production segment is incomplete: $previous_segment"
    fi
fi

for segment in $(seq "$segment_start" "$segment_end"); do
    segment_name=$(printf 'production.%03d' "$segment")
    status=$(stage_state "$segment_name" --require-gamd-log)
    if [[ "$status" == complete ]]; then
        echo "Skipping completed stage: $segment_name ($work_dir)"
        continue
    fi
    if [[ "$status" == partial ]]; then
        die "Partial production output detected and retained: $work_dir/$segment_name"
    fi
    if [[ "$segment" -eq 1 ]]; then
        input_restart=production_start.rst7
    else
        input_restart=$(printf 'production.%03d.rst7' "$((segment - 1))")
    fi

    group_file="$work_dir/$segment_name.group"
    exchange_log="$work_dir/exchange.$(printf '%03d' "$segment").log"
    write_group_file "$segment" "$input_restart" "$group_file"

    echo "Running GaREUS production segment $segment/$production_segments."

    if ! "$mpi_launcher" \
        "${mpi_options[@]}" \
        -np "$mpi_processes" \
        "$amber_mpi_engine" \
        "${amber_options[@]}" \
        -ng "$replica_count" \
        -groupfile "$group_file" \
        -rem 3 \
        -remlog "$exchange_log"; then
        die "GaREUS segment $segment Run failed: $exchange_log"
    fi

    completed=$(completed_stage_count "$segment_name" --require-gamd-log --require-complete)
    if [[ "$completed" -ne "$replica_count" ]]; then
        die "$segment_name output is incomplete in $work_dir ($completed/$replica_count)."
    fi
    if [[ ! -s "$exchange_log" ]]; then
        die "$segment_name exchange log was not created: $exchange_log"
    fi
    touch "$work_dir/.$segment_name.complete"
    echo "Completed: $segment_name ($work_dir)"
done

echo "Completed GaREUS production: $work_dir"
