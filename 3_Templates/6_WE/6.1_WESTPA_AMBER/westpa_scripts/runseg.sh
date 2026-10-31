#!/usr/bin/env bash
set -euo pipefail

original_args=("$@")

show_help() {
    cat <<'EOF'
Usage: ./westpa_scripts/runseg.sh

WESTPA callback that propagates one AMBER segment from its parent restart and
returns the start and end progress coordinates.

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

AMBER_ENGINE=$("${PYTHON:-python3}" "$WEST_SIM_ROOT/helpers/config_utils.py" "$WORK_DIR/resolved_config.toml" engine AMBER_ENGINE pmemd.cuda pmemd sander)

if [[ ${MD_WRITER_PARENT:-} != "$PPID" || ${MD_WRITER_ENTRY:-} != "$0" ]]; then
    exec "${PYTHON:-python3}" "$WEST_SIM_ROOT/helpers/writer_guard.py" --callback-entry \
        --registry "$WORK_DIR" --read "$WORK_DIR/common_files" --read "$WORK_DIR/inputs" --read "$WORK_DIR/progress_coordinate.mask" --read "$WEST_PARENT_DATA_REF" --write "$WEST_CURRENT_SEG_DATA_REF" --write "$WEST_PCOORD_RETURN" -- "$0" "${original_args[@]}"
fi

mkdir -p "$WEST_CURRENT_SEG_DATA_REF"
cd "$WEST_CURRENT_SEG_DATA_REF"

# WESTPA 2022.15 w_run removes and recreates an incomplete segment directory
# before calling this script. Leftover output therefore means a standalone
# callback or a WESTPA version that keeps partial segments; keep it for review.
for output in segment.in segment.out segment.info seg.rst7 seg.nc; do
    if [[ -e "$output" ]]; then
        echo "Error: Segment output from an earlier propagation attempt was kept: $WEST_CURRENT_SEG_DATA_REF/$output" >&2
        echo "Inspect the partial segment, move its directory aside, and rerun ./run.sh:" >&2
        printf '  mv %q %q.failed.<timestamp>\n' "$WEST_CURRENT_SEG_DATA_REF" "$WEST_CURRENT_SEG_DATA_REF" >&2
        exit 1
    fi
done
if [[ -s "$WEST_PCOORD_RETURN" ]]; then
    echo "Error: Progress-coordinate return file is not empty and was kept: $WEST_PCOORD_RETURN" >&2
    exit 1
fi

case "$WEST_CURRENT_SEG_INITPOINT_TYPE" in
    SEG_INITPOINT_NEWTRAJ)
        parent_restart=$WEST_PARENT_DATA_REF
        ;;
    SEG_INITPOINT_CONTINUES)
        parent_restart=$WEST_PARENT_DATA_REF/seg.rst7
        ;;
    *)
        echo "Error: unknown initial-point type: $WEST_CURRENT_SEG_INITPOINT_TYPE" >&2
        exit 2
        ;;
esac

if [[ ! -s "$parent_restart" ]]; then
    echo "Error: parent restart not found: $parent_restart" >&2
    exit 1
fi

seed=$((WEST_RAND32 % 2147483646 + 1))
sed "s/WEST_SEED/$seed/g" "$WORK_DIR/inputs/segment.in.template" \
    > segment.in

start_pcoord=$("$WEST_SIM_ROOT/westpa_scripts/calc_pcoord.sh" "$parent_restart")
if ! "$AMBER_ENGINE" \
    -O \
    -i segment.in \
    -o segment.out \
    -p "$WORK_DIR/common_files/system.parm7" \
    -c "$parent_restart" \
    -r seg.rst7 \
    -x seg.nc \
    -inf segment.info; then
    echo "Error: AMBER propagation failed: $WEST_CURRENT_SEG_DATA_REF/segment.out" >&2
    exit 1
fi
for output in seg.rst7 seg.nc segment.out segment.info; do
    if [[ ! -s "$output" ]]; then
        echo "Error: Segment output is incomplete: $WEST_CURRENT_SEG_DATA_REF/$output" >&2
        exit 1
    fi
done
end_pcoord=$("$WEST_SIM_ROOT/westpa_scripts/calc_pcoord.sh" seg.rst7)
printf '%s\n%s\n' "$start_pcoord" "$end_pcoord" > "$WEST_PCOORD_RETURN"
