#!/usr/bin/env bash
set -euo pipefail

die() {
    echo "Error: $*" >&2
    exit 1
}

show_help() {
    cat <<'EOF'
Usage: ./download.sh [PDB_ID]

Download a four-character PDB entry from RCSB into structure/. The default is
1UBQ. The downloaded structure is not processed or repaired.

Options:
  -h, --help  Show this help message and exit.
EOF
}

if [[ "${1:-}" == -h || "${1:-}" == --help ]]; then
    show_help
    exit 0
fi

if [[ $# -gt 1 ]]; then
    show_help >&2
    exit 2
fi

pdb_id=${1:-1UBQ}
pdb_id=${pdb_id^^}
curl_bin=${CURL:-curl}

if [[ ! "$pdb_id" =~ ^[A-Z0-9]{4}$ ]]; then
    die "PDB ID must contain exactly four letters or digits: $pdb_id"
fi
if ! command -v "$curl_bin" >/dev/null 2>&1; then
    die "curl not found: $curl_bin"
fi

mkdir -p structure
output="structure/${pdb_id}.pdb"
url="https://files.rcsb.org/download/${pdb_id}.pdb"

download_tmp=$(mktemp "structure/.${pdb_id}.download.XXXXXX")
trap 'rm -f -- "$download_tmp"' EXIT

echo "Downloading PDB $pdb_id from RCSB."
if ! "$curl_bin" -fsSL "$url" -o "$download_tmp"; then
    die "PDB download failed: $url"
fi
if [[ ! -s "$download_tmp" ]] || ! grep -qE '^(ATOM  |HETATM)' "$download_tmp"; then
    die "Downloaded file does not contain PDB atom records: $output"
fi

mv -- "$download_tmp" "$output"
echo "Downloaded structure: $output"
