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

die() {
    echo "Error: $*" >&2
    exit 1
}

work_dir=work

if (( ! ${dry_run:-0} )) &&
        [[ ${original_args[0]:-} != -h && ${original_args[0]:-} != --help && ${original_args[0]:-} != --dry-run ]] &&
        [[ ${MD_WRITER_PARENT:-} != "$PPID" || ${MD_WRITER_ENTRY:-} != "$0" ]]; then
    exec "${PYTHON:-python3}" helpers/writer_guard.py \
        --registry "work" --read "inputs" --write "work" -- "$0" "${original_args[@]}"
fi

states_file="$work_dir/states.tsv"
engine=${AMBER_ENGINE:-pmemd.cuda}

if [[ ! -s "$states_file" ]]; then
    die "Run build.sh first: $states_file"
fi
if (( ! dry_run )) && ! command -v "$engine" >/dev/null 2>&1; then
    die "AMBER engine not found: $engine"
fi
if (( ! dry_run )) && [[ "$(basename "$engine")" != "pmemd.cuda" ]]; then
    die "ACES26 soft-core inputs must run with pmemd.cuda: $engine"
fi

if (( ! dry_run )); then
    "${PYTHON:-python3}" helpers/input_identity.py --verify "$work_dir"
fi

report_engine_failure() {
    local label=$1
    local exit_status=$2
    local output_file=$3
    local engine_log=$4
    local log_file
    for log_file in "$output_file" "$engine_log"; do
        if [[ -s "$log_file" ]]; then
            echo "Last 20 lines of $log_file:" >&2
            tail -n 20 "$log_file" >&2
        fi
    done
    die "$label calculation failed with exit status $exit_status: $output_file. Engine stdout/stderr: $engine_log"
}

report_partial_stage() {
    local label=$1
    local directory=$2
    local stage=$3
    local failed_dir="$work_dir.failed/${directory#"$work_dir"/}"
    local leftovers=()
    local path
    for path in "$directory/.$stage.success.json" "$directory/$stage".{out,rst7,info,nc}; do
        if [[ -e "$path" ]]; then
            leftovers+=("$path")
        fi
    done
    if (( ${#leftovers[@]} == 0 )); then
        die "$label completion check failed; see the message above: $directory"
    fi
    die "Partial $stage output is retained for $label: ${leftovers[*]}. Move these files out of $work_dir (for example: mkdir -p $failed_dir && mv ${leftovers[*]} $failed_dir/) and rerun ./run.sh."
}

run_stage() {
    local directory=$1
    local stage=$2
    local input_restart=$3
    local trajectory=$4
    local calculation=$5

    local output_file="$directory/$stage.out"
    local restart_file="$directory/$stage.rst7"
    local command=(
        "$engine" -O
        -i "$stage.in"
        -o "$stage.out"
        -p system.parm7
        -c "$input_restart"
        -r "$stage.rst7"
        -inf "$stage.info"
    )
    if [[ "$trajectory" == yes ]]; then
        command+=(-x "$stage.nc")
    fi

    if (( dry_run )); then
        printf '+ (cd %q && ' "$directory"
        printf '%q ' "${command[@]}"
        printf ')\n'
        return
    fi

    local identity_options=()
    if [[ -s "$directory/disang.rest" ]]; then
        identity_options+=(--input "$directory/disang.rest")
    fi
    "${PYTHON:-python3}" helpers/input_identity.py \
        --record "$directory/.$stage.identity.json" --stage "$calculation - $stage" \
        --directory "$directory" "${identity_options[@]}" -- "${command[@]}"

    local required=("$output_file" "$restart_file" "$directory/$stage.info")
    if [[ "$trajectory" == yes ]]; then
        required+=("$directory/$stage.nc")
    fi
    # Completed stages are reused and missing stages run. A stage with output but
    # no completion evidence stops the run; production is never overwritten.
    local output completion_state
    if ! completion_state=$("${PYTHON:-python3}" helpers/input_identity.py \
            --check-completion "$directory/.$stage.identity.json"); then
        report_partial_stage "$calculation" "$directory" "$stage"
    fi
    if [[ "$completion_state" == complete ]]; then
        reused_stage_count=$((reused_stage_count + 1))
        return
    fi

    # Engine stdout/stderr are appended per attempt beside $stage.out; the log is
    # not a stage output, so it never marks a window as partial.
    local engine_log="$directory/engine.$stage.log"
    {
        printf '== %s' "$(date '+%Y-%m-%d %H:%M:%S %Z')"
        printf ' %q' "${command[@]}"
        printf '\n'
    } >> "$engine_log"
    local engine_status=0
    (
        cd "$directory"
        "${command[@]}"
    ) >> "$engine_log" 2>&1 || engine_status=$?
    if (( engine_status != 0 )); then
        report_engine_failure "$calculation - $stage" "$engine_status" "$output_file" "$engine_log"
    fi
    for output in "${required[@]}"; do
        if [[ ! -s "$output" ]]; then
            die "$calculation - $stage output was not created: $output"
        fi
    done
    "${PYTHON:-python3}" helpers/input_identity.py \
        --finish-completion "$directory/.$stage.identity.json" --directory "$directory" \
        --required-output "$directory/$stage.info"

}

if (( dry_run )); then
    echo "Dry run: planned FEP commands; no engine execution"
fi

reused_stage_count=0
if (( ! dry_run )); then
    echo "Running: ABFE window workflows (minimization, heating, equilibration, production): work"
fi

while IFS=$'\t' read -r method_stage environment window lambda seed directory; do
    if [[ "$method_stage" == stage ]]; then
        continue
    fi
    interaction=${method_stage##*_}
    calculation="ABFE $interaction/$environment window $window (lambda=$lambda)"
    run_stage "$directory" minimize system.rst7 no "$calculation"
    run_stage "$directory" heat minimize.rst7 yes "$calculation"
    run_stage "$directory" equilibrate heat.rst7 yes "$calculation"
    run_stage "$directory" production equilibrate.rst7 yes "$calculation"
done < "$states_file"

if (( ! dry_run )); then
    if (( reused_stage_count > 0 )); then
        echo "Reused completed stages: $reused_stage_count (work)"
    fi
    echo "ABFE production completed: work/restraint, work/charge, work/vdw"
fi
