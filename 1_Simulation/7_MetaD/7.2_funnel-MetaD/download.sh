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
script_dir=$(dirname "${BASH_SOURCE[0]}")
if [[ "$script_dir" != /* ]]; then
    script_dir="$PWD/$script_dir"
fi
structure_dir="$script_dir/structure"
pdb_url="https://files.rcsb.org/download/3PTB.pdb"
cif_url="https://files.rcsb.org/download/3PTB.cif"
ligand_url="https://files.rcsb.org/ligands/download/BEN_ideal.sdf"

if ! command -v "$curl_bin" >/dev/null 2>&1; then
    die "curl을 찾을 수 없습니다: $curl_bin"
fi
mkdir -p "$structure_dir"

if ! "$curl_bin" -fsSL "$pdb_url" -o "$structure_dir/3PTB.raw.pdb"; then
    die "PDB 다운로드에 실패했습니다: $pdb_url"
fi
if ! "$curl_bin" -fsSL "$cif_url" -o "$structure_dir/3PTB.cif"; then
    die "mmCIF 다운로드에 실패했습니다: $cif_url"
fi
if ! "$curl_bin" -fsSL "$ligand_url" -o "$structure_dir/BEN_ideal.sdf"; then
    die "BEN SDF 다운로드에 실패했습니다: $ligand_url"
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

echo "Funnel geometry 검토용 3PTB 구조: $structure_dir"
