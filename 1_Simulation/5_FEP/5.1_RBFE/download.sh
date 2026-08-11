#!/usr/bin/env bash
set -euo pipefail

die() {
    echo "Error: $*" >&2
    exit 1
}

structure_dir=${STRUCTURE_DIR:-"structure"}
curl_bin=${CURL:-curl}

if ! command -v "$curl_bin" >/dev/null 2>&1; then
    die "curl not found: $curl_bin"
fi

mkdir -p "$structure_dir"

echo "Downloading the T4 lysozyme L99A–toluene structure (PDB 4W53)."
if ! "$curl_bin" --fail --location --silent --show-error https://files.rcsb.org/download/4W53.pdb \
    -o "$structure_dir/4W53.raw.pdb"; then
    die "4W53 PDB Download failed."
fi
if ! "$curl_bin" --fail --location --silent --show-error https://files.rcsb.org/download/4W53.cif \
    -o "$structure_dir/4W53.cif"; then
    die "4W53 mmCIF Download failed."
fi
if ! "$curl_bin" --fail --location --silent --show-error https://files.rcsb.org/ligands/download/BNZ_ideal.sdf \
    -o "$structure_dir/BNZ_ideal.sdf"; then
    die "BNZ ideal SDF Download failed."
fi
if ! "$curl_bin" --fail --location --silent --show-error https://files.rcsb.org/ligands/download/MBN_ideal.sdf \
    -o "$structure_dir/MBN_ideal.sdf"; then
    die "MBN ideal SDF Download failed."
fi

if command -v sha256sum >/dev/null 2>&1; then
    (cd "$structure_dir" && sha256sum 4W53.raw.pdb 4W53.cif BNZ_ideal.sdf MBN_ideal.sdf > SHA256SUMS)
elif command -v shasum >/dev/null 2>&1; then
    (cd "$structure_dir" && shasum -a 256 4W53.raw.pdb 4W53.cif BNZ_ideal.sdf MBN_ideal.sdf > SHA256SUMS)
else
    die "sha256sum or shasum is required."
fi

echo "Source structure: $structure_dir"
