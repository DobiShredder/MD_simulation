#!/usr/bin/env bash
set -euo pipefail

die() {
    echo "오류: $*" >&2
    exit 1
}

script_dir=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
structure_dir=${STRUCTURE_DIR:-"$script_dir/structure"}
curl_bin=${CURL:-curl}

if ! command -v "$curl_bin" >/dev/null 2>&1; then
    die "curl을 찾을 수 없습니다: $curl_bin"
fi

mkdir -p "$structure_dir"

echo "T4 lysozyme L99A–toluene 구조를 다운로드합니다 (PDB 4W53)."
if ! "$curl_bin" --fail --location --silent --show-error https://files.rcsb.org/download/4W53.pdb \
    -o "$structure_dir/4W53.raw.pdb"; then
    die "4W53 PDB 다운로드에 실패했습니다."
fi
if ! "$curl_bin" --fail --location --silent --show-error https://files.rcsb.org/download/4W53.cif \
    -o "$structure_dir/4W53.cif"; then
    die "4W53 mmCIF 다운로드에 실패했습니다."
fi
if ! "$curl_bin" --fail --location --silent --show-error https://files.rcsb.org/ligands/download/BNZ_ideal.sdf \
    -o "$structure_dir/BNZ_ideal.sdf"; then
    die "BNZ ideal SDF 다운로드에 실패했습니다."
fi
if ! "$curl_bin" --fail --location --silent --show-error https://files.rcsb.org/ligands/download/MBN_ideal.sdf \
    -o "$structure_dir/MBN_ideal.sdf"; then
    die "MBN ideal SDF 다운로드에 실패했습니다."
fi

if command -v sha256sum >/dev/null 2>&1; then
    (cd "$structure_dir" && sha256sum 4W53.raw.pdb 4W53.cif BNZ_ideal.sdf MBN_ideal.sdf > SHA256SUMS)
elif command -v shasum >/dev/null 2>&1; then
    (cd "$structure_dir" && shasum -a 256 4W53.raw.pdb 4W53.cif BNZ_ideal.sdf MBN_ideal.sdf > SHA256SUMS)
else
    die "sha256sum 또는 shasum이 필요합니다."
fi

echo "Source structure: $structure_dir"
