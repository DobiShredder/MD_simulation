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
echo "Downloading the trypsin–benzamidine structure (PDB 3PTB)."

if ! "$curl_bin" -fsSL \
    https://files.rcsb.org/download/3PTB.pdb \
    -o "$structure_dir/3PTB.raw.pdb"; then
    die "PDB 3PTB Download failed."
fi
if ! "$curl_bin" -fsSL \
    https://files.rcsb.org/download/3PTB.cif \
    -o "$structure_dir/3PTB.cif"; then
    die "3PTB mmCIF Download failed."
fi
if ! "$curl_bin" -fsSL \
    https://files.rcsb.org/ligands/download/BEN_ideal.sdf \
    -o "$structure_dir/BEN_ideal.sdf"; then
    die "BEN ideal SDF Download failed."
fi

if command -v sha256sum >/dev/null 2>&1; then
    (
        cd "$structure_dir"
        sha256sum 3PTB.raw.pdb 3PTB.cif BEN_ideal.sdf > SHA256SUMS
    )
else
    (
        cd "$structure_dir"
        shasum -a 256 3PTB.raw.pdb 3PTB.cif BEN_ideal.sdf > SHA256SUMS
    )
fi

echo "Downloaded files and checksums: $structure_dir"
