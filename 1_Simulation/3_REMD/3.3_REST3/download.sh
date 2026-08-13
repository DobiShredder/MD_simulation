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

echo "Downloading the Chignolin structure (PDB 1UAO)."
mkdir -p "$structure_dir"

if ! "$curl_bin" \
    -fsSL \
    "$pdb_url" \
    -o "$structure_dir/1UAO.raw.pdb"; then
    die "Failed to download PDB: $pdb_url"
fi

if ! "$curl_bin" \
    -fsSL \
    "$cif_url" \
    -o "$structure_dir/1UAO.cif"; then
    die "Failed to download mmCIF: $cif_url"
fi

if command -v sha256sum >/dev/null 2>&1; then
    (
        cd "$structure_dir"
        sha256sum 1UAO.raw.pdb 1UAO.cif > SHA256SUMS
    )
else
    (
        cd "$structure_dir"
        shasum -a 256 1UAO.raw.pdb 1UAO.cif > SHA256SUMS
    )
fi

echo "Downloaded files and checksums: $structure_dir"

printf '\n'
echo "Downloading repex-topology-parser ${parser_version} source."
mkdir -p "$dependency_dir"

if ! "$curl_bin" \
    -fsSL \
    "$parser_url" \
    -o "$dependency_dir/$parser_archive"; then
    die "Failed to download parser source: $parser_url"
fi

if command -v sha256sum >/dev/null 2>&1; then
    actual_parser_sha256=$(sha256sum "$dependency_dir/$parser_archive" | awk '{print $1}')
else
    actual_parser_sha256=$(shasum -a 256 "$dependency_dir/$parser_archive" | awk '{print $1}')
fi

if [[ "$actual_parser_sha256" != "$parser_sha256" ]]; then
    die "Parser source checksum mismatch: $dependency_dir/$parser_archive"
fi

if ! tar -xzf "$dependency_dir/$parser_archive" -C "$dependency_dir"; then
    die "Failed to extract parser source: $dependency_dir/$parser_archive"
fi

if [[ ! -s "$parser_source" ]]; then
    die "Parser source not found after extraction: $parser_source"
fi

echo "Downloaded parser source: $parser_source"
