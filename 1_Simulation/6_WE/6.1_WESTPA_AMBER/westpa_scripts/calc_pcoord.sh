#!/usr/bin/env bash
set -euo pipefail

if [[ $# -ne 1 ]]; then
    echo "사용법: $0 RESTART_FILE" >&2
    exit 2
fi

restart_file=$1
topology_file="$WORK_DIR/common_files/system.parm7"

if [[ ! -s "$restart_file" ]]; then
    echo "오류: progress coordinate용 restart를 찾을 수 없습니다: $restart_file" >&2
    exit 1
fi
if [[ ! -s "$topology_file" ]]; then
    echo "오류: progress coordinate용 topology를 찾을 수 없습니다: $topology_file" >&2
    exit 1
fi
if ! command -v "$CPPTRAJ" >/dev/null 2>&1; then
    echo "오류: $CPPTRAJ 실행 파일을 찾을 수 없습니다." >&2
    exit 1
fi

tmp_file=$(mktemp "${TMPDIR:-/tmp}/we-pcoord.XXXXXX")
trap 'rm -f "$tmp_file"' EXIT

"$CPPTRAJ" -p "$topology_file" > /dev/null <<EOF
trajin $restart_file
distance ion_distance @Na @Cl noimage out $tmp_file
run
EOF

awk 'NF >= 2 && $1 !~ /^#/ { value=$2 } END {
    if (value == "") exit 1
    printf "%.6f\n", value
}' "$tmp_file"
