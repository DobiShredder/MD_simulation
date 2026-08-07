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

script_dir=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
structure_dir="$script_dir/structure"

assembly_pdb_url="https://files.rcsb.org/download/1K4C.pdb1"
assembly_cif_url="https://files.rcsb.org/download/1K4C-assembly1.cif"

# 실행 전 확인
if ! command -v "$curl_bin" >/dev/null 2>&1; then
    die "curl을 찾을 수 없습니다: $curl_bin"
fi

echo "KcsA biological assembly를 다운로드합니다 (PDB 1K4C)."
mkdir -p "$structure_dir"

# KcsA tetramer와 filter K+를 추출할 biological-assembly PDB를 받습니다.
if ! "$curl_bin" \
    -fsSL \
    "$assembly_pdb_url" \
    -o "$structure_dir/1K4C.pdb1"; then
    die "assembly PDB 다운로드에 실패했습니다: $assembly_pdb_url"
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
            1K4C.pdb1 \
            1K4C-assembly1.cif \
            > SHA256SUMS
    )
else
    (
        cd "$structure_dir"
        shasum \
            -a 256 \
            1K4C.pdb1 \
            1K4C-assembly1.cif \
            > SHA256SUMS
    )
fi

echo "다운로드 결과와 checksum: $structure_dir"
