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

echo "Downloading the Chignolin structure (PDB 1UAO)."

if ! "$curl_bin" \
    -fsSL \
    https://files.rcsb.org/download/1UAO.pdb \
    -o "$generation_dir/1UAO.raw.pdb"; then
    die "PDB 1UAO Download failed: $structure_dir/1UAO.raw.pdb"
fi

if ! "$curl_bin" \
    -fsSL \
    https://files.rcsb.org/download/1UAO.cif \
    -o "$generation_dir/1UAO.cif"; then
    die "1UAO mmCIF Download failed: $structure_dir/1UAO.cif"
fi

if command -v sha256sum >/dev/null 2>&1; then
    (
        cd "$generation_dir"
        sha256sum 1UAO.raw.pdb 1UAO.cif > SHA256SUMS
    )
else
    (
        cd "$generation_dir"
        shasum -a 256 1UAO.raw.pdb 1UAO.cif > SHA256SUMS
    )
fi

python3 helpers/publish_download.py "$generation_dir" "$structure_dir"

echo "Downloaded files and checksums: $structure_dir"
