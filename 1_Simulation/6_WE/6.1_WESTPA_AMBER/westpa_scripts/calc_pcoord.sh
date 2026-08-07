#!/usr/bin/env bash
set -euo pipefail

restart_file=$1
tmp_file=$(mktemp "${TMPDIR:-/tmp}/we-pcoord.XXXXXX")
trap 'rm -f "$tmp_file"' EXIT

cpptraj -p "$WEST_SIM_ROOT/common_files/system.parm7" > /dev/null <<EOF
trajin $restart_file
distance ion_distance @Na @Cl noimage out $tmp_file
run
EOF

awk 'NF >= 2 && $1 !~ /^#/ { value=$2 } END {
    if (value == "") exit 1
    printf "%.6f\n", value
}' "$tmp_file"
