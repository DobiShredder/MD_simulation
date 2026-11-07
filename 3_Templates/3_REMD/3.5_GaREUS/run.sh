#!/usr/bin/env bash
set -euo pipefail

original_args=("$@")

dry_run=0
allow_unverified=0
preparation_only=0
production_only=0
segment_range=""

show_help() {
    cat <<'EOF'
Usage: ./run.sh --allow-unverified [--preparation-only | --production-only] [--segments START-END]
       ./run.sh --dry-run [--preparation-only | --production-only] [--segments START-END]

Run preproduction, shared GaMD preparation, and AMBER GaREUS production.

Options:
  --allow-unverified  Opt in to actual execution. Per-replica GaMD state
                      handling (gamd-restart.dat) with Amber 26 multipmemd is
                      unverified; see README.md.
  --preparation-only  Run through shared GaMD parameter preparation and stop.
  --production-only   Run exchange production from the completed GaMD state.
  --segments RANGE    Run an inclusive 1-based production segment range.
  --dry-run   Print the replica-exchange command without running it.
  -h, --help  Show this help message and exit.
EOF
}

while [[ $# -gt 0 ]]; do
    case "$1" in
        --dry-run)
            dry_run=1
            ;;
        --allow-unverified)
            allow_unverified=1
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
            show_help
            exit 0
            ;;
        *)
            echo "Error: unknown option: $1" >&2
            show_help >&2
            exit 2
            ;;
    esac
    shift
done
if (( preparation_only && production_only )); then
    echo "Error: --preparation-only and --production-only cannot be used together." >&2
    exit 2
fi
# gamd-restart.dat has a fixed filename; whether Amber 26 multipmemd reads and
# writes it separately for each replica is unverified, so execution is opt-in.
if (( ! dry_run && ! allow_unverified )); then
    echo "Error: actual execution requires ./run.sh --allow-unverified." >&2
    echo "Per-replica GaMD state handling with Amber 26 multipmemd is unverified; see README.md before opting in." >&2
    exit 2
fi

die() {
    echo "Error: $*" >&2
    exit 1
}

work_dir=${WORK_DIR:-work}
rerun_command="./run.sh ${original_args[*]:-}"
rerun_command=${rerun_command% }
if (( ! ${dry_run:-0} )) && [[ ${MD_WRITER_PARENT:-} != "$PPID" || ${MD_WRITER_ENTRY:-} != "$0" ]]; then
    exec "${PYTHON:-python3}" helpers/writer_guard.py \
        --registry "$work_dir" --write "$work_dir" -- "$0" "${original_args[@]}"
fi
if (( ! dry_run )); then
    "${PYTHON:-python3}" helpers/input_identity.py --verify "$work_dir"
fi
states_file="$work_dir/states.tsv"
if [[ ! -s "$work_dir/resolved_config.toml" ]]; then
    die "Run ./build.sh first: $work_dir/resolved_config.toml"
fi
if [[ ! -s "$states_file" ]]; then
    die "Run ./build.sh first: $states_file"
fi
# build.sh writes build.done only after every build step and check passes.
if [[ ! -f "$work_dir/build.done" ]]; then
    die "Build did not complete: $work_dir/build.done is missing; see the ./build.sh error output and $work_dir/tleap.stdout.log. Move $work_dir aside (for example: mv $work_dir $work_dir.old) and rerun ./build.sh."
fi
amber_engine=$("${PYTHON:-python3}" helpers/config_utils.py "$work_dir/resolved_config.toml" engine AMBER_ENGINE pmemd.cuda)
amber_mpi_engine=$("${PYTHON:-python3}" helpers/config_utils.py "$work_dir/resolved_config.toml" mpi_engine AMBER_MPI_ENGINE pmemd.cuda.MPI)
mpi_launcher=${MPI_LAUNCHER:-mpirun}

replica_count=$(awk 'NR > 1 {count++} END {print count + 0}' "$states_file")
if (( replica_count < 2 || replica_count % 2 != 0 )); then
    die "Replica exchange requires at least two and an even number of states: $states_file ($replica_count states)"
fi
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

# Paths written by one stage, including its completion marker.
stage_candidates() {
    local stage=$1
    local replica
    if [[ "$stage" == shared_* ]]; then
        printf '%s\n' "$work_dir/.$stage.complete" "$work_dir/shared/${stage#shared_}."{out,rst7,nc,info}
        return
    fi
    if [[ "$stage" == gamd_prepare ]]; then
        printf '%s\n' "$work_dir/.gamd_prepare.complete" \
            "$work_dir/$gamd_reference_replica/"{gamd_prepare.out,gamd_prepare.rst7,gamd_prepare.nc,gamd_prepare.info,gamd.prepare.log}
        while IFS=$'\t' read -r replica _; do
            if [[ "$replica" != replica ]]; then
                printf '%s\n' "$work_dir/$replica/"{gamd-restart.dat,production_start.rst7,prepared.gamd.rst}
            fi
        done < "$states_file"
        return
    fi
    printf '%s\n' "$work_dir/.$stage.complete"
    if [[ "$stage" == production.* ]]; then
        printf '%s\n' "$work_dir/exchange.${stage#production.}.log"
    fi
    while IFS=$'\t' read -r replica _; do
        if [[ "$replica" == replica ]]; then
            continue
        fi
        printf '%s\n' "$work_dir/$replica/$stage."{out,rst7,nc,info,gamd.rst} \
            "$work_dir/$replica/restraint.$stage.dat" "$work_dir/$replica/gamd.$stage.log"
    done < "$states_file"
}

# Retained output is never moved here; print the manual recovery instead.
# All windows of a stage rerun together, so the list spans every window.
die_partial() {
    local stage=$1
    local label=${stage/#shared_/shared }
    local path
    local retained=()
    while IFS= read -r path; do
        if [[ -e "$path" || -L "$path" ]]; then
            retained+=("$path")
        fi
    done < <(stage_candidates "$stage")
    die "Partial $label output is retained in $work_dir. Move these files out of $work_dir, keeping their directories, and rerun $rerun_command:
  for file in ${retained[*]:-}; do mkdir -p \"$work_dir.failed/\${file%/*}\"; mv \"\$file\" \"$work_dir.failed/\$file\"; done"
}

# After a failed multipmemd run, show the MPI log and windows whose AMBER
# output lacks the final timing block.
report_replica_failure() {
    local stage=$1
    local mpirun_log=$2
    local replica output
    if [[ -s "$mpirun_log" ]]; then
        echo "Last 20 lines of $mpirun_log:" >&2
        tail -n 20 "$mpirun_log" >&2
    fi
    while IFS=$'\t' read -r replica _; do
        if [[ "$replica" == replica ]]; then
            continue
        fi
        output="$work_dir/$replica/$stage.out"
        if [[ ! -s "$output" ]]; then
            echo "Missing window output: $output" >&2
        elif ! grep -q 'Total wall time' "$output"; then
            echo "Unfinished window output: $output" >&2
        fi
    done < "$states_file"
}

# Run COMMAND in ENGINE_DIR and append its stdout/stderr to ENGINE_LOG, one
# header line per attempt. The log is a diagnostic beside <stage>.out, not a
# stage output.
run_engine() {
    local engine_log=$1
    local engine_dir=$2
    shift 2
    echo "== $(date '+%Y-%m-%d %H:%M:%S') $*" >> "$engine_log"
    if (
        cd "$engine_dir"
        "$@"
    ) >> "$engine_log" 2>&1; then
        return 0
    fi
    echo "Engine log: $engine_log" >&2
    echo "Last 20 lines of $engine_log:" >&2
    tail -n 20 "$engine_log" >&2
    return 1
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
        if [[ -s "$replica_dir/distance.RST" ]]; then
            identity_options+=(--input "$replica_dir/distance.RST")
        fi
        for suffix in out rst7 nc info; do
            identity_options+=(--output "$replica_dir/$stage.$suffix")
        done
        identity_options+=(--output "$replica_dir/restraint.$stage.dat" --output "$replica_dir/gamd.$stage.log")
        if [[ "$stage" == production.* ]]; then
            identity_options+=(--input "$replica_dir/$input_gamd_state" --output "$replica_dir/$stage.gamd.rst")
        fi
    done < "$states_file"
    if [[ "$stage" == production.* ]]; then
        identity_options+=(--output "$work_dir/exchange.${stage#production.}.log")
    fi
    "${PYTHON:-python3}" helpers/input_identity.py \
        --record "$work_dir/.$stage.$record_suffix.identity.json" --stage "$stage" \
        --marker "$marker" "${identity_options[@]}"
}

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

        if ! run_engine "$replica_dir/engine.$stage.log" "$replica_dir" \
            "$amber_engine" \
            "${amber_options[@]}" \
            -O \
            -i "$stage.in" \
            -o "$stage.out" \
            -p ../system.parm7 \
            -c "$input_coordinates" \
            -r "$stage.rst7" \
            -x "$stage.nc" \
            -inf "$stage.info"; then
            die "$stage Calculation failed: $replica_dir/$stage.out"
        fi
    done < "$states_file"
}

run_stage_if_needed() {
    local stage=$1
    local input_restart=$2
    local completed

    local status
    check_stage_identity "$stage" "$input_restart" "$stage.in"
    status=$(stage_state "$stage")
    if [[ "$status" == complete ]]; then
        echo "Skipping completed stage: $stage ($work_dir)"
        return
    fi
    if [[ "$status" == partial ]]; then
        die_partial "$stage"
    fi
    run_stage "$stage" "$input_restart"

    completed=$(completed_stage_count "$stage" --require-complete)
    if [[ "$completed" -ne "$replica_count" ]]; then
        die "$stage output is incomplete in $work_dir ($completed/$replica_count)."
    fi
    touch "$work_dir/.$stage.complete"
    echo "Completed: $stage ($work_dir)"
}

shared_outputs_complete() {
    local stage=$1 suffix
    local require_complete=${2:-}
    local required=(out rst7 info)
    if [[ "$stage" != minimize ]]; then
        required+=(nc)
    fi
    for suffix in "${required[@]}"; do
        if [[ ! -s "$work_dir/shared/$stage.$suffix" ]]; then
            if [[ "$require_complete" == --require-complete ]]; then
                die "shared $stage output is incomplete: $work_dir/shared/$stage.$suffix; existing files were preserved."
            fi
            return 1
        fi
    done
}

shared_stage_state() {
    local stage=$1 output
    local marker="$work_dir/.shared_$stage.complete"
    if [[ -f "$marker" ]] && shared_outputs_complete "$stage"; then
        echo complete
        return
    fi
    if [[ -e "$marker" ]]; then
        echo partial
        return
    fi
    for output in "$work_dir/shared/$stage."{out,rst7,nc,info}; do
        if [[ -e "$output" ]]; then
            echo partial
            return
        fi
    done
    echo missing
}

# The unbiased system runs once at constant pressure; every window starts
# from this box, so NVT exchange uses one volume (Amber26 manual, REMD).
run_shared_stage_if_needed() {
    local stage=$1
    local input_restart=$2
    local shared_dir="$work_dir/shared"
    local status
    "${PYTHON:-python3}" helpers/input_identity.py \
        --record "$shared_dir/.$stage.identity.json" --stage "shared $stage" \
        --directory "$shared_dir" --marker "$work_dir/.shared_$stage.complete" \
        --value "${AMBER_OPTIONS:-}" -- "$amber_engine" \
        -O -i "$stage.in" -o "$stage.out" -p ../system.parm7 -c "$input_restart" \
        -r "$stage.rst7" -x "$stage.nc" -inf "$stage.info"

    status=$(shared_stage_state "$stage")
    if [[ "$status" == complete ]]; then
        echo "Skipping completed stage: shared $stage ($work_dir)"
        return
    fi
    if [[ "$status" == partial ]]; then
        die_partial "shared_$stage"
    fi

    echo "Running shared $stage stage."
    if ! run_engine "$shared_dir/engine.$stage.log" "$shared_dir" \
        "$amber_engine" \
        "${amber_options[@]}" \
        -O \
        -i "$stage.in" \
        -o "$stage.out" \
        -p ../system.parm7 \
        -c "$input_restart" \
        -r "$stage.rst7" \
        -x "$stage.nc" \
        -inf "$stage.info"; then
        die "shared $stage Calculation failed: $shared_dir/$stage.out"
    fi
    shared_outputs_complete "$stage" --require-complete
    touch "$work_dir/.shared_$stage.complete"
    echo "Completed: shared $stage ($work_dir)"
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
    local identity_options=(--input "$work_dir/system.parm7"
        --input "$reference_dir/gamd_prepare.in" --input "$reference_dir/equilibrate.rst7"
        --value="$gamd_reference_replica" --value="$amber_engine" --value "${AMBER_OPTIONS:-}")
    for output in "${required[@]}"; do
        identity_options+=(--output "$output")
    done
    while IFS=$'\t' read -r replica _; do
        if [[ "$replica" != replica ]]; then
            identity_options+=(--input "$work_dir/$replica/equilibrate.rst7"
                --output "$work_dir/$replica/production_start.rst7"
            --output "$work_dir/$replica/gamd-restart.dat" --output "$work_dir/$replica/prepared.gamd.rst")
        fi
    done < "$states_file"
    "${PYTHON:-python3}" helpers/input_identity.py \
        --record "$completion_marker.identity.json" --stage gamd_prepare \
        --marker "$completion_marker" "${identity_options[@]}"

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
        die_partial gamd_prepare
    fi
    while IFS=$'\t' read -r replica _; do
        if [[ "$replica" == replica ]]; then
            continue
        fi
        if [[ -e "$work_dir/$replica/gamd-restart.dat" || -e "$work_dir/$replica/production_start.rst7" ]]; then
            die_partial gamd_prepare
        fi
    done < "$states_file"
    if (( production_only )); then
        die "Completed shared GaMD preparation required for production: $completion_marker"
    fi
    echo "Preparing shared GaMD parameters in replica $gamd_reference_replica."
    if ! run_engine "$reference_dir/engine.gamd_prepare.log" "$reference_dir" \
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
        -gamd gamd.prepare.log; then
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
        cp "$replica_dir/gamd-restart.dat" "$replica_dir/prepared.gamd.rst"
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

        # The group file runs from this directory, so restraint paths include work_dir.
        sed \
            -e "s|@DISANG@|$replica_dir/distance.RST|g" \
            -e "s|@DUMPAVE@|$dump_file|g" \
            "$replica_dir/$segment_name.template.in" \
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
        # Shared stages run once in work/shared; windows then start from its NPT box.
        printf '+ cd %q && %q -O -i minimize.in -o minimize.out -p ../system.parm7 -c ../system.rst7 -r minimize.rst7 -x minimize.nc -inf minimize.info\n' \
            "$work_dir/shared" "$amber_engine"
        printf '+ cd %q && %q -O -i equilibrate.in -o equilibrate.out -p ../system.parm7 -c ../shared/equilibrate.rst7 -r equilibrate.rst7 -x equilibrate.nc -inf equilibrate.info\n' \
            "$work_dir/000" "$amber_engine"
        printf '+ cd %q && %q -O -i gamd_prepare.in -o gamd_prepare.out -p ../system.parm7 -c equilibrate.rst7 -r gamd_prepare.rst7 -x gamd_prepare.nc -inf gamd_prepare.info -gamd gamd.prepare.log\n' \
            "$work_dir/$gamd_reference_replica" "$amber_engine"
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
    run_shared_stage_if_needed minimize ../system.rst7
    run_shared_stage_if_needed heat minimize.rst7
    run_shared_stage_if_needed equilibrate heat.rst7

    run_stage_if_needed equilibrate ../shared/equilibrate.rst7
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
    if [[ "$segment" -eq 1 ]]; then
        input_restart=production_start.rst7
    else
        input_restart=$(printf 'production.%03d.rst7' "$((segment - 1))")
    fi
    if [[ "$segment" -eq 1 ]]; then
        input_gamd_state=prepared.gamd.rst
    else
        printf -v input_gamd_state 'production.%03d.gamd.rst' "$((segment - 1))"
    fi
    check_stage_identity "$segment_name" "$input_restart" "$segment_name.template.in"
    status=$(stage_state "$segment_name" --require-gamd-log)
    if [[ "$status" == complete ]]; then
        echo "Skipping completed stage: $segment_name ($work_dir)"
        continue
    fi
    if [[ "$status" == partial ]]; then
        die_partial "$segment_name"
    fi

    group_file="$work_dir/$segment_name.group"
    exchange_log="$work_dir/exchange.$(printf '%03d' "$segment").log"
    write_group_file "$segment" "$input_restart" "$group_file"
    check_stage_identity "$segment_name" "$input_restart" "$segment_name.in" engine

    while IFS=$'	' read -r replica _; do
        if [[ "$replica" != replica ]]; then
            cp "$work_dir/$replica/$input_gamd_state" "$work_dir/$replica/gamd-restart.dat"
        fi
    done < "$states_file"
    mpirun_log="$work_dir/mpirun.$segment_name.log"
    echo "Running GaREUS production segment $segment/$production_segments (MPI output: $mpirun_log)."

    if ! "$mpi_launcher" \
        "${mpi_options[@]}" \
        -np "$mpi_processes" \
        "$amber_mpi_engine" \
        "${amber_options[@]}" \
        -ng "$replica_count" \
        -groupfile "$group_file" \
        -rem 3 \
        -remlog "$exchange_log" \
        >> "$mpirun_log" 2>&1; then
        report_replica_failure "$segment_name" "$mpirun_log"
        die "GaREUS segment $segment failed: $mpirun_log, $exchange_log"
    fi

    completed=$(completed_stage_count "$segment_name" --require-gamd-log --require-complete)
    if [[ "$completed" -ne "$replica_count" ]]; then
        die "$segment_name output is incomplete in $work_dir ($completed/$replica_count)."
    fi
    if [[ ! -s "$exchange_log" ]]; then
        die "$segment_name exchange log was not created: $exchange_log"
    fi
    while IFS=$'	' read -r replica _; do
        if [[ "$replica" != replica ]]; then
            if [[ ! -s "$work_dir/$replica/gamd-restart.dat" ]]; then
                die "GaMD continuation state missing: $work_dir/$replica/gamd-restart.dat"
            fi
            cp "$work_dir/$replica/gamd-restart.dat" "$work_dir/$replica/$segment_name.gamd.rst"
        fi
    done < "$states_file"
    touch "$work_dir/.$segment_name.complete"
    echo "Completed: $segment_name ($work_dir)"
done

echo "Completed GaREUS production: $work_dir"
