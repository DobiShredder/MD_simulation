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
echo "Downloading the C-crk SH3–SOS peptide structure (PDB 1CKB)."

if ! "$curl_bin" -fsSL \
    https://files.rcsb.org/download/1CKB.pdb \
    -o "$structure_dir/1CKB.raw.pdb"; then
    die "PDB 1CKB Download failed."
fi
if ! "$curl_bin" -fsSL \
    https://files.rcsb.org/download/1CKB.cif \
    -o "$structure_dir/1CKB.cif"; then
    die "1CKB mmCIF Download failed."
fi

if command -v sha256sum >/dev/null 2>&1; then
    (
        cd "$structure_dir"
        sha256sum 1CKB.raw.pdb 1CKB.cif > SHA256SUMS
    )
else
    (
        cd "$structure_dir"
        shasum -a 256 1CKB.raw.pdb 1CKB.cif > SHA256SUMS
    )
fi

echo "Downloaded files and checksums: $structure_dir"
