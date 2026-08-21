#!/usr/bin/env bash
set -euo pipefail

dry_run=0
selected_block=""
show_help() {
    cat <<'EOF'
Usage: ./run.sh [--block N] [--dry-run]

Continue all configured WESTPA blocks or run one selected block.

Options:
  --block N      Run only the selected 1-based block.
  --dry-run      Print WESTPA commands without running them.
  -h, --help     Show this help message and exit.

Environment:
  WESTPA_WORK_MANAGER  serial or processes (default: serial).
  WESTPA_WORKERS       Worker count for processes mode (default: 1).
  AMBER_ENGINE         Segment propagation engine (default: pmemd.cuda).
  CPPTRAJ              Progress-coordinate executable (default: cpptraj).
  PYTHON               Python with h5py for completion checks (default: python3).
  WORK_DIR             Generated simulation directory (default: work).
EOF
}

while [[ $# -gt 0 ]]; do
    case "$1" in
        --block)
            if [[ $# -lt 2 ]]; then
                echo "Error: --block requires an index." >&2
                exit 2
            fi
            selected_block=$2
            shift 2
            ;;
        --dry-run) dry_run=1; shift ;;
        -h|--help) show_help; exit 0 ;;
        *) show_help >&2; exit 2 ;;
    esac
done

die() {
    echo "Error: $*" >&2
    exit 1
}

export WEST_SIM_ROOT=${WEST_SIM_ROOT:-$PWD}
export WORK_DIR=${WORK_DIR:-$WEST_SIM_ROOT/work}
export AMBER_ENGINE=${AMBER_ENGINE:-pmemd.cuda}
export CPPTRAJ=${CPPTRAJ:-cpptraj}
python=${PYTHON:-python3}
work_manager=${WESTPA_WORK_MANAGER:-serial}
workers=${WESTPA_WORKERS:-1}

case "$work_manager" in
    serial|processes) ;;
    *) die "WESTPA_WORK_MANAGER must be serial or processes: $work_manager" ;;
esac
if [[ ! "$workers" =~ ^[1-9][0-9]*$ ]]; then
    die "WESTPA_WORKERS must be a positive integer: $workers"
fi
if [[ "$work_manager" == serial && "$workers" -ne 1 ]]; then
    die "Use WESTPA_WORKERS=1 with the serial work manager."
fi
if [[ "$work_manager" == processes && "$(basename "$AMBER_ENGINE")" == pmemd.cuda ]]; then
    die "Multiple process workers cannot share the default pmemd.cuda engine."
fi
if [[ -n "$selected_block" && ! "$selected_block" =~ ^[1-9][0-9]*$ ]]; then
    die "--block must be a positive integer: $selected_block"
fi

if (( ! dry_run )); then
    if [[ ! -s "$WORK_DIR/west.h5" ]]; then
        die "WESTPA state not found. Run ./init.sh first: $WORK_DIR/west.h5"
    fi
    for executable in w_run "$AMBER_ENGINE" "$CPPTRAJ" "$python"; do
        if ! command -v "$executable" >/dev/null 2>&1; then
            die "Executable not found: $executable"
        fi
    done
fi

found=0
for config in "$WORK_DIR"/configs/west.[0-9][0-9][0-9].cfg; do
    if [[ ! -s "$config" ]]; then
        continue
    fi
    config_name=${config##*/}
    block_text=${config_name#west.}
    block_text=${block_text%.cfg}
    block=$((10#$block_text))
    if [[ -n "$selected_block" && "$block" -ne "$selected_block" ]]; then
        continue
    fi
    found=$((found + 1))
    marker="$WORK_DIR/.block.$block_text.complete"
    if [[ -f "$marker" ]]; then
        continue
    fi
    command=(w_run -r "$config" --work-manager "$work_manager")
    if [[ "$work_manager" == processes ]]; then
        command+=(--n-workers "$workers")
    fi
    if (( dry_run )); then
        printf '+'
        printf ' %q' "${command[@]}"
        printf '\n'
        continue
    fi
    echo "Running: WE block $block_text"
    if ! "${command[@]}" > "$WORK_DIR/west.$block_text.log" 2>&1; then
        die "WESTPA block failed: $WORK_DIR/west.$block_text.log"
    fi
    if grep -q -- '-- ERROR' "$WORK_DIR/west.$block_text.log"; then
        die "WESTPA reported an error: $WORK_DIR/west.$block_text.log"
    fi
    requested_iteration=$(awk '/^[[:space:]]*max_total_iterations:/ {print $2; exit}' "$config")
    current_iteration=$("$python" - "$WORK_DIR/west.h5" <<'PY'
import sys
import h5py

with h5py.File(sys.argv[1], "r") as handle:
    print(int(handle.attrs["west_current_iteration"]))
PY
)
    if [[ ! "$requested_iteration" =~ ^[1-9][0-9]*$ ]]; then
        die "Could not read max_total_iterations: $config"
    fi
    if [[ "$current_iteration" -le "$requested_iteration" ]]; then
        die "WESTPA stopped before block completion: $WORK_DIR/west.$block_text.log"
    fi
    touch "$marker"
done
if (( found == 0 )); then
    die "Requested WESTPA block config was not found: ${selected_block:-all}"
fi

if (( ! dry_run )); then
    echo "WESTPA blocks completed: $WORK_DIR/west.h5"
fi
