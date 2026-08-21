#!/usr/bin/env bash
set -euo pipefail

show_help() {
    cat <<'EOF'
Usage: ./westpa_scripts/calc_pcoord.sh RESTART_FILE

Calculate the configured one-dimensional RMSD progress coordinate for one
AMBER restart file and print the value in angstroms.

Options:
  -h, --help  Show this help message and exit.
EOF
}

if [[ "${1:-}" == -h || "${1:-}" == --help ]]; then
    show_help
    exit 0
fi
if [[ $# -ne 1 ]]; then
    show_help >&2
    exit 2
fi

restart_file=$1
work_dir=${WORK_DIR:-work}
cpptraj=${CPPTRAJ:-cpptraj}
mask_file="$work_dir/progress_coordinate.mask"

topology_file="$work_dir/common_files/system.parm7"
reference_file="$work_dir/common_files/reference.rst7"

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
if [[ ! -s "$mask_file" ]]; then
    echo "Error: progress-coordinate mask not found: $mask_file" >&2
    exit 1
fi
if ! command -v "$cpptraj" >/dev/null 2>&1; then
    echo "Error: executable not found: $cpptraj" >&2
    exit 1
fi
progress_mask=$(<"$mask_file")

tmp_file=$(mktemp "${TMPDIR:-/tmp}/we-pcoord.XXXXXX")
trap 'rm -f "$tmp_file"' EXIT

"$cpptraj" -p "$topology_file" > /dev/null <<EOF
reference $reference_file
trajin $restart_file
rms progress_coordinate $progress_mask reference out $tmp_file
run
EOF

awk 'NF >= 2 && $1 !~ /^#/ { value=$2 } END {
    if (value == "") exit 1
    printf "%.6f\n", value
}' "$tmp_file"
