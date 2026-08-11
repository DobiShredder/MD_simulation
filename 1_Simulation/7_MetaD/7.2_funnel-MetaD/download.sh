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
pdb_url="https://files.rcsb.org/download/3PTB.pdb"
cif_url="https://files.rcsb.org/download/3PTB.cif"
ligand_url="https://files.rcsb.org/ligands/download/BEN_ideal.sdf"

if ! command -v "$curl_bin" >/dev/null 2>&1; then
    die "curl not found: $curl_bin"
fi
mkdir -p "$structure_dir"

if ! "$curl_bin" -fsSL "$pdb_url" -o "$structure_dir/3PTB.raw.pdb"; then
    die "Failed to download PDB: $pdb_url"
fi
if ! "$curl_bin" -fsSL "$cif_url" -o "$structure_dir/3PTB.cif"; then
    die "Failed to download mmCIF: $cif_url"
fi
if ! "$curl_bin" -fsSL "$ligand_url" -o "$structure_dir/BEN_ideal.sdf"; then
    die "BEN SDF Download failed: $ligand_url"
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

echo "3PTB structure for reviewing funnel geometry: $structure_dir"
