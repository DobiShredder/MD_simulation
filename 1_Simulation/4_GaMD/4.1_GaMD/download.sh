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

if ! command -v "$curl_bin" >/dev/null 2>&1; then
    die "curl not found: $curl_bin"
fi

mkdir -p "$structure_dir"
echo "Downloading the Chignolin structure (PDB 1UAO)."

if ! "$curl_bin" \
    -fsSL \
    https://files.rcsb.org/download/1UAO.pdb \
    -o "$structure_dir/1UAO.raw.pdb"; then
    die "PDB 1UAO Download failed."
fi

if ! "$curl_bin" \
    -fsSL \
    https://files.rcsb.org/download/1UAO.cif \
    -o "$structure_dir/1UAO.cif"; then
    die "1UAO mmCIF Download failed."
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
