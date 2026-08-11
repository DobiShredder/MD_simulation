#!/usr/bin/env bash
set -euo pipefail

if [[ $# -ne 1 ]]; then
    echo "Usage: $0 RESTART_FILE" >&2
    exit 2
fi

restart_file=$1
topology_file="$WORK_DIR/common_files/system.parm7"
reference_file="$WORK_DIR/common_files/reference.rst7"

if [[ ! -s "$restart_file" ]]; then
    echo "Error: progress-coordinate restart not found: $restart_file" >&2
    exit 1
fi
if [[ ! -s "$topology_file" ]]; then
    echo "Error: progress-coordinate topology not found: $topology_file" >&2
    exit 1
fi
if [[ ! -s "$reference_file" ]]; then
    echo "Error: RMSD reference not found: $reference_file" >&2
    exit 1
fi
if ! command -v "$CPPTRAJ" >/dev/null 2>&1; then
    echo "Error: executable not found: $CPPTRAJ" >&2
    exit 1
fi

tmp_file=$(mktemp "${TMPDIR:-/tmp}/we-pcoord.XXXXXX")
trap 'rm -f "$tmp_file"' EXIT

"$CPPTRAJ" -p "$topology_file" > /dev/null <<EOF
reference $reference_file
trajin $restart_file
rms chignolin_ca :2-9@CA reference out $tmp_file
run
EOF

awk 'NF >= 2 && $1 !~ /^#/ { value=$2 } END {
    if (value == "") exit 1
    printf "%.6f\n", value
}' "$tmp_file"
