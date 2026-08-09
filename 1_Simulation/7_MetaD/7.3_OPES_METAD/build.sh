#!/usr/bin/env bash
set -euo pipefail

die() {
    echo "오류: $*" >&2
    exit 1
}

script_dir=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
work_dir=${WORK_DIR:-"$script_dir/work"}
tleap=${TLEAP:-tleap}

if [[ "$work_dir" != /* ]]; then
    work_dir="$(pwd)/$work_dir"
fi

command -v "$tleap" >/dev/null 2>&1 || die "tleap을 찾을 수 없습니다: $tleap"
command -v python3 >/dev/null 2>&1 || die "python3를 찾을 수 없습니다."
mkdir -p "$work_dir"

if ! (
    cd "$work_dir"
    "$tleap" -f "$script_dir/inputs/tleap.in" > leap.log 2>&1
); then
    die "tleap 실행에 실패했습니다: $work_dir/leap.log"
fi
for output in system.parm7 system.rst7 system.pdb; do
    [[ -s "$work_dir/$output" ]] || die "build output이 없습니다: $work_dir/$output"
done
python3 "$script_dir/check_topology.py" "$work_dir/system.parm7" "$work_dir/cv_atoms.tsv"
echo "Topology build 완료: $work_dir"
