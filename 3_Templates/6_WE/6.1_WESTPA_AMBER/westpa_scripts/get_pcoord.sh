#!/usr/bin/env bash
set -euo pipefail

original_args=("$@")

show_help() {
    cat <<'EOF'
Usage: ./westpa_scripts/get_pcoord.sh

WESTPA callback that evaluates the initial-state progress coordinate and writes
it to WEST_PCOORD_RETURN.

Options:
  -h, --help  Show this help message and exit.
EOF
}

if [[ "${1:-}" == -h || "${1:-}" == --help ]]; then
    show_help
    exit 0
fi
if [[ $# -ne 0 ]]; then
    show_help >&2
    exit 2
fi

if [[ ${MD_WRITER_PARENT:-} != "$PPID" || ${MD_WRITER_ENTRY:-} != "$0" ]]; then
    exec "${PYTHON:-python3}" "$WEST_SIM_ROOT/helpers/writer_guard.py" --callback-entry \
        --registry "$WORK_DIR" --read "$WORK_DIR/common_files" --read "$WORK_DIR/inputs" --read "$WORK_DIR/progress_coordinate.mask" --read "$WEST_STRUCT_DATA_REF" --write "$WEST_PCOORD_RETURN" -- "$0" "${original_args[@]}"
fi

"$WEST_SIM_ROOT/westpa_scripts/calc_pcoord.sh" "$WEST_STRUCT_DATA_REF" \
    > "$WEST_PCOORD_RETURN"
