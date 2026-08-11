#!/usr/bin/env bash
set -euo pipefail

die() {
    echo "오류: $*" >&2
    exit 1
}

if [[ $# -ne 0 ]]; then
    echo "사용법: $0" >&2
    exit 2
fi

curl_bin=${CURL:-curl}
structure_dir="structure"
pdb_url="https://files.rcsb.org/download/1UAO.pdb"
cif_url="https://files.rcsb.org/download/1UAO.cif"

if ! command -v "$curl_bin" >/dev/null 2>&1; then
    die "curl을 찾을 수 없습니다: $curl_bin"
fi

echo "Chignolin 구조를 다운로드합니다 (PDB 1UAO)."
mkdir -p "$structure_dir"

if ! "$curl_bin" \
    -fsSL \
    "$pdb_url" \
    -o "$structure_dir/1UAO.raw.pdb"; then
    die "PDB 다운로드에 실패했습니다: $pdb_url"
fi

if ! "$curl_bin" \
    -fsSL \
    "$cif_url" \
    -o "$structure_dir/1UAO.cif"; then
    die "mmCIF 다운로드에 실패했습니다: $cif_url"
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

echo "다운로드 결과와 checksum: $structure_dir"

