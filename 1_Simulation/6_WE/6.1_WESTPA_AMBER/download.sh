#!/usr/bin/env bash
set -euo pipefail

die() {
    echo "Error: $*" >&2
    exit 1
}

if [[ $# -ne 0 ]]; then
    echo "Usage: $0" >&2
    exit 2
fi

curl_bin=${CURL:-curl}
structure_dir="structure"
pdb_url="https://files.rcsb.org/download/1UAO.pdb"
cif_url="https://files.rcsb.org/download/1UAO.cif"

if ! command -v "$curl_bin" >/dev/null 2>&1; then
    die "curl not found: $curl_bin"
fi

echo "Downloading the Chignolin structure (PDB 1UAO)."
mkdir -p "$structure_dir"

if ! "$curl_bin" -fsSL "$pdb_url" -o "$structure_dir/1UAO.raw.pdb"; then
    die "Failed to download PDB: $pdb_url"
fi

if ! "$curl_bin" -fsSL "$cif_url" -o "$structure_dir/1UAO.cif"; then
    die "Failed to download mmCIF: $cif_url"
fi

if command -v sha256sum >/dev/null 2>&1; then
    (
        cd "$structure_dir"
        sha256sum 1UAO.raw.pdb 1UAO.cif > SHA256SUMS
    )
else
    (
        cd "$structure_dir"
        shasum -a 256 1UAO.raw.pdb 1UAO.cif > SHA256SUMS
    )
fi

echo "Downloaded files and checksums: $structure_dir"
