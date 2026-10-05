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
dependency_dir="dependencies"
dependency_pending=".dependencies.download.pending"
pdb_url="https://files.rcsb.org/download/1UAO.pdb"
cif_url="https://files.rcsb.org/download/1UAO.cif"
parser_version="0.2.2"
parser_archive="repex_topology_parser-${parser_version}.tar.gz"
parser_url="https://files.pythonhosted.org/packages/d2/21/13792dda97e33ad2478f8ef5b5f1a6437ba84639b6cd94b798f23b9180ef/${parser_archive}"
parser_sha256="e51c369653988b37787b590c0f30bbd1c8589b7d3ce0fa840fa1cf85bce27b58"
parser_source="$dependency_dir/repex_topology_parser-${parser_version}/src/repex_topology_parser.py"

if ! command -v "$curl_bin" >/dev/null 2>&1; then
    die "curl not found: $curl_bin"
fi

if ! command -v tar >/dev/null 2>&1; then
    die "tar not found"
fi

if ! command -v python3 >/dev/null 2>&1; then
    die "Python executable not found: python3"
fi

echo "Downloading the Chignolin structure (PDB 1UAO)."
if [[ "${MD_WRITER_PARENT:-}" != "$PPID" || "${MD_WRITER_ENTRY:-}" != "$0" ]]; then
    exec python3 helpers/writer_guard.py \
        --registry work --write "$structure_dir" --write "$dependency_dir" \
        -- "$0" "$@"
fi
if [[ -e "$structure_dir/.download.pending" || -L "$structure_dir/.download.pending" || -e "$dependency_pending" || -L "$dependency_pending" ]]; then
    die "Download publication is incomplete; inspect $structure_dir/.download.pending or $dependency_pending."
fi

generation_dir=$(mktemp -d "$structure_dir.download.XXXXXX")
cleanup_download() {
    status=$?
    if [[ -e "$structure_dir/.download.pending" || -L "$structure_dir/.download.pending" || -e "$dependency_pending" || -L "$dependency_pending" ]]; then
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

if ! "$curl_bin" \
    -fsSL \
    "$pdb_url" \
    -o "$generation_dir/1UAO.raw.pdb"; then
    die "Failed to download PDB: $pdb_url"
fi

if ! "$curl_bin" \
    -fsSL \
    "$cif_url" \
    -o "$generation_dir/1UAO.cif"; then
    die "Failed to download mmCIF: $cif_url"
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


printf '\n'
echo "Downloading repex-topology-parser ${parser_version} source."
mkdir -p "$generation_dir/.dependencies"
staged_parser_source="$generation_dir/.dependencies/repex_topology_parser-${parser_version}/src/repex_topology_parser.py"

if ! "$curl_bin" \
    -fsSL \
    "$parser_url" \
    -o "$generation_dir/.dependencies/$parser_archive"; then
    die "Failed to download parser source: $parser_url"
fi

if command -v sha256sum >/dev/null 2>&1; then
    actual_parser_sha256=$(sha256sum "$generation_dir/.dependencies/$parser_archive" | awk '{print $1}')
else
    actual_parser_sha256=$(shasum -a 256 "$generation_dir/.dependencies/$parser_archive" | awk '{print $1}')
fi

if [[ "$actual_parser_sha256" != "$parser_sha256" ]]; then
    die "Parser source checksum mismatch: $generation_dir/.dependencies/$parser_archive"
fi

if ! tar -xzf "$generation_dir/.dependencies/$parser_archive" -C "$generation_dir/.dependencies"; then
    die "Failed to extract parser source: $generation_dir/.dependencies/$parser_archive"
fi

if [[ ! -s "$staged_parser_source" ]]; then
    die "Parser source not found after extraction: $staged_parser_source"
fi

python3 helpers/publish_download.py "$generation_dir" "$structure_dir" --dependencies "$dependency_dir"
echo "Downloaded files and checksums: $structure_dir"

echo "Downloaded parser source: $parser_source"
