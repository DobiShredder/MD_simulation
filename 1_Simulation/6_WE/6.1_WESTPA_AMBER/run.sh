#!/usr/bin/env bash
set -euo pipefail

original_args=("$@")

source ./env.sh

dry_run=0
if [[ "${1:-}" == "--dry-run" && $# -eq 1 ]]; then
    dry_run=1
elif [[ $# -ne 0 ]]; then
    echo "Usage: $0 [--dry-run]" >&2
    exit 2
fi

if (( dry_run )); then
    echo "Dry run: planned WESTPA command; no iteration execution"
    printf '+ w_run --work-manager serial >> %q 2>&1\n' "$WORK_DIR/west.log"
    exit 0
fi

if [[ ${MD_WRITER_PARENT:-} != "$PPID" || ${MD_WRITER_ENTRY:-} != "$0" ]]; then
    exec "${PYTHON:-python3}" helpers/writer_guard.py \
        --registry "$WORK_DIR" --read "inputs" --read "bstates" --read "tstate.file" --read "west.cfg" --write "$WORK_DIR" -- "$0" "${original_args[@]}"
fi

"${PYTHON:-python3}" helpers/input_identity.py --westpa-records "$WORK_DIR"
"${PYTHON:-python3}" helpers/input_identity.py \
    --record "$WORK_DIR/.we-input.identity.json" --stage "WESTPA immutable inputs" \
    --input "$WORK_DIR/common_files/system.parm7" --input "$WORK_DIR/common_files/reference.rst7" \
    --input "$WORK_DIR/bstates/basis.rst7" --input bstates/bstates.txt --input tstate.file \
    --input west.cfg --input inputs/segment.in.template \
    --input westpa_scripts/runseg.sh --input westpa_scripts/get_pcoord.sh --input westpa_scripts/calc_pcoord.sh \
    --output "$WORK_DIR/west.h5" --output "$WORK_DIR/west.log"

if [[ ! -s "$WORK_DIR/west.h5" ]]; then
    echo "Error: Run init.sh first: $WORK_DIR/west.h5" >&2
    exit 1
fi

for executable in w_run "$AMBER_ENGINE" "$CPPTRAJ"; do
    if ! command -v "$executable" >/dev/null 2>&1; then
        echo "Error: executable not found: $executable" >&2
        exit 1
    fi
done

requested_iteration=$(awk '/^[[:space:]]*max_total_iterations:/ {print $2; exit}' west.cfg)
if [[ ! "$requested_iteration" =~ ^[1-9][0-9]*$ ]]; then
    echo "Error: could not read max_total_iterations: west.cfg" >&2
    exit 1
fi

# Print this run's WESTPA log section and the newest segment log, then stop.
report_westpa_failure() {
    local message=$1
    echo "Last 20 lines of this run in $west_log:" >&2
    tail -n "+$log_start_line" "$west_log" | tail -n 20 >&2
    # Segment logs are named ITERATION-SEGMENT, so the last name is the newest.
    local segment_logs=("$WORK_DIR"/seg_logs/*.log)
    local latest_segment_log=${segment_logs[${#segment_logs[@]}-1]}
    if [[ -f "$latest_segment_log" ]]; then
        echo "Last 20 lines of the most recent segment log $latest_segment_log:" >&2
        tail -n 20 "$latest_segment_log" >&2
    fi
    echo "Error: $message: $west_log" >&2
    exit 1
}

# Each run appends to west.log after a timestamped header.
west_log="$WORK_DIR/west.log"
log_start_line=1
if [[ -f "$west_log" ]]; then
    log_start_line=$(( $(wc -l < "$west_log") + 1 ))
fi
echo "===== w_run started $(date '+%Y-%m-%d %H:%M:%S') =====" >> "$west_log"

echo "Running: up to $requested_iteration WESTPA iterations; log: $west_log"
if ! w_run --work-manager serial >> "$west_log" 2>&1; then
    report_westpa_failure "WESTPA run failed"
fi
if awk -v start="$log_start_line" 'NR >= start && /-- ERROR/ {found = 1} END {exit !found}' "$west_log"; then
    report_westpa_failure "A run error was recorded in the WESTPA log"
fi

if ! current_iteration=$("${PYTHON:-python3}" - "$WORK_DIR/west.h5" <<'PY'
import numbers
import sys
import h5py

try:
    with h5py.File(sys.argv[1], "r") as handle:
        current = handle.attrs.get("west_current_iteration")
        if not isinstance(current, numbers.Integral) or current < 1:
            raise ValueError("invalid west_current_iteration")
        print(current)
except (OSError, ValueError) as error:
    print(f"Error: WESTPA progress check: {sys.argv[1]}; {error}", file=sys.stderr)
    raise SystemExit(1) from None
PY
); then
    exit 1
fi

completed_iteration=$((current_iteration - 1))
if [[ "$current_iteration" -le "$requested_iteration" ]]; then
    echo "WESTPA paused: $completed_iteration of $requested_iteration iterations completed; state: $WORK_DIR/west.h5"
    echo "Run ./run.sh again to continue; log: $WORK_DIR/west.log"
else
    echo "WESTPA run completed: $completed_iteration iterations; state: $WORK_DIR/west.h5; log: $WORK_DIR/west.log"
fi
