#!/usr/bin/env bash
set -euo pipefail

if [[ $# -ne 2 ]]; then
    echo "Usage: $0 RESTART_FILE CPPTRAJ_LOG" >&2
    exit 2
fi

restart_file=$1
# The caller keeps this log beside its output, for example in the segment directory.
cpptraj_log=$2
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

if ! "$CPPTRAJ" -p "$topology_file" > "$cpptraj_log" 2>&1 <<EOF
reference $reference_file
trajin $restart_file
rms chignolin_ca :2-9@CA reference out $tmp_file
run
EOF
then
    echo "Last 20 lines of $cpptraj_log:" >&2
    tail -n 20 "$cpptraj_log" >&2
    echo "Error: cpptraj RMSD calculation failed for $restart_file; log: $cpptraj_log" >&2
    exit 1
fi

# Copy the RMSD table into the log; the EXIT trap removes the temporary file.
{
    echo "# cpptraj RMSD output"
    cat "$tmp_file"
} >> "$cpptraj_log"

awk -v restart="$restart_file" -v log_file="$cpptraj_log" '
BEGIN { number = "^[-+]?([0-9]+([.][0-9]*)?|[.][0-9]+)([eE][-+]?[0-9]+)?$" }
NF && $1 !~ /^#/ {
    if (NF != 2 || $1 !~ /^[0-9]+$/ || $2 !~ number || sprintf("%.17g", $2 + 0) !~ number) {
        invalid = 1
        exit
    }
    value = $2
    found = 1
}
END {
    if (invalid || !found) {
        print "Error: invalid or nonfinite cpptraj RMSD output for " restart "; log: " log_file > "/dev/stderr"
        exit 1
    }
    printf "%.6f\n", value
}' "$tmp_file"
