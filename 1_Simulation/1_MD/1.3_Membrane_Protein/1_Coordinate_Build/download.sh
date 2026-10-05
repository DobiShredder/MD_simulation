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

if ! command -v python3 >/dev/null 2>&1; then
    die "Python executable not found: python3"
fi

echo "Downloading membrane-oriented KcsA from OPM (PDB 1K4C)."
if [[ "${MD_WRITER_PARENT:-}" != "$PPID" || "${MD_WRITER_ENTRY:-}" != "$0" ]]; then
    exec python3 helpers/writer_guard.py \
        --registry .. --write "$structure_dir" \
        -- "$0" "$@"
fi
if [[ -e "$structure_dir/.download.pending" || -L "$structure_dir/.download.pending" ]]; then
    die "Download publication is incomplete; inspect $structure_dir/.download.pending."
fi

generation_dir=$(mktemp -d "$structure_dir.download.XXXXXX")
cleanup_download() {
    status=$?
    if [[ -e "$structure_dir/.download.pending" || -L "$structure_dir/.download.pending" ]]; then
        echo "Warning: download publication is incomplete; staging retained: $generation_dir" >&2
    else
        case "$generation_dir" in
            "$structure_dir".download.*) rm -rf -- "$generation_dir" ;;
        esac
    fi
    exit "$status"
}
trap cleanup_download EXIT
trap 'exit 130' INT
trap 'exit 143' TERM

# The OPM PDB contains the protein orientation and membrane boundaries at z=±15 Å.
if ! "$curl_bin" \
    -fsSL \
    "$opm_pdb_url" \
    -o "$generation_dir/1K4C-opm.pdb"; then
    die "OPM Failed to download PDB: $opm_pdb_url"
fi

# Restore the missing Ser22 and Arg117 side chains in 1K4C from closed KcsA 3EFF.
if ! "$curl_bin" \
    -fsSL \
    "$sidechain_template_url" \
    -o "$generation_dir/3EFF-opm.pdb"; then
    die "side-chain template Download failed: $sidechain_template_url"
fi

# Download the 128-lipid bilayer coordinates equilibrated with Lipid21.
if ! "$curl_bin" -fsSL --retry 3 "$popc_url" -o "$generation_dir/POPC.gro"; then
    die "POPC coordinate Download failed: $popc_url"
fi

if ! "$curl_bin" -fsSL --retry 3 "$pope_url" -o "$generation_dir/POPE.gro"; then
    die "POPE coordinate Download failed: $pope_url"
fi

if ! "$curl_bin" -fsSL --retry 3 "$cholesterol_url" -o "$generation_dir/CHOL15.gro"; then
    die "cholesterol coordinate Download failed: $cholesterol_url"
fi

# Also download the mmCIF for source-assembly and metadata checks.
if ! "$curl_bin" \
    -fsSL \
    "$assembly_cif_url" \
    -o "$generation_dir/1K4C-assembly1.cif"; then
    die "assembly Failed to download mmCIF: $assembly_cif_url"
fi

# Handle checksum command differences between Linux and macOS.
if command -v sha256sum >/dev/null 2>&1; then
    (
        cd "$generation_dir"
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
        cd "$generation_dir"
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

python3 helpers/publish_download.py "$generation_dir" "$structure_dir"

echo "Downloaded files and checksums: $structure_dir"
