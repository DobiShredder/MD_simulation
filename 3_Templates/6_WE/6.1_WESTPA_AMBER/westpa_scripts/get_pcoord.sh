#!/usr/bin/env bash
set -euo pipefail

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

"$WEST_SIM_ROOT/westpa_scripts/calc_pcoord.sh" "$WEST_STRUCT_DATA_REF" \
    > "$WEST_PCOORD_RETURN"
