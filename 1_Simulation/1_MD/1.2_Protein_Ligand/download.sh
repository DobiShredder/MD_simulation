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

# User settings and output paths
curl_bin=${CURL:-curl}

structure_dir="structure"

complex_pdb_url="https://files.rcsb.org/download/3HTB.pdb"
complex_cif_url="https://files.rcsb.org/download/3HTB.cif"
ligand_sdf_url="https://files.rcsb.org/ligands/download/JZ4_ideal.sdf"

# Input and dependency checks
if ! command -v "$curl_bin" >/dev/null 2>&1; then
    die "curl not found: $curl_bin"
fi

echo "Downloading the T4 lysozyme–JZ4 structure (PDB 3HTB)."
mkdir -p "$structure_dir"

# Download the PDB used to prepare the protein-ligand complex.
if ! "$curl_bin" \
    -fsSL \
    "$complex_pdb_url" \
    -o "$structure_dir/3HTB.raw.pdb"; then
    die "Failed to download PDB: $complex_pdb_url"
fi

# Also download the mmCIF for source-structure and metadata checks.
if ! "$curl_bin" \
    -fsSL \
    "$complex_cif_url" \
    -o "$structure_dir/3HTB.cif"; then
    die "Failed to download mmCIF: $complex_cif_url"
fi

# Download the ideal SDF used for JZ4 parameterization.
if ! "$curl_bin" \
    -fsSL \
    "$ligand_sdf_url" \
    -o "$structure_dir/JZ4_ideal.sdf"; then
    die "JZ4 SDF Download failed: $ligand_sdf_url"
fi

# Handle checksum command differences between Linux and macOS.
if command -v sha256sum >/dev/null 2>&1; then
    (
        cd "$structure_dir"
        sha256sum \
            3HTB.raw.pdb \
            3HTB.cif \
            JZ4_ideal.sdf \
            > SHA256SUMS
    )
else
    (
        cd "$structure_dir"
        shasum \
            -a 256 \
            3HTB.raw.pdb \
            3HTB.cif \
            JZ4_ideal.sdf \
            > SHA256SUMS
    )
fi

echo "Downloaded files and checksums: $structure_dir"
