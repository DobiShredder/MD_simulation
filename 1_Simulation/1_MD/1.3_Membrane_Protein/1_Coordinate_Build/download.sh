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

script_dir=$(dirname "${BASH_SOURCE[0]}")
structure_dir="$script_dir/structure"

opm_pdb_url="https://opm-assets.storage.googleapis.com/pdb/1k4c.pdb"
sidechain_template_url="https://opm-assets.storage.googleapis.com/pdb/3eff.pdb"
assembly_cif_url="https://files.rcsb.org/download/1K4C-assembly1.cif"
popc_url="https://zenodo.org/records/14776136/files/POPC.gro"
pope_url="https://zenodo.org/records/14776136/files/POPE.gro"
cholesterol_url="https://zenodo.org/records/14776136/files/CHOL15.gro"

# 실행 전 확인
if ! command -v "$curl_bin" >/dev/null 2>&1; then
    die "curl을 찾을 수 없습니다: $curl_bin"
fi

echo "OPM에서 membrane에 정렬된 KcsA를 다운로드합니다 (PDB 1K4C)."
mkdir -p "$structure_dir"

# OPM PDB에는 protein orientation과 z=±15 Å membrane boundary가 들어 있습니다.
if ! "$curl_bin" \
    -fsSL \
    "$opm_pdb_url" \
    -o "$structure_dir/1K4C-opm.pdb"; then
    die "OPM PDB 다운로드에 실패했습니다: $opm_pdb_url"
fi

# 1K4C에서 빠진 Ser22와 Arg117 side-chain은 closed KcsA 3EFF에서 복원합니다.
if ! "$curl_bin" \
    -fsSL \
    "$sidechain_template_url" \
    -o "$structure_dir/3EFF-opm.pdb"; then
    die "side-chain template 다운로드에 실패했습니다: $sidechain_template_url"
fi

# Lipid21로 평형화한 128-lipid bilayer coordinate를 받습니다.
if ! "$curl_bin" -fsSL --retry 3 "$popc_url" -o "$structure_dir/POPC.gro"; then
    die "POPC coordinate 다운로드에 실패했습니다: $popc_url"
fi

if ! "$curl_bin" -fsSL --retry 3 "$pope_url" -o "$structure_dir/POPE.gro"; then
    die "POPE coordinate 다운로드에 실패했습니다: $pope_url"
fi

if ! "$curl_bin" -fsSL --retry 3 "$cholesterol_url" -o "$structure_dir/CHOL15.gro"; then
    die "cholesterol coordinate 다운로드에 실패했습니다: $cholesterol_url"
fi

# 원본 assembly와 metadata를 확인할 mmCIF를 함께 받습니다.
if ! "$curl_bin" \
    -fsSL \
    "$assembly_cif_url" \
    -o "$structure_dir/1K4C-assembly1.cif"; then
    die "assembly mmCIF 다운로드에 실패했습니다: $assembly_cif_url"
fi

# Linux와 macOS의 checksum command 차이를 처리합니다.
if command -v sha256sum >/dev/null 2>&1; then
    (
        cd "$structure_dir"
        sha256sum \
            1K4C-opm.pdb \
            3EFF-opm.pdb \
            1K4C-assembly1.cif \
            POPC.gro \
            POPE.gro \
            CHOL15.gro \
            > SHA256SUMS
    )
else
    (
        cd "$structure_dir"
        shasum \
            -a 256 \
            1K4C-opm.pdb \
            3EFF-opm.pdb \
            1K4C-assembly1.cif \
            POPC.gro \
            POPE.gro \
            CHOL15.gro \
            > SHA256SUMS
    )
fi

echo "다운로드 결과와 checksum: $structure_dir"
