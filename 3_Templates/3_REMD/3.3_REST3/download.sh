#!/usr/bin/env bash
set -euo pipefail

if [[ "${1:-}" == -h || "${1:-}" == --help ]]; then
    cat <<'EOF'
Usage: ./download.sh PDB_ID

Download a PDB entry and the checksum-verified repex-topology-parser 0.2.2
source required for REST3 topology generation.

Options:
  -h, --help  Show this help message and exit.
EOF
    exit 0
fi
if [[ $# -ne 1 || ! "$1" =~ ^[A-Za-z0-9]{4}$ ]]; then
    echo "Error: provide one four-character PDB ID." >&2
    exit 2
fi

curl_bin=${CURL:-curl}
pdb_id=${1^^}
output="structure/$pdb_id.pdb"
if ! command -v "$curl_bin" >/dev/null 2>&1; then
    echo "Error: curl not found: $curl_bin" >&2
    exit 1
fi
mkdir -p structure
if ! "$curl_bin" -fsSL "https://files.rcsb.org/download/$pdb_id.pdb" -o "$output"; then
    echo "Error: failed to download PDB $pdb_id." >&2
    exit 1
fi
if [[ ! -s "$output" ]]; then
    echo "Error: downloaded PDB is empty: $output" >&2
    exit 1
fi

echo "Downloaded source structure: $output"

dependency_dir=dependencies
version=0.2.2
archive="repex_topology_parser-$version.tar.gz"
url="https://files.pythonhosted.org/packages/d2/21/13792dda97e33ad2478f8ef5b5f1a6437ba84639b6cd94b798f23b9180ef/$archive"
expected=e51c369653988b37787b590c0f30bbd1c8589b7d3ce0fa840fa1cf85bce27b58
mkdir -p "$dependency_dir"

if [[ ! -s "$dependency_dir/repex_topology_parser-$version/src/repex_topology_parser.py" ]]; then
    echo "Downloading repex-topology-parser $version source."
    if ! curl -fsSL "$url" -o "$dependency_dir/$archive"; then
        echo "Error: failed to download repex-topology-parser $version." >&2
        exit 1
    fi
    if command -v sha256sum >/dev/null 2>&1; then
        actual=$(sha256sum "$dependency_dir/$archive" | awk '{print $1}')
    else
        actual=$(shasum -a 256 "$dependency_dir/$archive" | awk '{print $1}')
    fi
    if [[ "$actual" != "$expected" ]]; then
        echo "Error: repex-topology-parser checksum mismatch." >&2
        exit 1
    fi
    if ! tar -xzf "$dependency_dir/$archive" -C "$dependency_dir"; then
        echo "Error: failed to extract $dependency_dir/$archive." >&2
        exit 1
    fi
fi

echo "REST3 parser source: $dependency_dir/repex_topology_parser-$version/src/repex_topology_parser.py"
