#!/usr/bin/env bash
set -euo pipefail

mkdir -p "$WEST_CURRENT_SEG_DATA_REF"
cd "$WEST_CURRENT_SEG_DATA_REF"

case "$WEST_CURRENT_SEG_INITPOINT_TYPE" in
    SEG_INITPOINT_NEWTRAJ)
        parent_restart=$WEST_PARENT_DATA_REF
        ;;
    SEG_INITPOINT_CONTINUES)
        parent_restart=$WEST_PARENT_DATA_REF/seg.rst7
        ;;
    *)
        echo "ERROR: unknown init point: $WEST_CURRENT_SEG_INITPOINT_TYPE" >&2
        exit 2
        ;;
esac

seed=$((WEST_RAND32 % 2147483646 + 1))
sed "s/WEST_SEED/$seed/g" "$WEST_SIM_ROOT/amber/segment.in.template" \
    > segment.in

start_pcoord=$("$WEST_SIM_ROOT/westpa_scripts/calc_pcoord.sh" "$parent_restart")
"$AMBER_ENGINE" -O -i segment.in -o segment.out \
    -p "$WEST_SIM_ROOT/common_files/system.parm7" -c "$parent_restart" \
    -r seg.rst7 -inf segment.info
end_pcoord=$("$WEST_SIM_ROOT/westpa_scripts/calc_pcoord.sh" seg.rst7)
printf '%s\n%s\n' "$start_pcoord" "$end_pcoord" > "$WEST_PCOORD_RETURN"
