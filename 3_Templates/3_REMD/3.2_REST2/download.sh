#!/usr/bin/env bash
set -euo pipefail

show_help() {
    cat <<'EOF'
Usage: ./download.sh PDB_ID

Download a four-character PDB entry from RCSB into structure/. The downloaded
structure is not processed or repaired.

Options:
  -h, --help  Show this help message and exit.
EOF
}

if [[ "${1:-}" == -h || "${1:-}" == --help ]]; then
    show_help
    exit 0
fi
if [[ $# -ne 1 || ! "$1" =~ ^[A-Za-z0-9]{4}$ ]]; then
    show_help >&2
    exit 2
fi

curl_bin=${CURL:-curl}
pdb_id=${1^^}
output="structure/$pdb_id.pdb"
if ! command -v "$curl_bin" >/dev/null 2>&1; then
    echo "Error: curl not found: $curl_bin" >&2
    exit 1
fi
mkdir -p structure
if ! "$curl_bin" -fsSL "https://files.rcsb.org/download/$pdb_id.pdb" -o "$output"; then
    echo "Error: failed to download PDB $pdb_id." >&2
    exit 1
fi
if [[ ! -s "$output" ]]; then
    echo "Error: downloaded PDB is empty: $output" >&2
    exit 1
fi
echo "Downloaded source structure: $output"
