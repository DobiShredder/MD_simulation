#!/usr/bin/env bash
set -euo pipefail

source ./env.sh

dry_run=0
if [[ "${1:-}" == "--dry-run" && $# -eq 1 ]]; then
    dry_run=1
elif [[ $# -ne 0 ]]; then
    echo "Usage: $0 [--dry-run]" >&2
    exit 2
fi

if (( dry_run )); then
    printf '+ w_run --work-manager serial > %q 2>&1\n' "$WORK_DIR/west.log"
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

echo "Running: 20 WESTPA iterations with the serial work manager"
if ! w_run --work-manager serial > "$WORK_DIR/west.log" 2>&1; then
    echo "Error: WESTPA Run failed: $WORK_DIR/west.log" >&2
    exit 1
fi
if grep -q -- '-- ERROR' "$WORK_DIR/west.log"; then
    echo "Error: A run error was recorded in the WESTPA log: $WORK_DIR/west.log" >&2
    exit 1
fi

echo "WESTPA run completed: $WORK_DIR/west.h5"
