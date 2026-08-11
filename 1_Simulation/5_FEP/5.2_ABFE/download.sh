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

echo "Downloading the T4 lysozyme–JZ4 structure (PDB 3HTB)."
mkdir -p "$structure_dir"

if ! "$curl_bin" -fsSL \
    https://files.rcsb.org/download/3HTB.pdb \
    -o "$structure_dir/3HTB.raw.pdb"; then
    die "3HTB PDB Download failed."
fi

if ! "$curl_bin" -fsSL \
    https://files.rcsb.org/download/3HTB.cif \
    -o "$structure_dir/3HTB.cif"; then
    die "3HTB mmCIF Download failed."
fi

if ! "$curl_bin" -fsSL \
    https://files.rcsb.org/ligands/download/JZ4_ideal.sdf \
    -o "$structure_dir/JZ4_ideal.sdf"; then
    die "JZ4 ideal SDF Download failed."
fi

if command -v sha256sum >/dev/null 2>&1; then
    (
        cd "$structure_dir"
        sha256sum 3HTB.raw.pdb 3HTB.cif JZ4_ideal.sdf > SHA256SUMS
    )
else
    (
        cd "$structure_dir"
        shasum -a 256 3HTB.raw.pdb 3HTB.cif JZ4_ideal.sdf > SHA256SUMS
    )
fi

echo "Downloaded files and checksums: $structure_dir"
