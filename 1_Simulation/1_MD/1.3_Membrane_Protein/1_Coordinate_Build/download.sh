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

opm_pdb_url="https://opm-assets.storage.googleapis.com/pdb/1k4c.pdb"
sidechain_template_url="https://opm-assets.storage.googleapis.com/pdb/3eff.pdb"
assembly_cif_url="https://files.rcsb.org/download/1K4C-assembly1.cif"
popc_url="https://zenodo.org/records/14776136/files/POPC.gro"
pope_url="https://zenodo.org/records/14776136/files/POPE.gro"
cholesterol_url="https://zenodo.org/records/14776136/files/CHOL15.gro"

# Input and dependency checks
if ! command -v "$curl_bin" >/dev/null 2>&1; then
    die "curl not found: $curl_bin"
fi

echo "Downloading membrane-oriented KcsA from OPM (PDB 1K4C)."
mkdir -p "$structure_dir"

# The OPM PDB contains the protein orientation and membrane boundaries at z=±15 Å.
if ! "$curl_bin" \
    -fsSL \
    "$opm_pdb_url" \
    -o "$structure_dir/1K4C-opm.pdb"; then
    die "OPM Failed to download PDB: $opm_pdb_url"
fi

# Restore the missing Ser22 and Arg117 side chains in 1K4C from closed KcsA 3EFF.
if ! "$curl_bin" \
    -fsSL \
    "$sidechain_template_url" \
    -o "$structure_dir/3EFF-opm.pdb"; then
    die "side-chain template Download failed: $sidechain_template_url"
fi

# Download the 128-lipid bilayer coordinates equilibrated with Lipid21.
if ! "$curl_bin" -fsSL --retry 3 "$popc_url" -o "$structure_dir/POPC.gro"; then
    die "POPC coordinate Download failed: $popc_url"
fi

if ! "$curl_bin" -fsSL --retry 3 "$pope_url" -o "$structure_dir/POPE.gro"; then
    die "POPE coordinate Download failed: $pope_url"
fi

if ! "$curl_bin" -fsSL --retry 3 "$cholesterol_url" -o "$structure_dir/CHOL15.gro"; then
    die "cholesterol coordinate Download failed: $cholesterol_url"
fi

# Also download the mmCIF for source-assembly and metadata checks.
if ! "$curl_bin" \
    -fsSL \
    "$assembly_cif_url" \
    -o "$structure_dir/1K4C-assembly1.cif"; then
    die "assembly Failed to download mmCIF: $assembly_cif_url"
fi

# Handle checksum command differences between Linux and macOS.
if command -v sha256sum >/dev/null 2>&1; then
    (
        cd "$structure_dir"
        sha256sum \
            1K4C-opm.pdb \
            3EFF-opm.pdb \
            1K4C-assembly1.cif \
            POPC.gro \
            POPE.gro \
            CHOL15.gro \
            > SHA256SUMS
    )
else
    (
        cd "$structure_dir"
        shasum \
            -a 256 \
            1K4C-opm.pdb \
            3EFF-opm.pdb \
            1K4C-assembly1.cif \
            POPC.gro \
            POPE.gro \
            CHOL15.gro \
            > SHA256SUMS
    )
fi

echo "Downloaded files and checksums: $structure_dir"
