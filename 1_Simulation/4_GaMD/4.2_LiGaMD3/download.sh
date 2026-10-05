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

if [[ "${MD_WRITER_PARENT:-}" != "$PPID" || "${MD_WRITER_ENTRY:-}" != "$0" ]]; then
    exec python3 helpers/writer_guard.py \
        --registry work --write "$structure_dir" \
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
if ! command -v python3 >/dev/null 2>&1; then
    die "Python executable not found: python3"
fi

echo "Downloading the trypsin–benzamidine structure (PDB 3PTB)."

if ! "$curl_bin" -fsSL \
    https://files.rcsb.org/download/3PTB.pdb \
    -o "$generation_dir/3PTB.raw.pdb"; then
    die "PDB 3PTB Download failed: $structure_dir/3PTB.raw.pdb"
fi
if ! "$curl_bin" -fsSL \
    https://files.rcsb.org/download/3PTB.cif \
    -o "$generation_dir/3PTB.cif"; then
    die "3PTB mmCIF Download failed: $structure_dir/3PTB.cif"
fi
if ! "$curl_bin" -fsSL \
    https://files.rcsb.org/ligands/download/BEN_ideal.sdf \
    -o "$generation_dir/BEN_ideal.sdf"; then
    die "BEN ideal SDF Download failed: $structure_dir/BEN_ideal.sdf"
fi

if command -v sha256sum >/dev/null 2>&1; then
    (
        cd "$generation_dir"
        sha256sum 3PTB.raw.pdb 3PTB.cif BEN_ideal.sdf > SHA256SUMS
    )
else
    (
        cd "$generation_dir"
        shasum -a 256 3PTB.raw.pdb 3PTB.cif BEN_ideal.sdf > SHA256SUMS
    )
fi

python3 helpers/publish_download.py "$generation_dir" "$structure_dir"

echo "Downloaded files and checksums: $structure_dir"
