#!/usr/bin/env bash
set -euo pipefail

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

mkdir -p "$WEST_CURRENT_SEG_DATA_REF"
cd "$WEST_CURRENT_SEG_DATA_REF"

existing=0
for output in segment.in segment.out segment.info seg.rst7; do
    if [[ -e "$output" ]]; then
        existing=$((existing + 1))
    fi
done
if [[ -s "$WEST_PCOORD_RETURN" ]]; then
    existing=$((existing + 1))
fi
if [[ "$existing" -ne 0 ]]; then
    echo "Error: Segment directory is not empty: $WEST_CURRENT_SEG_DATA_REF" >&2
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
    -inf segment.info; then
    echo "Error: AMBER propagation failed: $WEST_CURRENT_SEG_DATA_REF/segment.out" >&2
    exit 1
fi
if [[ ! -s seg.rst7 || ! -s segment.out || ! -s segment.info ]]; then
    echo "Error: Segment output is incomplete: $WEST_CURRENT_SEG_DATA_REF" >&2
    exit 1
fi
end_pcoord=$("$WEST_SIM_ROOT/westpa_scripts/calc_pcoord.sh" seg.rst7)
printf '%s\n%s\n' "$start_pcoord" "$end_pcoord" > "$WEST_PCOORD_RETURN"
