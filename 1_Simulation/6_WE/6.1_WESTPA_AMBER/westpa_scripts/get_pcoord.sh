#!/usr/bin/env bash
set -euo pipefail

original_args=("$@")
if [[ $# -ne 0 ]]; then
    echo "Usage: $0 (WESTPA callback; no arguments)" >&2
    exit 2
fi

if [[ ${MD_WRITER_PARENT:-} != "$PPID" || ${MD_WRITER_ENTRY:-} != "$0" ]]; then
    exec "${PYTHON:-python3}" "$WEST_SIM_ROOT/helpers/writer_guard.py" --callback-entry \
        --registry "$WORK_DIR" --read "$WORK_DIR/common_files" --read "$WEST_SIM_ROOT/inputs" --read "$WEST_STRUCT_DATA_REF" --write "$WEST_PCOORD_RETURN" -- "$0" "${original_args[@]}"
fi

"$WEST_SIM_ROOT/westpa_scripts/calc_pcoord.sh" "$WEST_STRUCT_DATA_REF" \
    > "$WEST_PCOORD_RETURN"
