#!/usr/bin/env bash
set -euo pipefail

source ./env.sh

dry_run=0
if [[ "${1:-}" == "--dry-run" ]]; then
    dry_run=1
    shift
fi
if [[ $# -ne 0 ]]; then
    echo "Usage: $0 [--dry-run]" >&2
    exit 2
fi

case "$WESTPA_WORK_MANAGER" in
    serial|processes)
        ;;
    *)
        echo "Error: WESTPA_WORK_MANAGER must be serial or processes." >&2
        exit 1
        ;;
esac

if [[ ! "$WESTPA_WORKERS" =~ ^[1-9][0-9]*$ ]]; then
    echo "Error: WESTPA_WORKERS must be an integer greater than or equal to 1." >&2
    exit 1
fi

if [[ "$WESTPA_WORK_MANAGER" == "serial" && "$WESTPA_WORKERS" -ne 1 ]]; then
    echo "Error: Use WESTPA_WORKERS=1 with the serial work manager." >&2
    exit 1
fi

if [[ "$WESTPA_WORK_MANAGER" == "processes" && "$AMBER_ENGINE" == "pmemd.cuda" ]]; then
    echo "Error: The process-worker example requires a CPU engine. Specify AMBER_ENGINE=sander." >&2
    exit 1
fi

westpa_command=(
    w_run
    --work-manager "$WESTPA_WORK_MANAGER"
)

if [[ "$WESTPA_WORK_MANAGER" == "processes" ]]; then
    westpa_command+=(
        --n-workers "$WESTPA_WORKERS"
    )
fi

if (( dry_run )); then
    echo "WESTPA 2: Chignolin Cα RMSD, 4 walkers per bin, 1 ps × 20 iterations"
    printf 'AMBER engine: %s\n' "$AMBER_ENGINE"
    printf 'Work manager: %s, worker count: %s\n' \
        "$WESTPA_WORK_MANAGER" \
        "$WESTPA_WORKERS"
    printf '%q ' "${westpa_command[@]}"
    printf '\n'
    exit 0
fi

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

if ! "${westpa_command[@]}" > "$WORK_DIR/west.log" 2>&1; then
    echo "Error: WESTPA Run failed: $WORK_DIR/west.log" >&2
    exit 1
fi
if grep -q -- '-- ERROR' "$WORK_DIR/west.log"; then
    echo "Error: A run error was recorded in the WESTPA log: $WORK_DIR/west.log" >&2
    exit 1
fi

echo "WESTPA run completed: $WORK_DIR/west.h5"
