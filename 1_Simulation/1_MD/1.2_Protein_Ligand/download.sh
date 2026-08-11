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

# 사용자 설정과 output 경로
curl_bin=${CURL:-curl}

structure_dir="structure"

complex_pdb_url="https://files.rcsb.org/download/3HTB.pdb"
complex_cif_url="https://files.rcsb.org/download/3HTB.cif"
ligand_sdf_url="https://files.rcsb.org/ligands/download/JZ4_ideal.sdf"

# 실행 전 확인
if ! command -v "$curl_bin" >/dev/null 2>&1; then
    die "curl을 찾을 수 없습니다: $curl_bin"
fi

echo "T4 lysozyme–JZ4 구조를 다운로드합니다 (PDB 3HTB)."
mkdir -p "$structure_dir"

# Protein–ligand complex preparation에 사용할 PDB를 받습니다.
if ! "$curl_bin" \
    -fsSL \
    "$complex_pdb_url" \
    -o "$structure_dir/3HTB.raw.pdb"; then
    die "PDB 다운로드에 실패했습니다: $complex_pdb_url"
fi

# 원본 구조와 metadata를 확인할 mmCIF를 함께 받습니다.
if ! "$curl_bin" \
    -fsSL \
    "$complex_cif_url" \
    -o "$structure_dir/3HTB.cif"; then
    die "mmCIF 다운로드에 실패했습니다: $complex_cif_url"
fi

# JZ4 parameterization에 사용할 ideal SDF를 받습니다.
if ! "$curl_bin" \
    -fsSL \
    "$ligand_sdf_url" \
    -o "$structure_dir/JZ4_ideal.sdf"; then
    die "JZ4 SDF 다운로드에 실패했습니다: $ligand_sdf_url"
fi

# Linux와 macOS의 checksum command 차이를 처리합니다.
if command -v sha256sum >/dev/null 2>&1; then
    (
        cd "$structure_dir"
        sha256sum \
            3HTB.raw.pdb \
            3HTB.cif \
            JZ4_ideal.sdf \
            > SHA256SUMS
    )
else
    (
        cd "$structure_dir"
        shasum \
            -a 256 \
            3HTB.raw.pdb \
            3HTB.cif \
            JZ4_ideal.sdf \
            > SHA256SUMS
    )
fi

echo "다운로드 결과와 checksum: $structure_dir"
