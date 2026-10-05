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

echo "Downloading the T4 lysozyme L99A–toluene structure (PDB 4W53)."
if ! "$curl_bin" --fail --location --silent --show-error https://files.rcsb.org/download/4W53.pdb \
    -o "$generation_dir/4W53.raw.pdb"; then
    die "4W53 PDB Download failed: $structure_dir/4W53.raw.pdb"
fi
if ! "$curl_bin" --fail --location --silent --show-error https://files.rcsb.org/download/4W53.cif \
    -o "$generation_dir/4W53.cif"; then
    die "4W53 mmCIF Download failed: $structure_dir/4W53.cif"
fi
if ! "$curl_bin" --fail --location --silent --show-error https://files.rcsb.org/ligands/download/BNZ_ideal.sdf \
    -o "$generation_dir/BNZ_ideal.sdf"; then
    die "BNZ ideal SDF Download failed: $structure_dir/BNZ_ideal.sdf"
fi
if ! "$curl_bin" --fail --location --silent --show-error https://files.rcsb.org/ligands/download/MBN_ideal.sdf \
    -o "$generation_dir/MBN_ideal.sdf"; then
    die "MBN ideal SDF Download failed: $structure_dir/MBN_ideal.sdf"
fi

if command -v sha256sum >/dev/null 2>&1; then
    (cd "$generation_dir" && sha256sum 4W53.raw.pdb 4W53.cif BNZ_ideal.sdf MBN_ideal.sdf > SHA256SUMS)
elif command -v shasum >/dev/null 2>&1; then
    (cd "$generation_dir" && shasum -a 256 4W53.raw.pdb 4W53.cif BNZ_ideal.sdf MBN_ideal.sdf > SHA256SUMS)
else
    die "sha256sum or shasum is required."
fi

python3 helpers/publish_download.py "$generation_dir" "$structure_dir"

echo "Source structure: $structure_dir"
