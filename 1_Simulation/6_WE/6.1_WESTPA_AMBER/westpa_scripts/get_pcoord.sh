#!/usr/bin/env bash
set -euo pipefail

"$WEST_SIM_ROOT/westpa_scripts/calc_pcoord.sh" "$WEST_STRUCT_DATA_REF" \
    > "$WEST_PCOORD_RETURN"
